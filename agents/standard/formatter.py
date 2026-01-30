"""Formatter agent that formats and polishes the final paper."""

from langchain_openai import ChatOpenAI
from typing import List
from models.research import ResearchState, TaskStatus
from config.models import (
    get_model_for_phase,
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
        paper_text = _revise_paper(llm, paper_text, state.issues_found)

    prompt = f"""You are a formatting specialist.

Reformat the paper below in APA 7th edition, polish section headings, and ensure citations are properly styled.

Paper:
{paper_text}

Return only the formatted paper."""

    response = llm.invoke(prompt)
    formatted = response.content if isinstance(response.content, str) else str(response.content)

    state.final_paper = formatted
    state.status = TaskStatus.COMPLETED
    state.tokens_used = (state.tokens_used or 0) + 2500
    state.cost = (state.cost or 0.0)

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