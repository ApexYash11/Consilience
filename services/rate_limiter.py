"""
Rate limiting service for research endpoints.

Tracks requests per user and enforces rate limits to prevent abuse.
Uses an in-memory store for simplicity; can be extended to Redis for horizontal scaling.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class RateLimitStore:
    """In-memory rate limit tracking for users."""

    def __init__(self):
        # {user_id: deque of request timestamps}
        self.user_requests: Dict[str, deque] = defaultdict(deque)

    def add_request(self, user_id: str) -> None:
        """Record a request for a user."""
        now = datetime.utcnow()
        self.user_requests[user_id].append(now)

    def get_request_count(self, user_id: str, window_seconds: int = 60) -> int:
        """Get number of requests in the last N seconds."""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=window_seconds)

        # Remove old requests outside the window
        requests = self.user_requests[user_id]
        while requests and requests[0] < cutoff:
            requests.popleft()

        return len(requests)

    def is_rate_limited(
        self, user_id: str, max_requests: int = 10, window_seconds: int = 60
    ) -> bool:
        """Check if user has exceeded rate limit."""
        count = self.get_request_count(user_id, window_seconds)
        return count >= max_requests


# Global rate limit store (can be replaced with Redis for scaling)
_rate_limit_store = RateLimitStore()


def get_rate_limiter() -> RateLimitStore:
    """Get the global rate limiter instance."""
    return _rate_limit_store
