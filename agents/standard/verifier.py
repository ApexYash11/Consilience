"""
Verifier Agent: Filters sources through credibility assessment.

Uses DeepSeek R1 Distill Qwen 7B (free) for verification.
- Strong reasoning for credibility assessment
- Fast inference with 32K context
- $0.00 cost
"""

from langchain_openai import ChatOpenAI
from models.research import ResearchState, Source, TaskStatus
from config.models import (
    get_model_for_phase,
    ModelPhase,
    ResearchMode,
    OPENROUTER_CONFIG,
)
from typing import List
import json
import logging
import time

logger = logging.getLogger(__name__)


def verifier_node(state: ResearchState) -> ResearchState:
    """Evaluate source list and keep high-credibility entries."""
    try:
        if not state.sources:
            logger.warning("Verifier received no sources to evaluate")
            state.verified_sources = []
            state.verification_notes = "No sources provided"
            return state

        model = get_model_for_phase(
            research_mode=ResearchMode.STANDARD,
            phase=ModelPhase.VERIFICATION,
        )

        llm = ChatOpenAI(
            model=model,
            temperature=0.25,
            max_completion_tokens=2000,
            **OPENROUTER_CONFIG,
        )

        verified: List[Source] = []
        rejected: List[Source] = []

        logger.info(f"Verifying {len(state.sources)} sources")

        for source in state.sources:
            score = evaluate_source(source, llm)

            if score >= 0.7:
                source.verified = True
                source.credibility = score
                verified.append(source)
                logger.debug(f"Source verified: {source.title} (score: {score:.2f})")
            else:
                rejected.append(source)
                source.verified = False
                source.credibility = score
                logger.debug(f"Source rejected: {source.title} (score: {score:.2f})")

        state.verified_sources = verified
        state.verification_notes = (
            f"Verified {len(verified)}/{len(state.sources)} sources; rejected {len(rejected)}."
        )

        state.tokens_used = (state.tokens_used or 0) + (len(state.sources) * 200)
        state.cost = (state.cost or 0.0) + 0.0

        logger.info(
            f"Verifier complete: {len(verified)} sources passed, {len(rejected)} failed"
        )

        return state

    except Exception as exc:
        logger.error("Verifier node failed", exc_info=True)
        state.status = TaskStatus.FAILED
        raise ValueError(f"Verification failed: {str(exc)}") from exc


def evaluate_source(source: Source, llm: ChatOpenAI) -> float:
    """Score source credibility on 0.0-1.0 scale."""
    prompt = f"""You are a meticulous research verifier.

Evaluate the following source and return JSON with {{"score": ..., "reason": ...}}:

Title: {source.title}
Authors: {source.authors}
Publication: {source.publication}
Year: {source.year}
DOI: {source.doi or 'None'}
URL: {source.url or 'None'}

Score guidelines:
- 0.9-1.0: Peer-reviewed journal, recent, multiple citations
- 0.7-0.9: Credible outlet with strong evidence
- 0.5-0.7: Legitimate source but lesser-known
- 0.0-0.5: Weak credibility or unverifiable

Return JSON only:
{{
    "score": 0.0,
    "reason": "..."
}}
"""

    # Invoke the LLM with retries and backoff to handle transient errors.
    response = None
    attempts = 3
    for attempt in range(1, attempts + 1):
        try:
            response = llm.invoke(prompt)
            break
        except Exception as e:
            logger.warning(
                f"LLM invoke attempt {attempt} failed for source '{source.title}': {str(e)}"
            )
            if attempt < attempts:
                backoff = 2 ** attempt
                time.sleep(backoff)
            else:
                logger.exception("LLM invoke ultimately failed; falling back to heuristic scoring")

    if response is None:
        # Fall back to heuristic scoring on repeated failure
        return heuristic_score(source)

    try:
        payload = response.content if isinstance(response.content, str) else str(response.content)

        # Strip surrounding triple-backtick fences (e.g., ```json ... ```) if present
        import re

        fenced = re.search(r"```(?:[\w+-]+\n)?(.*?)```", payload, re.DOTALL)
        if fenced:
            payload = fenced.group(1).strip()

        data = json.loads(payload)

        raw_score = data.get("score", None)
        # Validate numeric score; fall back to heuristic if not numeric
        if isinstance(raw_score, (int, float)):
            score = float(raw_score)
        else:
            try:
                score = float(raw_score)
            except Exception:
                score = heuristic_score(source)
    except json.JSONDecodeError:
        score = heuristic_score(source)

    return max(0.0, min(score, 1.0))


def heuristic_score(source: Source) -> float:
    """Fallback scoring when LLM response cannot be parsed."""
    score = 0.5
    if source.doi:
        score += 0.2
    if source.year and source.year >= 2020:
        score += 0.15
    if "journal" in (source.publication or "").lower():
        score += 0.15
    return min(score, 1.0)