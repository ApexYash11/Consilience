"""Reviewer agent that validates the draft paper."""

from langchain_openai import ChatOpenAI
from models.research import ResearchState, TaskStatus
from config.models import (
    get_model_for_phase,
    ModelPhase,
    ResearchMode,
    OPENROUTER_CONFIG,
)
import json
import logging
from utils.cost_estimator import estimate_cost_from_response

logger = logging.getLogger(__name__)


def reviewer_node(state: ResearchState) -> ResearchState:
    """Run structured peer review on draft paper."""
    if not state.draft_paper:
        state.review_feedback = "No draft available for review"
        state.issues_found = ["Draft paper missing"]
        state.revision_needed = True
        return state

    model = get_model_for_phase(
        research_mode=ResearchMode.STANDARD,
        phase=ModelPhase.REVIEW,
    )

    llm = ChatOpenAI(
        model=model,
        temperature=0.4,
        max_completion_tokens=3000,
        **OPENROUTER_CONFIG,
    )

    prompt = f"""You are an academic reviewer.

Read this draft and return structured JSON feedback:
{{
  "feedback": "summary",
  "issues": ["issue1", "issue2"],
  "revision_needed": true/false,
  "severity": "major/minor"
}}

Paper:
{state.draft_paper}
"""

    try:
        response = llm.invoke(prompt)
        payload = response.content if isinstance(response.content, str) else str(response.content)
    except Exception as e:
        logger.exception("Reviewer LLM invoke failed")
        # Record failure state and return safely so workflow can handle it
        state.review_feedback = f"Review failed: {str(e)}"
        state.issues_found = ["LLM invoke error"]
        state.revision_needed = True
        state.status = TaskStatus.FAILED
        return state

    try:
        result = json.loads(payload)
    except json.JSONDecodeError:
        logger.warning("Reviewer response could not be parsed as JSON")
        state.review_feedback = "Review LLM failed to return parseable output"
        state.issues_found = ["JSON parse failure"]
        state.revision_needed = True
        return state

    state.review_feedback = result.get("feedback", "No feedback provided")
    state.issues_found = result.get("issues", [])
    state.revision_needed = result.get("revision_needed", False)
    # Extract token usage and cost from the LLM response when available
    try:
        cost_info = estimate_cost_from_response(response, model)
        state.tokens_used = (state.tokens_used or 0) + int(cost_info.get("total_tokens", 0))
        state.cost = (state.cost or 0.0) + float(cost_info.get("cost", 0.0))
    except Exception:
        # Fallback to the previous rough values if cost estimation fails
        state.tokens_used = (state.tokens_used or 0) + 3500
        state.cost = (state.cost or 0.0)

    return state