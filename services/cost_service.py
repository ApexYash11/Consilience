"""
Cost tracking service.

Tracks cumulative monthly token/cost usage per user in the database
and exposes a quota check used by the API dependency layer.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import AsyncSessionLocal
from database.schema import UserDB, UsageRecordDB
from models.research import ResearchDepth
from utils.cost_estimator import estimate_research_cost

logger = logging.getLogger(__name__)


class CostService:
    """Per-user cost tracking and quota enforcement."""

    # ------------------------------------------------------------------
    # Estimation (no DB)
    # ------------------------------------------------------------------

    @staticmethod
    def estimate(depth: ResearchDepth) -> Dict[str, Any]:
        """Return a cost estimate dict for a given research depth."""
        mode = "deep" if depth == ResearchDepth.DEEP else "standard"
        return estimate_research_cost(mode)

    # ------------------------------------------------------------------
    # Quota checks
    # ------------------------------------------------------------------

    async def check_quota(self, user_id: str, depth: ResearchDepth) -> None:
        """
        Raise ValueError if the user has exhausted their monthly quota.

        Called as a FastAPI dependency before creating a research task.
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(UserDB).where(UserDB.id == user_id))
            user: Optional[UserDB] = result.scalar_one_or_none()

        if user is None:
            raise ValueError(f"User {user_id} not found")

        if depth == ResearchDepth.DEEP:
            quota = user.monthly_deep_quota or 0
            used = user.deep_papers_this_month or 0
            label = "deep research"
        else:
            quota = user.monthly_standard_quota or 5
            used = user.standard_papers_this_month or 0
            label = "standard research"

        if quota > 0 and used >= quota:
            raise ValueError(
                f"Monthly {label} quota exhausted ({used}/{quota}). "
                "Upgrade your plan or wait for the next billing cycle."
            )

    # ------------------------------------------------------------------
    # Usage recording (called after a task completes)
    # ------------------------------------------------------------------

    async def record_usage(
        self,
        user_id: str,
        depth: ResearchDepth,
        tokens_used: int,
        cost_usd: float,
    ) -> None:
        """Increment the user's monthly usage counters after a completed task."""
        async with AsyncSessionLocal() as session:
            # Determine which counter to bump
            if depth == ResearchDepth.DEEP:
                await session.execute(
                    update(UserDB)
                    .where(UserDB.id == user_id)
                    .values(
                        deep_papers_this_month=UserDB.deep_papers_this_month + 1,
                        total_tokens_this_month=UserDB.total_tokens_this_month + tokens_used,
                        total_cost_this_month=UserDB.total_cost_this_month + cost_usd,
                    )
                )
            else:
                await session.execute(
                    update(UserDB)
                    .where(UserDB.id == user_id)
                    .values(
                        standard_papers_this_month=UserDB.standard_papers_this_month + 1,
                        total_tokens_this_month=UserDB.total_tokens_this_month + tokens_used,
                        total_cost_this_month=UserDB.total_cost_this_month + cost_usd,
                    )
                )
            await session.commit()

        logger.info(
            "Usage recorded for user %s: depth=%s tokens=%d cost=$%.4f",
            user_id, depth.value, tokens_used, cost_usd,
        )

    # ------------------------------------------------------------------
    # Usage summary (for /api/users/usage)
    # ------------------------------------------------------------------

    async def get_usage_summary(self, user_id: str) -> Dict[str, Any]:
        """Return current-month usage and remaining quota for a user."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(UserDB).where(UserDB.id == user_id))
            user: Optional[UserDB] = result.scalar_one_or_none()

        if user is None:
            raise ValueError(f"User {user_id} not found")

        standard_quota = user.monthly_standard_quota or 5
        deep_quota = user.monthly_deep_quota or 0
        standard_used = user.standard_papers_this_month or 0
        deep_used = user.deep_papers_this_month or 0

        return {
            "user_id": user_id,
            "period": datetime.now(timezone.utc).strftime("%Y-%m"),
            "standard_research": {
                "used": standard_used,
                "quota": standard_quota,
                "remaining": max(0, standard_quota - standard_used),
            },
            "deep_research": {
                "used": deep_used,
                "quota": deep_quota,
                "remaining": max(0, deep_quota - deep_used) if deep_quota > 0 else 0,
                "available": deep_quota > 0,
            },
            "tokens_this_month": user.total_tokens_this_month or 0,
            "cost_this_month_usd": float(user.total_cost_this_month or 0.0),
            "subscription_tier": user.subscription_tier.value if user.subscription_tier else "free",
        }
