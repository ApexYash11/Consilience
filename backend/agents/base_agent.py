import asyncio
import logging
from typing import Dict, Any, Optional, TypeVar, Callable
from uuid import UUID

from ..config.settings import RetryConfig as SettingsRetryConfig
from ..utils.retry import retry_with_backoff, RetryConfig, CircuitBreaker

logger = logging.getLogger(__name__)

StateT = TypeVar("StateT")


class BaseAgent:
    """Base class for all research agents with retry/error handling."""

    def __init__(
        self,
        agent_name: str,
        agent_type: str,
        retry_config: Optional[RetryConfig] = None,
        request_queue: Optional[Any] = None,
    ):
        self.agent_name = agent_name
        self.agent_type = agent_type
        self.request_queue = request_queue  # Optional queue for coordinating LLM calls

        # Use provided config or create from settings
        self.retry_config = retry_config or RetryConfig(
            max_retries=getattr(SettingsRetryConfig, "MAX_RETRIES", 3),
            initial_delay_seconds=getattr(
                SettingsRetryConfig, "INITIAL_RETRY_DELAY_SECONDS", 1.0
            ),
        )

        # Per-agent circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=getattr(
                SettingsRetryConfig, "CIRCUIT_BREAKER_FAILURE_THRESHOLD", 5
            ),
            reset_timeout_seconds=getattr(
                SettingsRetryConfig, "CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS", 300
            ),
        )

    def set_request_queue(self, queue: Optional[Any]) -> None:
        """Inject request queue into agent (for lazy initialization)."""
        self.request_queue = queue

    def _get_available_request_queue(self) -> Optional[Any]:
        """Get request queue from agent state or app context."""
        # First check if agent has an injected queue
        if self.request_queue:
            return self.request_queue
        
        # Try to get from FastAPI app state if available
        try:
            from fastapi import Request
            from starlette.requests import Request as StarletteRequest
            # This won't work directly in task context, but we can try app state
            # via contextvars if needed
            pass
        except Exception:
            pass
        
        return None

    async def call_llm_with_retry(
        self,
        llm_func: Callable,
        *args,
        timeout_seconds: float = 120.0,
        **kwargs,
    ) -> Any:
        """
        Call LLM function with timeout, retry, and circuit breaker.
        
        If request_queue is available, routes through the queue for coordinated
        rate limiting and concurrency control. Otherwise uses local retry logic.

        Usage:
            response = await agent.call_llm_with_retry(
                llm.ainvoke,
                [HumanMessage(content="prompt")],
                timeout_seconds=120.0,
            )
        """

        # Get available queue
        queue = self._get_available_request_queue()

        # If queue is available, route through it for coordinated rate limiting
        if queue:
            async def llm_call():
                """Create a coroutine for the queue to execute."""
                return await llm_func(*args, **kwargs)

            logger.debug(
                f"{self.agent_name} routing LLM call through request queue "
                f"(timeout={timeout_seconds}s)"
            )

            return await queue.submit(
                llm_call,
                timeout_seconds=timeout_seconds,
                agent_name=self.agent_name,
            )

        # Fallback: use timeout + retry + circuit breaker (backward compatibility)
        # Wrap LLM call with retry and circuit breaker for resilience
        async def llm_call_with_timeout():
            try:
                # Apply circuit breaker + retry wrapper for consistency with queue path
                return await retry_with_backoff(
                    lambda: llm_func(*args, **kwargs),
                    config=self.retry_config,
                    circuit_breaker=self.circuit_breaker,
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"{self.agent_name} LLM call timed out after {timeout_seconds}s"
                )
                raise

        # Apply retry logic
        return await retry_with_backoff(
            llm_call_with_timeout,
            config=self.retry_config,
            circuit_breaker=self.circuit_breaker,
        )
