"""Formatter agent that formats and polishes the final paper."""

from langchain_openai import ChatOpenAI
from typing import List
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
            paper_text = _revise_paper(llm, paper_text, state.issues_found)
        except Exception as e:
            logger.exception("Revision step failed")
            # record failure on state but do not let exception propagate
            try:
                setattr(state, "revision_failed", True)
                setattr(state, "revision_error", str(e))
            except Exception:
                try:
                    state.__dict__["revision_failed"] = True
                    state.__dict__["revision_error"] = str(e)
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

        if tokens is None:
            tokens = base_estimate + revise_estimate

        state.tokens_used = (state.tokens_used or 0) + int(tokens)

        # Compute cost using model pricing (per million tokens)
        try:
            pricing = get_model_pricing(model)
            cost_per_million = pricing.get("input", 0.0) + pricing.get("output", 0.0)
            cost_per_token = cost_per_million / 1_000_000
            state.cost = (state.cost or 0.0) + (int(tokens) * cost_per_token)
        except Exception:
            state.cost = (state.cost or 0.0)
    except Exception as exc:
        logger.exception("Formatter LLM invoke failed")
        # Mark task failed and return a safe value
        state.status = TaskStatus.FAILED
        state.final_paper = f"Formatting failed: {str(exc)}"
        return state

    logger.info("Formatter completed final formatting")
    return state


def _revise_paper(llm: ChatOpenAI, paper: str, issues: List[str]) -> str:
    """Revise paper to address identified issues."""
    prompt = f"""You are a revision assistant.

Address the following issues when revising the paper:
{json.dumps(issues, indent=2)}

Paper:
{paper}

Return a revised version of the paper."""
    response = llm.invoke(prompt)
    return response.content if isinstance(response.content, str) else str(response.content)