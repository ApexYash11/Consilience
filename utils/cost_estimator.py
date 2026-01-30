"""
Cost estimator for OpenRouter API calls.

Tracks token usage and calculates costs based on model pricing.
Integrates with Consilience's billing system.
"""

from typing import Dict, Any, Optional
from config.models import PRICING, get_model_pricing
import logging

logger = logging.getLogger(__name__)


def estimate_cost_from_response(
    response: Any,
    model: str,
) -> Dict[str, Any]:
    """
    Estimate cost from LLM response.

    Args:
        response: LangChain response object with usage info
        model: Model identifier string

    Returns:
        Dictionary with:
            - input_tokens: Number of input tokens
            - output_tokens: Number of output tokens
            - total_tokens: Sum of input + output
            - cost: Cost in USD
            - model: Model used
    """
    try:
        # Try to get usage info from response
        if hasattr(response, "response_metadata"):
            usage = response.response_metadata.get("usage", {})
        elif hasattr(response, "usage_metadata"):
            usage = response.usage_metadata
        else:
            # Estimate based on content length
            import tiktoken

            try:
                encoding = tiktoken.get_encoding("cl100k_base")
                # Response.content is the model output; treat it as completion/output tokens
                output_tokens = len(encoding.encode(str(getattr(response, "content", ""))))
                input_tokens = 0
            except Exception:
                # Rough estimate: ~4 chars per token for output
                output_tokens = len(str(getattr(response, "content", ""))) // 4
                input_tokens = 0

            usage = {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
            }

        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = input_tokens + output_tokens

        # Get pricing for model
        pricing = get_model_pricing(model)

        # Calculate cost
        input_cost = (input_tokens * pricing["input"]) / 1_000_000
        output_cost = (output_tokens * pricing["output"]) / 1_000_000
        total_cost = input_cost + output_cost

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "cost": round(total_cost, 6),
            "model": model,
        }

    except Exception as e:
        logger.warning(f"Failed to calculate cost: {str(e)}")
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "input_cost": 0.0,
            "output_cost": 0.0,
            "cost": 0.0,
            "model": model,
        }


def estimate_cost_from_tokens(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """
    Estimate cost from token counts.

    Args:
        model: Model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD
    """
    pricing = get_model_pricing(model)
    input_cost = (input_tokens * pricing["input"]) / 1_000_000
    output_cost = (output_tokens * pricing["output"]) / 1_000_000
    return round(input_cost + output_cost, 6)


def estimate_research_cost(
    research_mode: str,
    num_sources: int = 15,
    include_thinking: bool = False,
) -> Dict[str, Any]:
    """
    Estimate total cost for a research task.

    Args:
        research_mode: "standard" or "deep"
        num_sources: Expected number of sources (affects token count)
        include_thinking: Whether to include thinking mode tokens (deep research)

    Returns:
        Cost breakdown by phase
    """
    cost_breakdown = {}
    total_cost = 0.0

    if research_mode == "standard":
        # Free tier - all costs are zero
        phases = {
            "planning": 2000,  # tokens
            "research": 5000 * 5,  # 5 researchers
            "verification": 3000,
            "detection": 2500,
            "synthesis": 8000,
            "review": 2000,
            "revision": 3000,
            "formatting": 1000,
        }

        for phase, tokens in phases.items():
            cost_breakdown[phase] = 0.0  # All free models

    else:  # deep research with Kimi K2.5
        from config.models import DEEP_MODELS

        model = DEEP_MODELS["planning"]  # All phases use same model
        pricing = get_model_pricing(model)

        # Token estimates for deep research
        phases = {
            "planning": 5000,
            "research": 50000,
            "verification": 20000,
            "detection": 15000,
            "synthesis": 30000,  # Output intensive
            "review": 20000,
            "revision": 30000,
            "formatting": 10000,
        }

        if include_thinking:
            # Thinking mode adds ~50k tokens
            phases["thinking"] = 50000

        for phase, input_tokens in phases.items():
            output_tokens = int(input_tokens * 1.5)  # Estimate output as 1.5x input
            phase_cost = estimate_cost_from_tokens(model, input_tokens, output_tokens)
            cost_breakdown[phase] = phase_cost
            total_cost += phase_cost

    cost_breakdown["total"] = total_cost

    return cost_breakdown


def format_cost_summary(cost_info: Dict[str, Any]) -> str:
    """
    Format cost information for display.

    Args:
        cost_info: Cost dictionary from estimate functions

    Returns:
        Formatted string for display/logging
    """
    if "total" in cost_info:
        # From estimate_research_cost
        summary = f"Research Cost Summary\n"
        summary += f"{'Phase':<15} {'Cost':>10}\n"
        summary += "-" * 25 + "\n"
        for phase, cost in cost_info.items():
            if phase != "total":
                summary += f"{phase:<15} ${cost:>9.4f}\n"
        summary += "-" * 25 + "\n"
        summary += f"{'TOTAL':<15} ${cost_info['total']:>9.4f}\n"
    else:
        # From estimate_cost_from_response
        summary = f"Cost Breakdown\n"
        summary += f"Model: {cost_info.get('model', 'Unknown')}\n"
        summary += f"Input tokens: {cost_info.get('input_tokens', 0)}\n"
        summary += f"Output tokens: {cost_info.get('output_tokens', 0)}\n"
        summary += f"Total tokens: {cost_info.get('total_tokens', 0)}\n"
        summary += f"Total cost: ${cost_info.get('cost', 0):.6f}\n"

    return summary


# Standard research cost estimates
STANDARD_RESEARCH_COST = 0.0  # All free models

# Deep research cost estimates
DEEP_RESEARCH_COST_MIN = 0.25  # Without thinking
DEEP_RESEARCH_COST_MAX = 0.50  # With thinking mode

# Cost thresholds for alerts
COST_WARNING_THRESHOLD = 5.0  # Alert if cost > $5
COST_ERROR_THRESHOLD = 50.0  # Error if cost > $50
