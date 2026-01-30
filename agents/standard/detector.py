"""Detector agent that finds contradictions between verified sources."""

from langchain_openai import ChatOpenAI
from typing import Dict, List
from models.research import Contradiction, ResearchState, Source
from config.models import (
    get_model_for_phase,
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

    for idx, source_a in enumerate(sources):
        for source_b in sources[idx + 1 :]:
            comparisons += 1
            verdict = _compare_sources(source_a, source_b, llm)
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
    state.tokens_used = (state.tokens_used or 0) + comparisons * 150
    state.cost = (state.cost or 0.0)

    logger.info(state.contradiction_analysis)
    return state


def _compare_sources(
    source_a: Source, source_b: Source, llm: ChatOpenAI
) -> Dict[str, bool | str]:
    """Ask the LLM if Source A and Source B contradict each other."""
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

    try:
        parsed = json.loads(payload)
        return {
            "contradicts": parsed.get("contradicts", False),
            "severity": parsed.get("severity", "minor"),
            "description": parsed.get("description", ""),
        }
    except json.JSONDecodeError:
        logger.warning("Detector could not parse response, assuming no contradiction.")
        return {"contradicts": False, "severity": "minor", "description": "Parsing failed."}