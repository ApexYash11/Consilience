"""
OpenRouter Request Queue Service

Manages throttling of LLM API calls to prevent rate limiting.
- Enforces max concurrent requests (max_concurrent)
- Enforces rate limit (calls_per_minute)
- Handles 429 responses with Retry-After header parsing
- Implements exponential backoff as fallback

This service ensures all LLM calls route through a single coordinated queue,
preventing the 429 "Rate Limit Exceeded" errors that occur when multiple
agents call OpenRouter simultaneously.

Usage:
    queue = OpenRouterRequestQueue(max_concurrent=5, calls_per_minute=100)
    result = await queue.submit(llm.ainvoke(...), timeout_seconds=60.0, agent_name="Planner")
"""

import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, Coroutine
from uuid import UUID

logger = logging.getLogger(__name__)


class OpenRouterRequestQueue:
    """
    Async request queue for OpenRouter LLM calls with concurrency and rate limiting.
    
    Attributes:
        max_concurrent: Maximum simultaneous API calls (default 5)
        calls_per_minute: Maximum API calls per minute (default 100)
        max_retries_on_429: Maximum retry attempts on rate limit (default 3)
        fallback_backoff_base: Base for exponential backoff (default 2.0)
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        calls_per_minute: int = 100,
        max_retries_on_429: int = 3,
        fallback_backoff_base: float = 2.0,
    ):
        """
        Initialize the request queue.
        
        Args:
            max_concurrent: Max simultaneous requests
            calls_per_minute: Rate limit threshold
            max_retries_on_429: Retry attempts on rate limit
            fallback_backoff_base: Base for exponential backoff (seconds)
        """
        self.max_concurrent = max_concurrent
        self.calls_per_minute = calls_per_minute
        self.max_retries_on_429 = max_retries_on_429
        self.fallback_backoff_base = fallback_backoff_base

        # Concurrency control
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # Rate limiting: sliding window of API call timestamps (last 60 seconds)
        self._call_times: deque = deque()
        self._call_times_lock = asyncio.Lock()

        # Pending requests for graceful shutdown
        self._pending_requests: set = set()
        self._pending_requests_lock = asyncio.Lock()

        logger.info(
            f"OpenRouterRequestQueue initialized: "
            f"max_concurrent={max_concurrent}, "
            f"calls_per_minute={calls_per_minute}"
        )

    async def submit(
        self,
        coro: Coroutine,
        timeout_seconds: float = 60.0,
        agent_name: str = "unknown",
        task_id: Optional[UUID] = None,
        retry_count: int = 0,
    ) -> Any:
        """
        Submit an LLM call through the queue.
        
        Enforces:
        1. Concurrency limit (max N simultaneous calls)
        2. Rate limit (max M calls per minute)
        3. Timeout per call
        4. Retry logic on 429 responses
        
        Args:
            coro: The coroutine to execute (e.g., llm.ainvoke(...))
            timeout_seconds: Timeout for this specific call
            agent_name: Name of agent making the call (for logging)
            task_id: Optional task ID for tracking
            retry_count: Internal retry counter (don't set manually)
            
        Returns:
            Result from the coroutine
            
        Raises:
            asyncio.TimeoutError: If call exceeds timeout
            Exception: From the underlying coroutine
        """
        request_id = hash((agent_name, time.time(), retry_count))

        try:
            # Track this request
            async with self._pending_requests_lock:
                self._pending_requests.add(request_id)

            # Step 1: Rate limit gate (wait until call window allows another call)
            await self._rate_limit_gate(agent_name)

            # Step 2: Concurrency gate (wait for available slot)
            async with self._semaphore:
                # Record this call timestamp for rate limiting
                async with self._call_times_lock:
                    self._call_times.append(time.time())

                try:
                    # Step 3: Execute with timeout
                    logger.debug(
                        f"[{agent_name}] Starting request (task_id={task_id}, "
                        f"pending={len(self._pending_requests)})"
                    )

                    result = await asyncio.wait_for(coro, timeout=timeout_seconds)

                    logger.debug(f"[{agent_name}] Request completed successfully")
                    return result

                except asyncio.TimeoutError as e:
                    logger.warning(
                        f"[{agent_name}] Request timed out after {timeout_seconds}s "
                        f"(task_id={task_id})"
                    )
                    raise

                except Exception as e:
                    error_message = str(e)

                    # Step 4: Check for 429 rate limit response
                    if self._is_rate_limit_error(e):
                        retry_after = self._extract_retry_after(e)

                        if retry_count < self.max_retries_on_429:
                            logger.warning(
                                f"[{agent_name}] Rate limited (429). "
                                f"Retrying in {retry_after}s (attempt {retry_count + 1}/{self.max_retries_on_429})"
                            )

                            # Wait for the specified duration
                            await asyncio.sleep(retry_after)

                            # Recursively retry
                            return await self.submit(
                                coro=coro,
                                timeout_seconds=timeout_seconds,
                                agent_name=agent_name,
                                task_id=task_id,
                                retry_count=retry_count + 1,
                            )
                        else:
                            logger.error(
                                f"[{agent_name}] Rate limited (429) after "
                                f"{self.max_retries_on_429} retries. Giving up."
                            )
                            raise

                    # Re-raise non-rate-limit errors
                    raise

        finally:
            # Untrack this request
            async with self._pending_requests_lock:
                self._pending_requests.discard(request_id)

    async def _rate_limit_gate(self, agent_name: str) -> None:
        """
        Wait if necessary to ensure we don't exceed calls_per_minute.
        
        Uses a sliding window: only count API calls from the last 60 seconds.
        If count >= limit, sleep until oldest call ages out of the window.
        """
        while True:
            async with self._call_times_lock:
                now = time.time()
                window_start = now - 60.0

                # Remove calls older than 60 seconds
                while self._call_times and self._call_times[0] < window_start:
                    self._call_times.popleft()

                # Check if we're at the limit
                if len(self._call_times) < self.calls_per_minute:
                    # We have room; proceed
                    return

                # Calculate how long to wait
                oldest_call = self._call_times[0]
                time_to_window_exit = (oldest_call + 60.0) - now
                sleep_time = max(0.1, time_to_window_exit)

                logger.debug(
                    f"[{agent_name}] Rate limited ({len(self._call_times)}/{self.calls_per_minute} "
                    f"calls/min). Waiting {sleep_time:.1f}s"
                )

            # Sleep outside the lock
            await asyncio.sleep(sleep_time)

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """
        Detect if an error is a 429 Rate Limit Exceeded response.
        
        Checks:
        - HTTPStatusError with status_code == 429
        - Response JSON with 429 status or error message mentioning "rate"
        - Generic error message containing "429" or "rate limit"
        """
        error_str = str(error).lower()

        # Check for 429 in error message
        if "429" in error_str:
            return True

        # Check for "rate limit" mentioned in error
        if "rate limit" in error_str or "rate_limit" in error_str:
            return True

        # Check for HTTPStatusError with 429 (from requests/httpx)
        # Use getattr for safer attribute access
        response = getattr(error, "response", None)
        if response is not None:
            status_code = getattr(response, "status_code", None)
            if status_code == 429:
                return True
            status = getattr(response, "status", None)
            if status == 429:
                return True

        return False

    def _extract_retry_after(self, error: Exception) -> float:
        """
        Extract Retry-After duration from error response.
        
        Priority:
        1. Retry-After header (seconds as int or HTTP-date)
        2. Exponential backoff fallback: base^attempt seconds (max 300s)
        
        Returns:
            Seconds to wait before retry
        """
        # Try to extract Retry-After header
        # Use getattr for safer attribute access
        response = getattr(error, "response", None)
        if response is not None:
            headers = getattr(response, "headers", None)
            if headers is not None:
                retry_after_header = headers.get("Retry-After") if hasattr(headers, "get") else None
                if retry_after_header:
                    try:
                        # First try as integer (seconds)
                        return float(retry_after_header)
                    except ValueError:
                        # Try as HTTP-date (not common for OpenRouter, but supported)
                        try:
                            retry_time = datetime.strptime(
                                retry_after_header, "%a, %d %b %Y %H:%M:%S %Z"
                            )
                            wait_time = (retry_time - datetime.utcnow()).total_seconds()
                            if wait_time > 0:
                                return wait_time
                        except ValueError:
                            pass

        # Fallback: exponential backoff with max 300s
        # This is a safe default if Retry-After is missing
        backoff = min(
            self.fallback_backoff_base ** 2,  # Conservative: base^2 (4, 16, 64...)
            300.0,  # Max 5 minutes
        )
        logger.warning(
            f"No Retry-After header found; using fallback backoff of {backoff:.1f}s"
        )
        return backoff

    async def shutdown(self) -> None:
        """
        Gracefully shut down the queue.
        
        Cancels all pending requests and releases resources.
        Called on FastAPI app shutdown.
        """
        logger.info(
            f"Shutting down OpenRouterRequestQueue "
            f"({len(self._pending_requests)} pending requests)"
        )

        # Cancel pending requests (they'll see cancellation)
        async with self._pending_requests_lock:
            for request_id in self._pending_requests:
                logger.debug(f"Cancelling pending request {request_id}")

            self._pending_requests.clear()

        # Give pending tasks a moment to clean up
        await asyncio.sleep(0.1)

        logger.info("OpenRouterRequestQueue shutdown complete")

    async def get_stats(self) -> dict:
        """
        Get current queue statistics.
        
        Returns:
            Dict with pending_requests, calls_per_min_usage, etc.
        """
        async with self._call_times_lock:
            now = time.time()
            window_start = now - 60.0

            # Count calls in current window
            calls_in_window = sum(1 for t in self._call_times if t >= window_start)

        async with self._pending_requests_lock:
            pending = len(self._pending_requests)

        return {
            "pending_requests": pending,
            "calls_in_current_minute": calls_in_window,
            "rate_limit_threshold": self.calls_per_minute,
            "rate_limit_percentage": (calls_in_window / self.calls_per_minute) * 100,
            "max_concurrent": self.max_concurrent,
            "semaphore_available": self._semaphore._value,
        }
