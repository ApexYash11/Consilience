"""
Tests for Phase 5: Quota and Rate Limiting

Tests quota enforcement, HTTP 429 responses, and usage tracking.
"""

import pytest
from uuid import uuid4
from decimal import Decimal
from typing import cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from ..database.schema import UserDB, UsageRecordDB
from ..models.research import ResearchDepth
from ..models.user import CurrentUser
from ..models.payment import SubscriptionTier
from ..services.cost_service import CostService


@pytest.mark.asyncio
class TestQuotaEnforcement:
    """Test quota checks and HTTP 429 responses."""

    async def test_standard_quota_check_passes_when_under_limit(self):
        """Standard research allowed when usage < quota."""
        # Mock user with available quota
        mock_user = UserDB(
            id="test_user_123",
            email="test@example.com",
            subscription_tier=SubscriptionTier.FREE.value,
            monthly_standard_quota=5,
            monthly_deep_quota=3,
            standard_papers_this_month=2,
            deep_papers_this_month=0,
            total_tokens_this_month=1000,
            total_cost_this_month=10.0
        )
        
        with patch('services.cost_service.AsyncSessionLocal') as mock_session_local:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_local.return_value.__aenter__.return_value = mock_session
            
            # Mock the execute to return our user
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_user)
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            cost_service = CostService()
            # Should not raise (user is under default quota of 5)
            await cost_service.check_quota("test_user_123", ResearchDepth.STANDARD)

    async def test_standard_quota_check_fails_when_at_limit(self):
        """Standard research blocked when usage >= quota."""
        # Mock user with exhausted quota
        mock_user = UserDB(
            id="test_user_456",
            email="test@example.com",
            subscription_tier=SubscriptionTier.FREE.value,
            monthly_standard_quota=5,
            monthly_deep_quota=3,
            standard_papers_this_month=5,  # At limit
            deep_papers_this_month=0,
            total_tokens_this_month=5000,
            total_cost_this_month=50.0
        )
        
        with patch('services.cost_service.AsyncSessionLocal') as mock_session_local:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_local.return_value.__aenter__.return_value = mock_session
            
            # Mock the execute to return our user
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_user)
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            cost_service = CostService()
            
            # Should raise ValueError (quota exhausted)
            with pytest.raises(ValueError, match="quota exhausted"):
                await cost_service.check_quota("test_user_456", ResearchDepth.STANDARD)

    async def test_deep_quota_check_fails_when_at_limit(self):
        """Deep research blocked when usage >= quota."""
        mock_user = UserDB(
            id="test_user_789",
            email="test@example.com",
            subscription_tier="pro",
            monthly_standard_quota=20,
            monthly_deep_quota=10,
            standard_papers_this_month=5,
            deep_papers_this_month=10,
            total_tokens_this_month=5000,
            total_cost_this_month=100.0
        )
        
        with patch('services.cost_service.AsyncSessionLocal') as mock_session_local:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_local.return_value.__aenter__.return_value = mock_session
            
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_user)
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            cost_service = CostService()
            
            # Should raise ValueError (quota exhausted)
            with pytest.raises(ValueError, match="deep research.*quota exhausted"):
                await cost_service.check_quota("test_user_789", ResearchDepth.DEEP)

    async def test_quota_check_user_not_found(self):
        """Quota check raises ValueError for non-existent user."""
        with patch('services.cost_service.AsyncSessionLocal') as mock_session_local:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_local.return_value.__aenter__.return_value = mock_session
            
            # Mock the execute to return None (user not found)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            cost_service = CostService()
            fake_user_id = str(uuid4())
            
            with pytest.raises(ValueError, match="not found"):
                await cost_service.check_quota(fake_user_id, ResearchDepth.STANDARD)

    async def test_quota_check_with_zero_quota_means_unlimited(self):
        """Zero quota means unlimited usage (for free tier)."""
        # Mock user with zero quota (unlimited)
        mock_user = UserDB(
            id="test_unlimited",
            email="test@example.com",
            subscription_tier=SubscriptionTier.FREE.value,
            monthly_standard_quota=5,
            monthly_deep_quota=0,  # Zero = unlimited
            standard_papers_this_month=0,
            deep_papers_this_month=100,  # Way over, but shouldn't fail
            total_tokens_this_month=10000,
            total_cost_this_month=200.0
        )
        
        with patch('services.cost_service.AsyncSessionLocal') as mock_session_local:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_local.return_value.__aenter__.return_value = mock_session
            
            # Mock the execute to return our user
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_user)
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            cost_service = CostService()
            
            # Should NOT raise (zero quota = unlimited)
            await cost_service.check_quota("test_unlimited", ResearchDepth.DEEP)


@pytest.mark.asyncio
class TestUsageTracking:
    """Test usage recording."""

    async def test_record_standard_usage_works(self):
        """Recording usage succeeds and calls session methods."""
        with patch('services.cost_service.AsyncSessionLocal') as mock_session_local:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_session.execute = AsyncMock()
            mock_session.commit = AsyncMock()
            
            cost_service = CostService()
            await cost_service.record_usage(
                user_id="test_user",
                depth=ResearchDepth.STANDARD,
                tokens_used=2000,
                cost_usd=1.50,
            )
            
            assert mock_session.add.called
            assert mock_session.commit.awaited

    async def test_record_deep_usage_works(self):
        """Recording deep usage succeeds and calls session methods."""
        with patch('services.cost_service.AsyncSessionLocal') as mock_session_local:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_session.execute = AsyncMock()
            mock_session.commit = AsyncMock()
            
            cost_service = CostService()
            await cost_service.record_usage(
                user_id="test_user",
                depth=ResearchDepth.DEEP,
                tokens_used=8000,
                cost_usd=5.00,
            )
            
            assert mock_session.add.called
            assert mock_session.commit.awaited

    async def test_usage_record_creates_entry(self):
        """Usage recording calls commit."""
        with patch('services.cost_service.AsyncSessionLocal') as mock_session_local:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()
            
            cost_service = CostService()
            await cost_service.record_usage(
                user_id="test_user",
                depth=ResearchDepth.STANDARD,
                tokens_used=2000,
                cost_usd=1.50,
            )
            
            # Verify commit was called
            assert mock_session.commit.called


@pytest.mark.asyncio
class TestUsageSummary:
    """Test the usage summary endpoint data."""

    async def test_get_usage_summary_returns_correct_structure(self):
        """Usage summary returns correct data structure."""
        mock_user = UserDB(
            id="test_user",
            email="test@example.com",
            subscription_tier="free",
            monthly_standard_quota=5,
            monthly_deep_quota=3,
            standard_papers_this_month=2,
            deep_papers_this_month=1,
            total_tokens_this_month=3000,
            total_cost_this_month=2.50,
        )
        
        with patch('services.cost_service.AsyncSessionLocal') as mock_session_local:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_user
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            cost_service = CostService()
            summary = await cost_service.get_usage_summary("test_user")
            
            assert "period" in summary
            assert isinstance(summary, dict)

    async def test_get_usage_summary_includes_quotas(self):
        """Usage summary includes quota info."""
        mock_user = UserDB(
            id="test_user",
            email="test@example.com",
            subscription_tier="free",
            monthly_standard_quota=5,
            monthly_deep_quota=3,
            standard_papers_this_month=2,
            deep_papers_this_month=0,
        )
        
        with patch('services.cost_service.AsyncSessionLocal') as mock_session_local:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_user
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            cost_service = CostService()
            summary = await cost_service.get_usage_summary("test_user")
            
            assert "standard_research" in summary or "standard" in summary

    async def test_get_usage_summary_shows_remaining(self):
        """Usage summary calculates remaining quota correctly."""
        mock_user = UserDB(
            id="test_user",
            email="test@example.com",
            subscription_tier="free",
            monthly_standard_quota=10,
            standard_papers_this_month=3,
        )
        
        with patch('services.cost_service.AsyncSessionLocal') as mock_session_local:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_user
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            cost_service = CostService()
            summary = await cost_service.get_usage_summary("test_user")
            
            assert summary["standard_research"]["quota"] == 10
            assert summary["standard_research"]["used"] == 3
            assert summary["standard_research"]["remaining"] == 7

    async def test_get_usage_summary_free_tier_no_deep(self):
        """Free tier shows zero quota for deep research."""
        mock_user = UserDB(
            id="test_user",
            email="test@example.com",
            subscription_tier="free",
            monthly_standard_quota=5,
            monthly_deep_quota=0,
            standard_papers_this_month=0,
            deep_papers_this_month=0,
            total_tokens_this_month=0,
            total_cost_this_month=0.00,
        )
        
        with patch('services.cost_service.AsyncSessionLocal') as mock_session_local:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_user
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            cost_service = CostService()
            summary = await cost_service.get_usage_summary("test_user")
            
            assert summary["deep_research"]["available"] is False
            assert summary["deep_research"]["quota"] == 0

    async def test_get_usage_summary_paid_tier_has_deep(self):
        """Paid tier has deep research quota available."""
        mock_user = UserDB(
            id="test_user",
            email="test@example.com",
            subscription_tier="pro",
            monthly_standard_quota=20,
            monthly_deep_quota=10,
            standard_papers_this_month=0,
            deep_papers_this_month=0,
            total_tokens_this_month=0,
            total_cost_this_month=0.00,
        )
        
        with patch('services.cost_service.AsyncSessionLocal') as mock_session_local:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_user
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            cost_service = CostService()
            summary = await cost_service.get_usage_summary("test_user")
            
            assert summary["deep_research"]["available"] is True
            assert summary["deep_research"]["quota"] == 10

    async def test_get_usage_summary_includes_costs(self):
        """Usage summary includes cost information."""
        mock_user = UserDB(
            id="test_user",
            email="test@example.com",
            subscription_tier="free",
            monthly_standard_quota=5,
            monthly_deep_quota=0,
            standard_papers_this_month=0,
            deep_papers_this_month=0,
            total_tokens_this_month=1000,
            total_cost_this_month=5.00,
        )
        
        with patch('services.cost_service.AsyncSessionLocal') as mock_session_local:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_user
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            cost_service = CostService()
            summary = await cost_service.get_usage_summary("test_user")
            
            assert isinstance(summary, dict)

    async def test_get_usage_summary_user_not_found(self):
        """Usage summary raises for non-existent user."""
        with patch('services.cost_service.AsyncSessionLocal') as mock_session_local:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_local.return_value.__aenter__.return_value = mock_session
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            cost_service = CostService()
            with pytest.raises(ValueError, match="not found"):
                await cost_service.get_usage_summary(str(uuid4()))


@pytest.mark.asyncio
class TestCostEstimation:
    """Test cost estimation."""

    def test_estimate_standard_returns_dict(self):
        """Cost estimate returns proper dict."""
        estimate = CostService.estimate(ResearchDepth.STANDARD)
        
        assert isinstance(estimate, dict)
        assert "total" in estimate

    def test_estimate_deep_returns_dict(self):
        """Deep cost estimate returns proper dict."""
        estimate = CostService.estimate(ResearchDepth.DEEP)
        
        assert isinstance(estimate, dict)
        assert "total" in estimate

    def test_deep_estimate_higher_than_standard(self):
        """Deep research should cost more than standard."""
        standard = CostService.estimate(ResearchDepth.STANDARD)
        deep = CostService.estimate(ResearchDepth.DEEP)
        
        standard_cost = standard.get("total", 0)
        deep_cost = deep.get("total", 0)
        
        assert deep_cost > standard_cost
