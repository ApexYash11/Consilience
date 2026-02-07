import asyncio
import logging
from typing import Dict, Any, Optional, TypeVar, Callable
from uuid import UUID

from config.settings import RetryConfig as SettingsRetryConfig
from utils.retry import retry_with_backoff, RetryConfig, CircuitBreaker

logger = logging.getLogger(__name__)

StateT = TypeVar("StateT")


class BaseAgent:
    """Base class for all research agents with retry/error handling."""
    
    def __init__(
        self,
        agent_name: str,
        agent_type: str,
        retry_config: Optional[RetryConfig] = None,
    ):
        self.agent_name = agent_name
        self.agent_type = agent_type
        
        # Use provided config or create from settings
        self.retry_config = retry_config or RetryConfig(
            max_retries=getattr(SettingsRetryConfig, "MAX_RETRIES", 3),
            initial_delay_seconds=getattr(SettingsRetryConfig, "INITIAL_RETRY_DELAY_SECONDS", 1.0),
        )
        
        # Per-agent circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=getattr(SettingsRetryConfig, "CIRCUIT_BREAKER_FAILURE_THRESHOLD", 5),
            reset_timeout_seconds=getattr(SettingsRetryConfig, "CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS", 300),
        )
    
    async def call_llm_with_retry(
        self,
        llm_func: Callable,
        *args,
        timeout_seconds: float = 60.0,
        **kwargs,
    ) -> Any:
        """
        Call LLM function with timeout, retry, and circuit breaker.
        
        Usage:
            response = await agent.call_llm_with_retry(
                llm.ainvoke,
                [HumanMessage(content="prompt")],
                timeout_seconds=60.0,
            )
        """
        
        # Wrap LLM call with timeout
        async def llm_call_with_timeout():
            try:
                async with asyncio.timeout(timeout_seconds):
                    return await llm_func(*args, **kwargs)
            except asyncio.TimeoutError:
                logger.error(f"{self.agent_name} LLM call timed out after {timeout_seconds}s")
                raise
        
        # Apply retry logic
        return await retry_with_backoff(
            llm_call_with_timeout,
            config=self.retry_config,
            circuit_breaker=self.circuit_breaker,
        )
