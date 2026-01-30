"""Formatter agent that formats and polishes the final paper."""

from langchain_openai import ChatOpenAI
from typing import List, Tuple, Optional
import uuid
from models.research import ResearchState, TaskStatus
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


def formatter_node(state: ResearchState) -> ResearchState:
    """Format and polish the draft paper for final output."""
    if not state.draft_paper:
        state.status = TaskStatus.FAILED
        state.final_paper = "No draft provided to format."
        return state

    model = get_model_for_phase(
        research_mode=ResearchMode.STANDARD,
        phase=ModelPhase.FORMATTING,
    )

    llm = ChatOpenAI(
        model=model,
        temperature=0.25,
        max_completion_tokens=4000,
        **OPENROUTER_CONFIG,
    )

    paper_text = state.draft_paper
    if state.revision_needed and state.issues_found:
        try:
            revised_result = _revise_paper(llm, paper_text, state.issues_found)
            # _revise_paper now returns (revised_text, revision_tokens)
            if isinstance(revised_result, tuple) and len(revised_result) == 2:
                paper_text, revision_tokens = revised_result
            else:
                paper_text = revised_result
                revision_tokens = 0

            # Safely coerce and add revision tokens
            try:
                state.tokens_used = (state.tokens_used or 0) + int(revision_tokens or 0)
            except Exception:
                try:
                    state.tokens_used = (state.tokens_used or 0) + int(float(revision_tokens or 0))
                except Exception:
                    pass
        except Exception as e:
            logger.exception("Revision step failed")
            try:
                setattr(state, "revision_failed", True)
                setattr(state, "revision_error", "REVISION_FAILED")
            except Exception:
                try:
                    state.__dict__["revision_failed"] = True
                    state.__dict__["revision_error"] = "REVISION_FAILED"
                except Exception:
                    pass
            # revert to original draft if revision failed
            paper_text = state.draft_paper

    prompt = f"""You are a formatting specialist.

Reformat the paper below in APA 7th edition, polish section headings, and ensure citations are properly styled.

Paper:
{paper_text}

Return only the formatted paper."""

    try:
        response = llm.invoke(prompt)
        formatted = response.content if isinstance(response.content, str) else str(response.content)

        state.final_paper = formatted
        state.status = TaskStatus.COMPLETED

        # Try to extract actual token usage from LLM response metadata
        tokens = None
        try:
            usage = getattr(response, "usage", None)
            if usage is not None:
                # usage may be an object or dict
                total = getattr(usage, "total_tokens", None)
                if total is None and isinstance(usage, dict):
                    total = usage.get("total_tokens")
                if total is not None:
                    tokens = int(total)

            if tokens is None:
                meta = getattr(response, "meta", None)
                if isinstance(meta, dict):
                    tokens = meta.get("tokens")
                elif hasattr(meta, "tokens"):
                    tokens = getattr(meta, "tokens")
        except Exception:
            tokens = None

        # Base estimate and revise estimate if revision was applied earlier
        base_estimate = 2500
        revise_estimate = 1500 if (state.revision_needed and state.issues_found) else 0

        # Try to extract prompt/completion tokens separately
        prompt_tokens: Optional[int] = None
        completion_tokens: Optional[int] = None
        try:
            usage = getattr(response, "usage", None)
            if usage is not None:
                if isinstance(usage, dict):
                    prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
                    completion_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
                else:
                    prompt_tokens = getattr(usage, "prompt_tokens", None) or getattr(usage, "input_tokens", None)
                    completion_tokens = getattr(usage, "completion_tokens", None) or getattr(usage, "output_tokens", None)

            if (prompt_tokens is None or completion_tokens is None) and hasattr(response, "meta"):
                meta = getattr(response, "meta")
                if isinstance(meta, dict):
                    prompt_tokens = prompt_tokens or meta.get("prompt_tokens") or meta.get("input_tokens")
                    completion_tokens = completion_tokens or meta.get("completion_tokens") or meta.get("output_tokens")
        except Exception:
            prompt_tokens = prompt_tokens or None
            completion_tokens = completion_tokens or None

        # Fallback to conservative split if missing
        if prompt_tokens is None or completion_tokens is None:
            total_estimate = (base_estimate + revise_estimate) if tokens is None else int(tokens)
            # assume 30% input, 70% output
            prompt_tokens = int(total_estimate * 0.3)
            completion_tokens = max(0, int(total_estimate - prompt_tokens))

        # Add revision tokens if they were returned earlier (already added to tokens_used above)
        state.tokens_used = (state.tokens_used or 0) + int(prompt_tokens or 0) + int(completion_tokens or 0)

        # Compute cost using separate input/output pricing
        try:
            pricing = get_model_pricing(model)
            cost_per_token_input = (pricing.get("input", 0.0) or 0.0) / 1_000_000
            cost_per_token_output = (pricing.get("output", 0.0) or 0.0) / 1_000_000

            input_cost = int(prompt_tokens or 0) * cost_per_token_input
            output_cost = int(completion_tokens or 0) * cost_per_token_output

            state.cost = (state.cost or 0.0) + input_cost + output_cost
        except Exception:
            state.cost = (state.cost or 0.0)
    except Exception as exc:
        logger.exception("Formatter LLM invoke failed")
        # Mark task failed and return a safe, non-sensitive message
        state.status = TaskStatus.FAILED
        err_id = uuid.uuid4().hex[:8]
        state.final_paper = f"Formatting failed due to an internal error (ERR-{err_id})."
        return state

    logger.info("Formatter completed final formatting")
    return state


def _revise_paper(llm: ChatOpenAI, paper: str, issues: List[str]) -> Tuple[str, int]:
    """Revise paper to address identified issues and return (revised_text, revision_tokens)."""
    prompt = f"""You are a revision assistant.

Address the following issues when revising the paper:
{json.dumps(issues, indent=2)}

Paper:
{paper}

Return a revised version of the paper."""
    response = llm.invoke(prompt)
    revised = response.content if isinstance(response.content, str) else str(response.content)

    # attempt to extract token usage for the revision call
    revision_tokens = None
    try:
        usage = getattr(response, "usage", None)
        if usage is not None:
            if isinstance(usage, dict):
                revision_tokens = usage.get("total_tokens") or (usage.get("prompt_tokens") or 0) + (usage.get("completion_tokens") or 0)
            else:
                revision_tokens = getattr(usage, "total_tokens", None) or (getattr(usage, "prompt_tokens", 0) + getattr(usage, "completion_tokens", 0))
        if revision_tokens is None and hasattr(response, "meta"):
            meta = getattr(response, "meta")
            if isinstance(meta, dict):
                revision_tokens = meta.get("tokens")
    except Exception:
        revision_tokens = None

    if revision_tokens is None:
        # conservative fallback estimate for revision
        revision_tokens = 1500

    try:
        revision_tokens = int(revision_tokens)
    except Exception:
        try:
            revision_tokens = int(float(revision_tokens))
        except Exception:
            revision_tokens = 1500

    return revised, revision_tokens