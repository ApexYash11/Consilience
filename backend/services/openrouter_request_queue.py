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
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class RateLimitedError(Exception):
    """Exception raised when API rate limit is exceeded."""
    def __init__(self, message: str, http_status: int = 429, error_code: str = "RATE_LIMIT"):
        super().__init__(message)
        self.http_status = http_status
        self.error_code = error_code


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
        
        # Track asyncio.Tasks for proper cancellation on shutdown
        self._pending_tasks: dict = {}  # request_id -> asyncio.Task

        logger.info(
            f"OpenRouterRequestQueue initialized: "
            f"max_concurrent={max_concurrent}, "
            f"calls_per_minute={calls_per_minute}"
        )

    async def submit(
        self,
        coro_factory: Callable[[], Coroutine],
        timeout_seconds: float = 60.0,
        agent_name: str = "unknown",
    ) -> Any:
        """
        Submit a coroutine factory to the queue for execution with rate limiting and retry.
        
        The coroutine factory is called to create a fresh coroutine for each attempt,
        allowing proper retries on 429 rate limit errors.
        
        Enforces:
        1. Concurrency limit (max N simultaneous calls)
        2. Rate limit (max M calls per minute)
        3. Timeout per call
        4. Retry logic on 429 responses with fresh coroutine per attempt
        
        Args:
            coro_factory: Callable that returns a fresh coroutine (not a coroutine object!)
                         Use: queue.submit(lambda: llm.ainvoke(...), ...)
                         NOT:  queue.submit(llm.ainvoke(...), ...)
            timeout_seconds: Timeout for each attempt in seconds
            agent_name: Name of agent making the call (for logging)
            
        Returns:
            Result from the coroutine
            
        Raises:
            asyncio.TimeoutError: If call exceeds timeout
            Exception: From the underlying coroutine
        """
        task_id = uuid4()
        retry_count = 0
        
        while retry_count <= self.max_retries_on_429:
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
                        # Step 3: Execute with timeout (wrap in task for proper cancellation)
                        logger.debug(
                            f"[{agent_name}] Starting request (task_id={task_id}, "
                            f"pending={len(self._pending_requests)})"
                        )

                        # Create task inside lock to eliminate race condition
                        # Create a FRESH coroutine from the factory for each attempt
                        coro = coro_factory()
                        async with self._pending_requests_lock:
                            current_task = asyncio.create_task(coro)
                            self._pending_tasks[request_id] = current_task
                        
                        try:
                            result = await asyncio.wait_for(current_task, timeout=timeout_seconds)
                            logger.debug(f"[{agent_name}] Request completed successfully")
                            return result
                        finally:
                            async with self._pending_requests_lock:
                                self._pending_tasks.pop(request_id, None)

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
                            retry_after = self._extract_retry_after(e, retry_count)

                            if retry_count < self.max_retries_on_429:
                                logger.warning(
                                    f"[{agent_name}] Rate limited (429). "
                                    f"Retrying in {retry_after}s (attempt {retry_count + 1}/{self.max_retries_on_429})"
                                )

                                # Wait for the specified duration
                                await asyncio.sleep(retry_after)
                                
                                # Increment retry count and loop to create a FRESH coroutine
                                retry_count += 1
                                # Untrack and continue to next attempt
                                async with self._pending_requests_lock:
                                    self._pending_requests.discard(request_id)
                                continue
                            else:
                                logger.error(
                                    f"[{agent_name}] Rate limited (429) after "
                                    f"{self.max_retries_on_429} retries. Giving up."
                                )
                                
                                # PHASE 4: Raise error with error code and HTTP status
                                raise RateLimitedError(
                                    message=f"Rate limited after {self.max_retries_on_429} retries: {error_message}",
                                    http_status=429,
                                    error_code="RATE_LIMIT",
                                )

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

    def _extract_retry_after(self, error: Exception, retry_count: int = 0) -> float:
        """
        Extract Retry-After duration from error response.
        
        Priority:
        1. Retry-After header (seconds as int or HTTP-date)
        2. Exponential backoff fallback: base^attempt seconds (max 300s)
        
        Args:
            error: The exception/error response
            retry_count: Current retry attempt number for backoff calculation
            
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
                        # Try as HTTP-date using email.utils for reliable parsing
                        try:
                            from email.utils import parsedate_to_datetime
                            from datetime import timezone
                            
                            parsed_dt = parsedate_to_datetime(retry_after_header)
                            wait_time = (parsed_dt - datetime.now(timezone.utc)).total_seconds()
                            if wait_time > 0:
                                return wait_time
                        except (ValueError, TypeError):
                            pass

        # Fallback: exponential backoff with max 300s
        # This is a safe default if Retry-After is missing
        backoff = min(
            self.fallback_backoff_base ** retry_count,  # Exponential: base^retry_count
            300.0,  # Max 5 minutes
        )
        logger.warning(
            f"No Retry-After header found; using fallback backoff of {backoff:.1f}s"
        )
        return backoff

    async def shutdown(self) -> None:
        """
        Gracefully shut down the queue.
        
        Cancels all pending requests/tasks and awaits their cleanup.
        Called on FastAPI app shutdown.
        """
        logger.info(
            f"Shutting down OpenRouterRequestQueue "
            f"({len(self._pending_requests)} pending requests)"
        )

        # Cancel pending tasks with proper cleanup (inside critical section)
        cancelled_tasks = []
        async with self._pending_requests_lock:
            pending_ids = list(self._pending_requests)
            for request_id in pending_ids:
                logger.debug(f"Cancelling pending request {request_id}")
                self._pending_requests.discard(request_id)
                
                # Cancel associated task if it exists
                task = self._pending_tasks.pop(request_id, None)
                if task and isinstance(task, asyncio.Task) and not task.done():
                    task.cancel()
                    cancelled_tasks.append(task)
                    logger.debug(f"Task for request {request_id} cancelled")

        # Await all cancelled tasks to ensure proper cleanup (finally blocks, resource release)
        if cancelled_tasks:
            results = await asyncio.gather(*cancelled_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, asyncio.CancelledError):
                    pass  # Expected from cancellation
                elif isinstance(result, Exception):
                    logger.debug(f"Task cleanup exception: {result}")

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
