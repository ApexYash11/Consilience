"""
LLM Call Helper - Routes LLM calls through the request queue for rate limiting

Provides a unified interface for all agents to call LLM APIs with
coordinated rate limiting and 429 handling.
"""

import asyncio
import logging
from typing import Any, Optional, TYPE_CHECKING
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage

from ..services.agent_queue_manager import get_global_request_queue

if TYPE_CHECKING:
    from .openrouter_request_queue import OpenRouterRequestQueue

logger = logging.getLogger(__name__)


async def call_llm_async(
    llm: ChatOpenAI,
    messages: list[BaseMessage],
    timeout_seconds: float = 60.0,
    agent_name: str = "unknown",
) -> Any:
    """
    Call LLM through the request queue for coordinated rate limiting.
    
    Routes all LLM calls through the global OpenRouter request queue to ensure:
    - Max concurrent calls enforced
    - Rate limit (calls/minute) enforced
    - 429 responses with Retry-After are handled
    - Exponential backoff fallback if Retry-After missing
    
    If no queue is available, falls back to direct call (backward compatible).
    
    Args:
        llm: LangChain ChatOpenAI instance
        messages: List of messages to send to LLM
        timeout_seconds: Timeout for this call in seconds
        agent_name: Name of agent making the call (for logging)
        
    Returns:
        LLM response (same as llm.ainvoke)
        
    Raises:
        asyncio.TimeoutError: If call exceeds timeout
        Exception: From the LLM
    """
    queue: Optional["OpenRouterRequestQueue"] = get_global_request_queue()  # type: ignore
    
    if queue:
        logger.debug(
            f"[{agent_name}] Routing LLM call through request queue "
            f"(timeout={timeout_seconds}s)"
        )
        
        # Create coroutine factory (not a coroutine!) for queue to execute with proper retries
        def llm_call_factory():
            """Factory that creates a fresh coroutine for each attempt."""
            return llm.ainvoke(messages)
        
        return await queue.submit(
            llm_call_factory,
            timeout_seconds=timeout_seconds,
            agent_name=agent_name,
        )
    else:
        # No queue available, call directly with timeout
        logger.debug(
            f"[{agent_name}] No request queue available; calling LLM directly "
            f"(timeout={timeout_seconds}s)"
        )
        
        try:
            async with asyncio.timeout(timeout_seconds):
                return await llm.ainvoke(messages)
        except asyncio.TimeoutError:
            logger.warning(
                f"[{agent_name}] LLM call timed out after {timeout_seconds}s"
            )
            raise


def call_llm_sync(
    llm: ChatOpenAI,
    messages: list[BaseMessage],
    agent_name: str = "unknown",
) -> Any:
    """
    Call LLM synchronously (for agents that use sync functions).
    
    Automatically runs async call in event loop.
    
    Args:
        llm: LangChain ChatOpenAI instance
        messages: List of messages to send to LLM
        agent_name: Name of agent making the call (for logging)
        
    Returns:
        LLM response
    """
    # Try to get running event loop, or create new one
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, create one
        return asyncio.run(
            call_llm_async(llm, messages, timeout_seconds=60.0, agent_name=agent_name)
        )
    else:
        # There's a running loop, but we can't use async context from sync
        # Schedule the async helper via run_coroutine_threadsafe to use the request queue
        logger.debug(f"[{agent_name}] Sync context with running loop; scheduling async call via queue")
        try:
            future = asyncio.run_coroutine_threadsafe(
                call_llm_async(llm, messages, timeout_seconds=60.0, agent_name=agent_name),
                loop
            )
            # Wait for result with timeout to enforce the same 60s bound
            return future.result(timeout=60)
        except Exception as e:
            logger.error(f"[{agent_name}] Failed to schedule async LLM call: {e}")
            raise
