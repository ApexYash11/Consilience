"""Reviewer agent that validates the draft paper."""

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from ...models.research import ResearchState, TaskStatus
from ...config.models import (
    get_model_for_phase,
    ModelPhase,
    ResearchMode,
    OPENROUTER_CONFIG,
)
from ...services.llm_call_helper import call_llm_sync
import json
import logging
from ...utils.cost_estimator import estimate_cost_from_response

logger = logging.getLogger(__name__)


def reviewer_node(state: ResearchState) -> ResearchState:
    """Run structured peer review on draft paper.
    
    PART 4: Enhanced timeout detection for revision loop termination.
    """
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
        response = call_llm_sync(llm, [HumanMessage(content=prompt)], agent_name="reviewer")
        payload = (
            response.content
            if isinstance(response.content, str)
            else str(response.content)
        )
    except TimeoutError as e:
        # PART 4: Timeout detection - mark for retry handler
        logger.error(f"[PART 4] Reviewer LLM timed out: {e}")
        state.review_failed = True
        state.review_feedback = f"Review timed out (60s limit exceeded)"
        state.issues_found = ["LLM timeout"]
        state.revision_needed = True  # Request retry
        logger.info(
            f"[DEBUG VALIDATION] Reviewer timeout on attempt {state.current_revision_attempt}. "
            f"Setting review_failed=True for check_revision_and_revise to detect."
        )
        return state
    except Exception as e:
        # PART 4: Other exceptions - record failure
        logger.exception(f"[PART 4] Reviewer LLM invoke failed: {e}")
        state.review_failed = True
        state.review_feedback = f"Review failed: {str(e)}"
        state.issues_found = ["LLM invoke error"]
        state.revision_needed = True
        state.status = TaskStatus.FAILED
        return state

    try:
        result = json.loads(payload)
    except json.JSONDecodeError:
        logger.warning("Reviewer response could not be parsed as JSON")
        state.review_failed = True
        state.review_feedback = "Review LLM failed to return parseable output"
        state.issues_found = ["JSON parse failure"]
        state.revision_needed = True
        return state

    # Success case
    state.review_failed = False
    state.review_feedback = result.get("feedback", "No feedback provided")
    state.issues_found = result.get("issues", [])
    state.revision_needed = result.get("revision_needed", False)
    # Extract token usage and cost from the LLM response when available
    try:
        cost_info = estimate_cost_from_response(response, model)
        state.tokens_used = (state.tokens_used or 0) + int(
            cost_info.get("total_tokens", 0)
        )
        state.cost = (state.cost or 0.0) + float(cost_info.get("cost", 0.0))
    except Exception:
        # Fallback to the previous rough values if cost estimation fails
        state.tokens_used = (state.tokens_used or 0) + 3500
        state.cost = state.cost or 0.0

    return state
