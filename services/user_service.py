"""
User service — manages user subscription state in the database.

Called by the webhook handler after Dodo Payments events to keep
the user's tier and dodo IDs in sync with the payment provider.
"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import AsyncSessionLocal
from database.schema import UserDB
from models.payment import SubscriptionStatus, SubscriptionTier

logger = logging.getLogger(__name__)


class UserService:
    """Async user management operations."""

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_user(self, user_id: str) -> Optional[UserDB]:
        """Fetch a user record by ID (UUID string)."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UserDB).where(UserDB.id == user_id)
            )
            return result.scalar_one_or_none()

    async def get_user_by_dodo_customer(self, dodo_customer_id: str) -> Optional[UserDB]:
        """Look up a user by their Dodo customer ID."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UserDB).where(UserDB.dodo_customer_id == dodo_customer_id)
            )
            return result.scalar_one_or_none()

    async def get_dodo_subscription_id(self, user_id: str) -> Optional[str]:
        """Return the stored Dodo subscription ID for a user, or None."""
        user = await self.get_user(user_id)
        if user is None:
            return None
        return str(user.dodo_subscription_id) if user.dodo_subscription_id else None

    # ------------------------------------------------------------------
    # Writes (called by webhook handler)
    # ------------------------------------------------------------------

    async def update_subscription(
        self,
        user_id: str,
        tier: SubscriptionTier,
        status: SubscriptionStatus,
        dodo_customer_id: Optional[str] = None,
        dodo_subscription_id: Optional[str] = None,
    ) -> None:
        """
        Sync subscription state into the database after a Dodo webhook event.

        Also grants/revokes deep research quota based on tier.
        """
        values: dict = {
            "subscription_tier": tier,
            "subscription_status": status,
        }
        if dodo_customer_id:
            values["dodo_customer_id"] = dodo_customer_id
        if dodo_subscription_id:
            values["dodo_subscription_id"] = dodo_subscription_id

        # Adjust deep research quota based on tier
        if tier == SubscriptionTier.PRO:
            values["monthly_deep_quota"] = 5
        elif tier == SubscriptionTier.ENTERPRISE:
            values["monthly_deep_quota"] = 100
        else:
            values["monthly_deep_quota"] = 0

        async with AsyncSessionLocal() as session:
            await session.execute(
                update(UserDB).where(UserDB.id == user_id).values(**values)
            )
            await session.commit()

        logger.info(
            "Updated subscription for user %s: tier=%s status=%s",
            user_id,
            tier,
            status,
        )

    async def revoke_paid_tier(self, user_id: str) -> None:
        """Downgrade user to FREE tier (triggered by cancellation/failure)."""
        await self.update_subscription(
            user_id=user_id,
            tier=SubscriptionTier.FREE,
            status=SubscriptionStatus.CANCELED,
        )

