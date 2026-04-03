"""Detector agent that finds contradictions between verified sources."""

import asyncio
import random
import json
import logging
from functools import reduce
from langchain_openai import ChatOpenAI
from typing import Dict, List, Tuple
from ...models.research import Contradiction, ResearchState, Source
from ...config.models import (
    get_model_for_phase,
    get_model_pricing,
    ModelPhase,
    ResearchMode,
    OPENROUTER_CONFIG,
)

logger = logging.getLogger(__name__)


async def detector_node_async(state: ResearchState) -> ResearchState:
    """Async implementation: Compare verified sources to surface contradictions with intelligent sampling."""
    from ...config.timeout_config import (
        DETECTOR_MAX_COMPARISONS,
        DETECTOR_MAX_CONCURRENCY,
        DETECTOR_MIN_COMPARISONS,
    )
    
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

    # Generate all possible pairs
    all_pairs = [(sources[i], sources[j]) for i in range(len(sources)) for j in range(i + 1, len(sources))]
    total_possible = len(all_pairs)
    
    # Determine pairs to compare (PHASE 5: intelligent sampling)
    if total_possible <= DETECTOR_MAX_COMPARISONS:
        pairs_to_compare = all_pairs
        sampling_used = False
        logger.info(f"[Phase 5] Detector: Comparing all {total_possible} pairs (below threshold)")
    else:
        pairs_to_compare = _select_pairs_to_compare(all_pairs, sources, DETECTOR_MAX_COMPARISONS, DETECTOR_MIN_COMPARISONS)
        sampling_used = True
        logger.info(f"[Phase 5] Detector: Sampling {len(pairs_to_compare)}/{total_possible} pairs using intelligent prioritization")

    # PHASE 5: Async batching with semaphore control
    contradictions: List[Contradiction] = []
    total_input_tokens = 0
    total_output_tokens = 0
    
    semaphore = asyncio.Semaphore(DETECTOR_MAX_CONCURRENCY)
    
    async def compare_with_semaphore(source_a: Source, source_b: Source) -> Tuple[Dict, Dict, Source, Source]:
        """Acquire semaphore, run comparison in executor to avoid blocking."""
        async with semaphore:
            loop = asyncio.get_running_loop()
            verdict, cost_info = await loop.run_in_executor(None, _compare_sources, source_a, source_b, llm)
            return verdict, cost_info, source_a, source_b
    
    # Create and await all comparison tasks
    tasks = [compare_with_semaphore(a, b) for a, b in pairs_to_compare]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results and collect contradictions
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"[Phase 5] Comparison failed: {result}")
            continue
        
        verdict, cost_info, source_a, source_b = result
        
        # Accumulate token counts safely
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
    sampling_note = " (sampling applied)" if sampling_used else ""
    state.contradiction_analysis = f"Detected {len(contradictions)} contradictions across {len(pairs_to_compare)} comparisons{sampling_note}."
    
    # Update tokens used from actual comparison counts
    computed_tokens = (total_input_tokens or 0) + (total_output_tokens or 0)
    fallback_per_comparison = 150
    if computed_tokens > 0:
        state.tokens_used = (state.tokens_used or 0) + int(computed_tokens)
    else:
        state.tokens_used = (state.tokens_used or 0) + (len(pairs_to_compare) * fallback_per_comparison)

    # Compute cost using separate input/output pricing
    try:
        pricing = get_model_pricing(model)
        cost_per_token_input = (pricing.get("input", 0.0) or 0.0) / 1_000_000
        cost_per_token_output = (pricing.get("output", 0.0) or 0.0) / 1_000_000

        input_cost = (total_input_tokens or 0) * cost_per_token_input
        output_cost = (total_output_tokens or 0) * cost_per_token_output

        if (total_input_tokens or 0) + (total_output_tokens or 0) == 0:
            fallback_tokens = len(pairs_to_compare) * fallback_per_comparison
            input_cost = int(fallback_tokens * 0.3) * cost_per_token_input
            output_cost = int(fallback_tokens * 0.7) * cost_per_token_output

        state.cost = (state.cost or 0.0) + input_cost + output_cost
    except Exception:
        state.cost = state.cost or 0.0

    logger.info(state.contradiction_analysis)
    return state


def _select_pairs_to_compare(
    all_pairs: List[Tuple[Source, Source]],
    sources: List[Source],
    max_comparisons: int,
    min_comparisons: int,
) -> List[Tuple[Source, Source]]:
    """
    Intelligently select high-value pairs for comparison.
    
    Prioritizes:
    1. High relevance scores
    2. Recent sources (by index position)
    3. Diverse pairings
    
    Args:
        all_pairs: All possible source pairs
        sources: List of all sources (with index priority)
        max_comparisons: Maximum pairs to select
        min_comparisons: Minimum priority pairs to include
        
    Returns:
        Intelligently selected subset of pairs
    """
    if not all_pairs:
        return []
    
    if len(all_pairs) <= max_comparisons:
        return all_pairs
    
    # Calculate priority score for each source (relevance + recency)
    source_priority: Dict[str, float] = {}
    for idx, source in enumerate(sources):
        relevance = getattr(source, 'relevance_score', 0) or 0.0
        recency_bonus = 1.0 / (idx + 1)  # Recent sources get higher bonus
        source_priority[source.id] = relevance + recency_bonus
    
    # Score each pair (sum of source priorities)
    pair_scores: Dict[int, float] = {}
    for i, (source_a, source_b) in enumerate(all_pairs):
        score = source_priority.get(source_a.id, 0.0) + source_priority.get(source_b.id, 0.0)
        pair_scores[i] = score
    
    # Sort indices by score (highest first)
    sorted_indices = sorted(range(len(all_pairs)), key=lambda i: pair_scores[i], reverse=True)
    
    # Select top priority pairs (capped to max_comparisons)
    priority_count = min(max(min_comparisons, max_comparisons // 2), max_comparisons)
    selected_indices: set = set(sorted_indices[:priority_count])
    
    # Randomly sample remaining pairs to fill quota
    remaining_indices = [i for i in sorted_indices[priority_count:]]
    additional_needed = max(0, max_comparisons - len(selected_indices))
    if remaining_indices and additional_needed > 0:
        additional = random.sample(remaining_indices, min(len(remaining_indices), additional_needed))
        selected_indices.update(additional)
    
    # Return selected pairs in original order for consistency
    return [all_pairs[i] for i in sorted(selected_indices)]


def detector_node(state: ResearchState) -> ResearchState:
    """Sync wrapper for detector_node_async to handle both sync and async contexts."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    
    if loop is None:
        # No running loop - we're in sync context, safe to use asyncio.run
        return asyncio.run(detector_node_async(state))
    else:
        # Already in async context - need to run in thread executor to avoid nested loop
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, detector_node_async(state))
            return future.result()


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
    payload = (
        response.content if isinstance(response.content, str) else str(response.content)
    )

    # Extract usage metadata if available
    input_tokens = None
    output_tokens = None
    try:
        usage = getattr(response, "usage", None)
        if usage is not None:
            if isinstance(usage, dict):
                input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
                output_tokens = usage.get("completion_tokens") or usage.get(
                    "output_tokens"
                )
            else:
                input_tokens = getattr(usage, "prompt_tokens", None) or getattr(
                    usage, "input_tokens", None
                )
                output_tokens = getattr(usage, "completion_tokens", None) or getattr(
                    usage, "output_tokens", None
                )

        # meta fallback
        if (input_tokens is None or output_tokens is None) and hasattr(
            response, "meta"
        ):
            meta = getattr(response, "meta")
            if isinstance(meta, dict):
                input_tokens = (
                    input_tokens
                    or meta.get("prompt_tokens")
                    or meta.get("input_tokens")
                )
                output_tokens = (
                    output_tokens
                    or meta.get("completion_tokens")
                    or meta.get("output_tokens")
                )
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
            logger.warning(
                "Detector parsed non-dict JSON; falling back to no-contradiction."
            )
            verdict = {
                "contradicts": False,
                "severity": "minor",
                "description": "Non-dict response.",
            }
        else:
            verdict = {
                "contradicts": parsed.get("contradicts", False),
                "severity": parsed.get("severity", "minor"),
                "description": parsed.get("description", ""),
            }
    except json.JSONDecodeError:
        logger.warning("Detector could not parse response, assuming no contradiction.")
        verdict = {
            "contradicts": False,
            "severity": "minor",
            "description": "Parsing failed.",
        }

    cost_info = {
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
    }
    return verdict, cost_info
