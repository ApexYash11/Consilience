"""
Tests for rate limiting service.

Tests request tracking and rate limit enforcement.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from services.rate_limiter import RateLimitStore, get_rate_limiter


class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_rate_limiter_tracks_requests(self):
        """Rate limiter records requests."""
        limiter = RateLimitStore()
        user_id = str(uuid4())

        limiter.add_request(user_id)
        limiter.add_request(user_id)

        assert limiter.get_request_count(user_id) == 2

    def test_rate_limiter_counts_within_window(self):
        """Rate limiter only counts recent requests."""
        limiter = RateLimitStore()
        user_id = str(uuid4())

        # Add a request and manually set its time to 90 seconds ago
        limiter.add_request(user_id)
        now = datetime.utcnow()
        old_time = now - timedelta(seconds=90)
        limiter.user_requests[user_id][0] = old_time

        # Add a new request (within window)
        limiter.add_request(user_id)

        # Only recent request should count (60 second window)
        count = limiter.get_request_count(user_id, window_seconds=60)
        assert count == 1

    def test_rate_limiter_allows_under_limit(self):
        """User not rate limited if under limit."""
        limiter = RateLimitStore()
        user_id = str(uuid4())

        # Add 5 requests
        for _ in range(5):
            limiter.add_request(user_id)

        # Not limited with max of 10
        assert not limiter.is_rate_limited(user_id, max_requests=10)

    def test_rate_limiter_blocks_over_limit(self):
        """User rate limited when over limit."""
        limiter = RateLimitStore()
        user_id = str(uuid4())

        # Add 10 requests
        for _ in range(10):
            limiter.add_request(user_id)

        # Limited with max of 10
        assert limiter.is_rate_limited(user_id, max_requests=10)

    def test_rate_limiter_resets_after_window(self):
        """Requests outside window are forgotten."""
        limiter = RateLimitStore()
        user_id = str(uuid4())

        # Add request and artificially age it beyond the window
        limiter.add_request(user_id)
        old_time = datetime.utcnow() - timedelta(seconds=120)
        limiter.user_requests[user_id][0] = old_time

        # Check not limited (old request cleaned up)
        count = limiter.get_request_count(user_id, window_seconds=60)
        assert count == 0
        assert not limiter.is_rate_limited(user_id, max_requests=10, window_seconds=60)

    def test_different_users_tracked_separately(self):
        """Rate limits are per-user."""
        limiter = RateLimitStore()
        user1 = str(uuid4())
        user2 = str(uuid4())

        # User 1 makes 8 requests
        for _ in range(8):
            limiter.add_request(user1)

        # User 2 makes 3 requests
        for _ in range(3):
            limiter.add_request(user2)

        # Verify counts are separate
        assert limiter.get_request_count(user1) == 8
        assert limiter.get_request_count(user2) == 3
        assert limiter.is_rate_limited(user1, max_requests=10) is False
        assert limiter.is_rate_limited(user2, max_requests=10) is False

    def test_global_rate_limiter_instance(self):
        """get_rate_limiter returns singleton."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()

        assert limiter1 is limiter2

    def test_custom_window_size(self):
        """Rate limiter respects custom window sizes."""
        limiter = RateLimitStore()
        user_id = str(uuid4())

        # Add request at t=0
        limiter.add_request(user_id)

        # Count with 30 second window (should include request)
        count = limiter.get_request_count(user_id, window_seconds=30)
        assert count == 1

        # Count with 1 second window (request is still recent, so included)
        count = limiter.get_request_count(user_id, window_seconds=1)
        assert count == 1
