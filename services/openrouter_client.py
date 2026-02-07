"""
OpenRouter client wrapper with fine-grained token tracking.

Wraps LangChain ChatOpenAI to extract and log individual API calls.
Enables cost breakdown per query, per model, per token type.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)


class TokenUsageTracker:
    """Track tokens used across agent calls."""
    
    def __init__(self, task_id: UUID):
        self.task_id = task_id
        self.calls: list[Dict[str, Any]] = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
    
    def record_call(
        self,
        agent_name: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost_usd: float,
        input_preview: str,
        output_preview: str,
        duration_seconds: float,
    ):
        """Record a single LLM API call with full metadata."""
        
        call_record = {
            "task_id": self.task_id,
            "agent_name": agent_name,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost_usd,
            "input_preview": input_preview[:200],  # First 200 chars
            "output_preview": output_preview[:200],
            "duration_seconds": duration_seconds,
            "timestamp": datetime.utcnow(),
        }
        
        self.calls.append(call_record)
        self.total_input_tokens += prompt_tokens
        self.total_output_tokens += completion_tokens
        self.total_cost += cost_usd
        
        logger.debug(
            f"[{agent_name}] {model}: "
            f"in={prompt_tokens} out={completion_tokens} cost=${cost_usd:.4f}"
        )
    
    def get_summary(self) -> Dict[str, Any]:
        """Return aggregated usage statistics."""
        return {
            "total_calls": len(self.calls),
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_cost_usd": self.total_cost,
            "calls_detail": self.calls,
            "avg_cost_per_call": (
                self.total_cost / len(self.calls) if self.calls else 0
            ),
        }


async def extract_token_usage(response) -> Dict[str, int]:
    """
    Extract token counts from LangChain ChatOpenAI response.
    
    Handles OpenRouter/API token data with fallback mechanisms.
    Token data sources (in priority order):
    1. response.response_metadata.get("usage") - OpenRouter usage dict
    2. response.usage_metadata - LangChain usage attribute
    3. Estimate from content length if no metadata available
    
    Returns:
        Dict with prompt_tokens, completion_tokens, total_tokens
    """
    
    # Try to get usage from response metadata (OpenRouter format)
    if hasattr(response, "response_metadata"):
        usage = response.response_metadata.get("usage", {})
        if usage:
            return {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0),
            }
    
    # Fallback: Try LangChain usage_metadata attribute
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        usage = response.usage_metadata
        return {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0),
        }
    
    # Final fallback: Estimate from content length (~4 characters per token)
    # This is approximate but better than 0 tokens
    if hasattr(response, "content") and response.content:
        output_tokens = max(1, len(str(response.content)) // 4)
        return {
            "prompt_tokens": 0,  # Can't estimate input tokens without context
            "completion_tokens": output_tokens,
            "total_tokens": output_tokens,
        }
    
    # No token data available
    logger.warning("No token usage metadata available in response; returning 0")
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }