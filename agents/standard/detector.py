"""Detector agent that finds contradictions between verified sources."""

from langchain_openai import ChatOpenAI
from typing import Dict, List, Tuple
from models.research import Contradiction, ResearchState, Source
from config.models import (
    get_model_for_phase,
    get_model_pricing,
    ModelPhase,
    ResearchMode,
    OPENROUTER_CONFIG,
)
import json
import logging

logger = logging.getLogger(__name__)


def detector_node(state: ResearchState) -> ResearchState:
    """Compare verified sources to surface contradictions."""
    sources = state.verified_sources or []
    if len(sources) < 2:
        state.contradictions = []
        state.contradiction_analysis = "Not enough verified sources to compare."
        return state

    model = get_model_for_phase(
        research_mode=ResearchMode.STANDARD,
        phase=ModelPhase.DETECTION,
    )

    llm = ChatOpenAI(
        model=model,
        temperature=0.3,
        max_completion_tokens=1500,
        **OPENROUTER_CONFIG,
    )

    contradictions: List[Contradiction] = []
    comparisons = 0
    total_input_tokens = 0
    total_output_tokens = 0

    for idx, source_a in enumerate(sources):
        for source_b in sources[idx + 1 :]:
            comparisons += 1
            verdict, cost_info = _compare_sources(source_a, source_b, llm)
            # accumulate token counts per comparison (safely coercing)
            try:
                total_input_tokens += int(cost_info.get("input_tokens", 0) or 0)
            except Exception:
                total_input_tokens += 0
            try:
                total_output_tokens += int(cost_info.get("output_tokens", 0) or 0)
            except Exception:
                total_output_tokens += 0

            if verdict.get("contradicts"):
                contradictions.append(
                    Contradiction(
                        source_a_id=source_a.id,
                        source_b_id=source_b.id,
                        claim_a=source_a.excerpt or source_a.title,
                        claim_b=source_b.excerpt or source_b.title,
                        severity=str(verdict.get("severity", "minor")),
                        description=str(verdict.get("description", "Conflicting claims")),
                    )
                )

    state.contradictions = contradictions
    state.contradiction_analysis = (
        f"Detected {len(contradictions)} contradictions across {comparisons} comparisons."
    )
    # Update tokens used from actual comparison counts
    computed_tokens = (total_input_tokens or 0) + (total_output_tokens or 0)
    # conservative fallback per-comparison estimate
    fallback_per_comparison = 150
    if computed_tokens > 0:
        state.tokens_used = (state.tokens_used or 0) + int(computed_tokens)
    else:
        # conservative fallback per-comparison estimate
        fallback_per_comparison = 150
        state.tokens_used = (state.tokens_used or 0) + (comparisons * fallback_per_comparison)

    # Compute cost using separate input/output pricing
    try:
        pricing = get_model_pricing(model)
        cost_per_token_input = (pricing.get("input", 0.0) or 0.0) / 1_000_000
        cost_per_token_output = (pricing.get("output", 0.0) or 0.0) / 1_000_000

        input_cost = (total_input_tokens or 0) * cost_per_token_input
        output_cost = (total_output_tokens or 0) * cost_per_token_output

        if (total_input_tokens or 0) + (total_output_tokens or 0) == 0:
            # fallback: use comparisons * fallback_per_comparison split conservatively
            fallback_tokens = comparisons * fallback_per_comparison
            # assume 30% input, 70% output for fallback
            input_cost = int(fallback_tokens * 0.3) * cost_per_token_input
            output_cost = int(fallback_tokens * 0.7) * cost_per_token_output

        state.cost = (state.cost or 0.0) + input_cost + output_cost
    except Exception:
        state.cost = (state.cost or 0.0)

    logger.info(state.contradiction_analysis)
    return state


def _compare_sources(
    source_a: Source, source_b: Source, llm: ChatOpenAI
) -> Tuple[Dict[str, bool | str], Dict[str, int]]:
    """Ask the LLM if Source A and Source B contradict each other.

    Returns a tuple of (verdict_dict, cost_info) where cost_info contains
    input_tokens and output_tokens estimates for this comparison.
    """
    prompt = f"""You are a contradiction analyst.

Compare the claims below and decide whether they contradict.

Source A: {source_a.title}
Claim A: {source_a.excerpt or 'No excerpt available'}

Source B: {source_b.title}
Claim B: {source_b.excerpt or 'No excerpt available'}

Return JSON only:
{{
  "contradicts": true/false,
  "severity": "critical/major/minor",
  "description": "One-sentence explanation"
}}
"""

    response = llm.invoke(prompt)
    payload = response.content if isinstance(response.content, str) else str(response.content)

    # Extract usage metadata if available
    input_tokens = None
    output_tokens = None
    try:
        usage = getattr(response, "usage", None)
        if usage is not None:
            if isinstance(usage, dict):
                input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
                output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
            else:
                input_tokens = getattr(usage, "prompt_tokens", None) or getattr(usage, "input_tokens", None)
                output_tokens = getattr(usage, "completion_tokens", None) or getattr(usage, "output_tokens", None)

        # meta fallback
        if (input_tokens is None or output_tokens is None) and hasattr(response, "meta"):
            meta = getattr(response, "meta")
            if isinstance(meta, dict):
                input_tokens = input_tokens or meta.get("prompt_tokens") or meta.get("input_tokens")
                output_tokens = output_tokens or meta.get("completion_tokens") or meta.get("output_tokens")
    except Exception:
        input_tokens = input_tokens or None
        output_tokens = output_tokens or None

    # conservative token estimates if metadata missing
    if input_tokens is None:
        input_tokens = max(50, int(len(prompt) / 4))
    if output_tokens is None:
        output_tokens = max(50, int(len(payload) / 4)) if payload else 150

    try:
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            logger.warning("Detector parsed non-dict JSON; falling back to no-contradiction.")
            verdict = {"contradicts": False, "severity": "minor", "description": "Non-dict response."}
        else:
            verdict = {
                "contradicts": parsed.get("contradicts", False),
                "severity": parsed.get("severity", "minor"),
                "description": parsed.get("description", ""),
            }
    except json.JSONDecodeError:
        logger.warning("Detector could not parse response, assuming no contradiction.")
        verdict = {"contradicts": False, "severity": "minor", "description": "Parsing failed."}

    cost_info = {"input_tokens": int(input_tokens or 0), "output_tokens": int(output_tokens or 0)}
    return verdict, cost_info