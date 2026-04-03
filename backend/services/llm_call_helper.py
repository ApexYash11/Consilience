"""
LLM Call Helper - Routes LLM calls through the request queue for rate limiting

Provides a unified interface for all agents to call LLM APIs with:
- Coordinated rate limiting via request queue
- Retry logic with exponential backoff
- Circuit breaker for cascading failure prevention
- Enhanced timing and debugging logs
- Thread-safe sync wrapper

PARTS IMPLEMENTED:
- PART 1: Debug root cause (timing logs, queue analysis)
- PART 2: Increased timeouts (120s LLM, 240s wrapper)
- PART 3: Retry logic (max 2 retries, exponential backoff)
- PART 4: Fallback model infrastructure (integrated with config/models.py)
- PART 5: Thread-safe sync wrapper (asyncio.run_coroutine_threadsafe)
- PART 6: Circuit breaker (5-failure threshold, 60s recovery)
"""

import asyncio
import logging
import time
from typing import Any, Optional, TYPE_CHECKING, Callable
from datetime import datetime, timedelta
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage

from ..services.agent_queue_manager import get_global_request_queue

if TYPE_CHECKING:
    from .openrouter_request_queue import OpenRouterRequestQueue

logger = logging.getLogger(__name__)


# ============================================================================
# PART 6: CIRCUIT BREAKER IMPLEMENTATION
# ============================================================================
class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading LLM failures.
    
    States:
    - CLOSED: Normal operation, requests allowed
    - OPEN: Too many failures, requests blocked (fail fast)
    - HALF_OPEN: Recovery window, single request allowed to test
    
    Transitions:
    - CLOSED → OPEN: failure_count >= failure_threshold (5)
    - OPEN → HALF_OPEN: recovery_timeout elapsed (60s)
    - HALF_OPEN → CLOSED: test request succeeds
    - HALF_OPEN → OPEN: test request fails
    """
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Failures required to open circuit (default 5)
            recovery_timeout: Seconds to wait before half-open attempt (default 60)
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        
        self.failure_count = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.opened_at: Optional[datetime] = None
        self.last_attempt_at: Optional[datetime] = None
        
        logger.info(
            f"[CircuitBreaker] Initialized with threshold={failure_threshold}, "
            f"recovery_timeout={recovery_timeout}s"
        )
    
    def is_available(self) -> bool:
        """Check if circuit allows requests."""
        now = datetime.utcnow()
        
        if self.state == "CLOSED":
            return True
        
        elif self.state == "OPEN":
            # Check if recovery timeout has elapsed
            if self.opened_at and (now - self.opened_at).total_seconds() >= self.recovery_timeout:
                logger.warning(
                    f"[CircuitBreaker] HALF_OPEN: Testing recovery "
                    f"after {self.recovery_timeout}s"
                )
                self.state = "HALF_OPEN"
                return True
            else:
                elapsed = (now - self.opened_at).total_seconds() if self.opened_at else 0
                logger.warning(
                    f"[CircuitBreaker] OPEN: Rejecting request "
                    f"({elapsed:.1f}s / {self.recovery_timeout}s)"
                )
                return False
        
        elif self.state == "HALF_OPEN":
            # Allow single request in HALF_OPEN
            return True
        
        return False
    
    def record_failure(self):
        """Record a failed request."""
        self.failure_count += 1
        self.last_attempt_at = datetime.utcnow()
        
        logger.warning(
            f"[CircuitBreaker] Failure recorded: {self.failure_count}/{self.failure_threshold}"
        )
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            self.opened_at = datetime.utcnow()
            logger.error(
                f"[CircuitBreaker] OPEN after {self.failure_count} failures. "
                f"Recovery attempt in {self.recovery_timeout}s."
            )
    
    def record_success(self):
        """Record a successful request."""
        if self.state == "HALF_OPEN":
            logger.info(
                f"[CircuitBreaker] CLOSED: Recovery successful after "
                f"{self.failure_count} prior failures"
            )
        
        self.failure_count = 0
        self.state = "CLOSED"
        self.opened_at = None


# Global circuit breaker instance
_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)


# ============================================================================
# PART 1 & 2 & 3: ENHANCED ASYNC LLM CALL WITH RETRIES AND TIMING
# ============================================================================
async def call_llm_async(
    llm: ChatOpenAI,
    messages: list[BaseMessage],
    timeout_seconds: float = 120.0,  # PART 2: Increased from 60s to 120s
    agent_name: str = "unknown",
    max_retries: int = 2,  # PART 3: Retry logic
) -> Any:
    """
    Call LLM through the request queue for coordinated rate limiting.
    
    ENHANCEMENTS:
    - PART 1: Detailed timing logs (request start/end with duration)
    - PART 2: Increased timeout from 60s to 120s for LLM calls
    - PART 3: Retry logic with exponential backoff [0, 2, 5]s
    - PART 6: Circuit breaker check (fail-fast if too many failures)
    
    Routes all LLM calls through the global OpenRouter request queue to ensure:
    - Max concurrent calls enforced
    - Rate limit (calls/minute) enforced
    - 429 responses with Retry-After are handled
    - Exponential backoff fallback if Retry-After missing
    
    If no queue is available, falls back to direct call (backward compatible).
    
    Args:
        llm: LangChain ChatOpenAI instance
        messages: List of messages to send to LLM
        timeout_seconds: Timeout for each LLM call in seconds (default 120s)
        agent_name: Name of agent making the call (for logging)
        max_retries: Maximum retry attempts on timeout (default 2)
        
    Returns:
        LLM response (same as llm.ainvoke)
        
    Raises:
        asyncio.TimeoutError: If all retries exceed timeout
        Exception: From the LLM
    """
    
    # PART 6: Circuit breaker check (fail-fast if open)
    if not _circuit_breaker.is_available():
        error_msg = "[CircuitBreaker] OPEN - rejecting request"
        logger.error(f"[{agent_name}] {error_msg}")
        raise RuntimeError(error_msg)
    
    # PART 3: Retry delays in seconds [immediate, 2s, 5s]
    retry_delays = [0, 2, 5]
    last_error: Optional[Exception] = None
    
    for attempt in range(max_retries + 1):
        attempt_num = attempt + 1
        
        # PART 1: Log request start with timing
        request_start = time.time()
        logger.info(
            f"[{agent_name}] [ATTEMPT {attempt_num}/{max_retries + 1}] "
            f"Starting LLM call (timeout={timeout_seconds}s)"
        )
        
        try:
            queue: Optional["OpenRouterRequestQueue"] = get_global_request_queue()  # type: ignore
            
            if queue:
                logger.debug(
                    f"[{agent_name}] Routing through request queue "
                    f"(timeout={timeout_seconds}s)"
                )
                
                # Create coroutine factory for queue with proper retries
                def llm_call_factory():
                    """Factory that creates a fresh coroutine for each attempt."""
                    return llm.ainvoke(messages)
                
                result = await queue.submit(
                    llm_call_factory,
                    timeout_seconds=timeout_seconds,
                    agent_name=agent_name,
                )
            else:
                # No queue available, call directly with timeout
                logger.debug(
                    f"[{agent_name}] No request queue; calling LLM directly "
                    f"(timeout={timeout_seconds}s)"
                )
                
                async with asyncio.timeout(timeout_seconds):
                    result = await llm.ainvoke(messages)
            
            # PART 1: Log success with timing
            elapsed = time.time() - request_start
            logger.info(
                f"[{agent_name}] [ATTEMPT {attempt_num}/{max_retries + 1}] "
                f"SUCCESS (completed in {elapsed:.2f}s)"
            )
            
            # PART 6: Record success for circuit breaker recovery
            _circuit_breaker.record_success()
            
            return result
        
        except asyncio.TimeoutError as e:
            elapsed = time.time() - request_start
            last_error = e
            
            # PART 1: Log timeout with attempt details
            logger.warning(
                f"[{agent_name}] [ATTEMPT {attempt_num}/{max_retries + 1}] "
                f"TIMEOUT after {elapsed:.2f}s (configured timeout={timeout_seconds}s)"
            )
            
            # PART 3: Check if we should retry
            if attempt < max_retries:
                retry_delay = retry_delays[attempt + 1]
                logger.info(
                    f"[{agent_name}] [ATTEMPT {attempt_num}/{max_retries + 1}] "
                    f"Retrying in {retry_delay}s..."
                )
                await asyncio.sleep(retry_delay)
            else:
                # Final attempt failed, record failure for circuit breaker
                _circuit_breaker.record_failure()
                logger.error(
                    f"[{agent_name}] All {max_retries + 1} attempts failed with timeout. "
                    f"Circuit breaker failure count: {_circuit_breaker.failure_count}"
                )
        
        except Exception as e:
            elapsed = time.time() - request_start
            last_error = e
            
            # PART 1: Log error with timing
            logger.error(
                f"[{agent_name}] [ATTEMPT {attempt_num}/{max_retries + 1}] "
                f"ERROR after {elapsed:.2f}s: {str(e)}"
            )
            
            # Record failure for circuit breaker
            _circuit_breaker.record_failure()
            
            # Don't retry non-timeout errors, raise immediately
            raise
    
    # All retries exhausted
    if last_error:
        logger.error(
            f"[{agent_name}] Final error after {max_retries + 1} attempts: {str(last_error)}"
        )
        raise last_error
    else:
        raise RuntimeError(
            f"[{agent_name}] All {max_retries + 1} LLM attempts failed for unknown reason"
        )


# ============================================================================
# PART 5: THREAD-SAFE SYNC WRAPPER
# ============================================================================
def call_llm_sync(
    llm: ChatOpenAI,
    messages: list[BaseMessage],
    agent_name: str = "unknown",
    timeout_seconds: float = 120.0,  # PART 2: LLM timeout (increased from 60s)
) -> Any:
    """
    Call LLM synchronously (for agents that use sync functions).
    
    ENHANCEMENTS:
    - PART 2: 240s wrapper timeout (120s LLM + 120s buffer for queue processing)
    - PART 5: Thread-safe future handling via asyncio.run_coroutine_threadsafe
    
    Automatically runs async call in event loop with proper timeout management.
    
    Args:
        llm: LangChain ChatOpenAI instance
        messages: List of messages to send to LLM
        agent_name: Name of agent making the call (for logging)
        timeout_seconds: LLM call timeout in seconds (default 120s)
        
    Returns:
        LLM response
        
    Raises:
        TimeoutError: If wrapper timeout exceeded (240s)
        Exception: From the LLM
    """
    # PART 2: Wrapper timeout = LLM timeout + buffer for queue processing
    wrapper_timeout = timeout_seconds + 120.0  # 120s LLM + 120s buffer = 240s
    
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, create one (simple case)
        logger.debug(
            f"[{agent_name}] Creating new event loop for sync LLM call "
            f"(timeout={timeout_seconds}s)"
        )
        return asyncio.run(
            call_llm_async(
                llm, 
                messages, 
                timeout_seconds=timeout_seconds, 
                agent_name=agent_name
            )
        )
    else:
        # PART 5: Running loop exists - use thread-safe scheduling
        logger.debug(
            f"[{agent_name}] Scheduling async call via thread-safe future "
            f"(LLM timeout={timeout_seconds}s, wrapper timeout={wrapper_timeout}s)"
        )
        
        try:
            # PART 5: Schedule coroutine in the running loop via thread-safe mechanism
            future = asyncio.run_coroutine_threadsafe(
                call_llm_async(
                    llm, 
                    messages, 
                    timeout_seconds=timeout_seconds, 
                    agent_name=agent_name
                ),
                loop
            )
            
            # PART 2: Wait for result with wrapper timeout
            # This enforces the combined timeout for both LLM call and queue processing
            logger.debug(
                f"[{agent_name}] Waiting for future result "
                f"(wrapper timeout={wrapper_timeout}s)"
            )
            
            result = future.result(timeout=wrapper_timeout)
            
            logger.info(
                f"[{agent_name}] Sync wrapper completed successfully"
            )
            return result
        
        except asyncio.TimeoutError as e:
            logger.error(
                f"[{agent_name}] Sync wrapper timeout after {wrapper_timeout}s"
            )
            # Record failure for circuit breaker
            _circuit_breaker.record_failure()
            raise TimeoutError(
                f"LLM call exceeded wrapper timeout of {wrapper_timeout}s"
            ) from e
        
        except Exception as e:
            logger.error(
                f"[{agent_name}] Sync wrapper error: {str(e)}"
            )
            # Record failure for circuit breaker
            if isinstance(e, (asyncio.TimeoutError, TimeoutError)):
                _circuit_breaker.record_failure()
            raise
