"""
Retry utilities with exponential backoff, jitter, and circuit breaker.
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Callable, TypeVar, Any, Optional
from dataclasses import dataclass, field
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    backoff_multiplier: float = 2.0
    jitter_enabled: bool = True


@dataclass
class CircuitBreaker:
    """Prevent cascading failures by stopping retries after repeated errors."""
    failure_threshold: int = 5
    reset_timeout_seconds: int = 300
    
    failure_count: int = field(default=0)
    last_failure_time: Optional[datetime] = field(default=None)
    is_open: bool = field(default=False)
    
    def record_failure(self):
        """Record a failure; open circuit if threshold exceeded."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)
        
        if self.failure_count >= self.failure_threshold:
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures. "
                f"Circuit will reset in {self.reset_timeout_seconds}s."
            )
            self.is_open = True
    
    def record_success(self):
        """Reset circuit on success."""
        self.failure_count = 0
        self.is_open = False
    
    def should_allow_request(self) -> bool:
        """Check if circuit should allow requests."""
        if not self.is_open:
            return True
        
        # Check if enough time has passed to reset
        if self.last_failure_time:
            elapsed = (datetime.now(timezone.utc) - self.last_failure_time).total_seconds()
            if elapsed > self.reset_timeout_seconds:
                logger.info("Circuit breaker resetting.")
                self.is_open = False
                self.failure_count = 0
                return True
        
        return False


async def retry_with_backoff(
    func: Callable[..., Any],
    *args,
    config: RetryConfig = RetryConfig(),
    circuit_breaker: Optional[CircuitBreaker] = None,
    **kwargs,
) -> Any:
    """
    Retry async function with exponential backoff and jitter.
    
    Args:
        func: Async function to call
        config: Retry configuration
        circuit_breaker: Optional circuit breaker to check/update
        
    Returns:
        Result of func() if successful
        
    Raises:
        Last exception if all retries exhausted
    """
    
    last_exception: Optional[Exception] = None
    
    for attempt in range(config.max_retries + 1):
        # Check circuit breaker
        if circuit_breaker and not circuit_breaker.should_allow_request():
            logger.error("Circuit breaker is OPEN; skipping request")
            raise RuntimeError("Circuit breaker open; service unavailable")
        
        try:
            result = await func(*args, **kwargs)
            
            # Success; reset circuit breaker
            if circuit_breaker:
                circuit_breaker.record_success()
            
            return result
            
        except asyncio.TimeoutError as e:
            last_exception = e
            logger.warning(f"Request timed out (attempt {attempt + 1}/{config.max_retries + 1})")
            
            if circuit_breaker:
                circuit_breaker.record_failure()
            
            if attempt < config.max_retries:
                delay = _calculate_delay(attempt, config)
                logger.info(f"Retrying after {delay:.2f} seconds...")
                await asyncio.sleep(delay)
            
        except Exception as e:
            # Other exceptions (don't retry on bad requests, auth errors, etc.)
            if "401" in str(e) or "403" in str(e) or "BadRequest" in str(type(e).__name__):
                logger.error(f"Non-retryable error: {str(e)}")
                raise e
            
            last_exception = e
            logger.warning(f"Request failed: {str(e)} (attempt {attempt + 1}/{config.max_retries + 1})")
            
            if circuit_breaker:
                circuit_breaker.record_failure()
            
            if attempt < config.max_retries:
                delay = _calculate_delay(attempt, config)
                logger.info(f"Retrying after {delay:.2f} seconds...")
                await asyncio.sleep(delay)
    
    logger.error(f"All {config.max_retries + 1} attempts exhausted")
    if last_exception is not None:
        raise last_exception
    raise RuntimeError("All retry attempts failed")


def _calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay with exponential backoff and optional jitter."""
    
    # Exponential backoff: 1, 2, 4, 8, ...
    delay = config.initial_delay_seconds * (config.backoff_multiplier ** attempt)
    
    # Cap at maximum
    delay = min(delay, config.max_delay_seconds)
    
    # Add jitter: random ±20% of delay
    if config.jitter_enabled:
        jitter = delay * 0.2 * random.uniform(-1, 1)
        delay += jitter
    
    return max(delay, 0)  # Ensure non-negative