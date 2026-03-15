"""
Rate limiting service for research endpoints.

Tracks requests per user and enforces rate limits to prevent abuse.
Uses an in-memory store for simplicity; can be extended to Redis for horizontal scaling.
"""

import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Tuple
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class RateLimitStore:
    """Thread-safe in-memory rate limit tracking for users with TTL cleanup."""

    def __init__(self, cleanup_interval_seconds: int = 300, ttl_seconds: int = 3600):
        # {user_id: deque of request timestamps}
        self.user_requests: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.ttl_seconds = ttl_seconds  # Remove entries older than this

    def add_request(self, user_id: str) -> None:
        """Record a request for a user (thread-safe)."""
        now = datetime.utcnow()
        with self._lock:
            self.user_requests[user_id].append(now)

    def get_request_count(self, user_id: str, window_seconds: int = 60) -> int:
        """Get number of requests in the last N seconds (thread-safe)."""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=window_seconds)

        with self._lock:
            # Remove old requests outside the window
            requests = self.user_requests.get(user_id, deque())
            while requests and requests[0] < cutoff:
                requests.popleft()

            return len(requests)

    def is_rate_limited(
        self, user_id: str, max_requests: int = 10, window_seconds: int = 60
    ) -> bool:
        """Check if user has exceeded rate limit (non-atomic)."""
        count = self.get_request_count(user_id, window_seconds)
        return count >= max_requests

    def check_and_record(
        self, user_id: str, max_requests: int = 10, window_seconds: int = 60
    ) -> bool:
        """
        Atomically check and record a request.
        
        Returns:
            True if request was allowed and recorded; False if rate limited
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=window_seconds)

        with self._lock:
            requests = self.user_requests[user_id]
            
            # Remove old requests outside the window
            while requests and requests[0] < cutoff:
                requests.popleft()

            # Check if at limit
            if len(requests) >= max_requests:
                return False

            # Record this request in the same critical section
            requests.append(now)
            return True

    def cleanup_expired(self) -> None:
        """Remove entries for users with no recent requests."""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.ttl_seconds)

        with self._lock:
            expired_users = []
            for user_id, requests in self.user_requests.items():
                # Remove old requests from this user
                while requests and requests[0] < cutoff:
                    requests.popleft()
                
                # If user has no requests left, mark for deletion
                if not requests:
                    expired_users.append(user_id)

            # Delete expired users
            for user_id in expired_users:
                del self.user_requests[user_id]

            logger.debug(f"Cleaned up {len(expired_users)} expired rate limit entries")


# Global rate limit store (can be replaced with Redis for scaling)
_rate_limit_store = RateLimitStore()


def get_rate_limiter() -> RateLimitStore:
    """Get the global rate limiter instance."""
    return _rate_limit_store
