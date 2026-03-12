"""
Dodo Payments integration service.

Handles subscription checkout, cancellation, and plan management.
Uses the Dodo Payments REST API via httpx (async).

Security:
- API key stored in DODO_API_KEY env var only
- Webhook signature verified in webhooks.py, not here
"""

import hashlib
import hmac
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

import httpx

from core.config import get_settings
from models.payment import (
    DodoCheckoutSessionCreate,
    DodoCheckoutSessionResponse,
    SubscriptionPlan,
    SubscriptionTier,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static plan catalogue — source of truth for pricing
# ---------------------------------------------------------------------------

_PLANS: list[SubscriptionPlan] = [
    SubscriptionPlan(
        tier=SubscriptionTier.FREE,
        name="Free",
        price_monthly_usd=Decimal("0.00"),
        features=[
            "5 standard research papers / month",
            "LangGraph orchestration",
            "7 parallel agents",
            "~3 min per paper",
        ],
    ),
    SubscriptionPlan(
        tier=SubscriptionTier.PRO,
        name="Pro",
        price_monthly_usd=Decimal("29.00"),
        features=[
            "Unlimited standard research",
            "5 deep research papers / month",
            "18 sub-agents, 3 research rounds",
            "Premium LLM (Claude / GPT-4)",
            "~10 min per deep paper",
        ],
    ),
    SubscriptionPlan(
        tier=SubscriptionTier.ENTERPRISE,
        name="Enterprise",
        price_monthly_usd=Decimal("99.00"),
        features=[
            "Unlimited standard + deep research",
            "Priority LLM routing",
            "Dedicated support",
            "Custom model selection",
        ],
    ),
]

# Dodo product IDs — set these in your Dodo Payments dashboard and .env, or
# hard-code the test IDs here while in development.
_PRODUCT_IDS: Dict[SubscriptionTier, str] = {
    SubscriptionTier.PRO: "prod_pro_consilience",
    SubscriptionTier.ENTERPRISE: "prod_enterprise_consilience",
}


class PaymentService:
    """Async Dodo Payments client for subscription lifecycle management."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._api_key = self._settings.dodo_api_key or ""
        self._base_url = self._settings.dodo_api_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_plans() -> list[SubscriptionPlan]:
        """Return all available subscription plans."""
        return _PLANS

    # ------------------------------------------------------------------
    # Checkout
    # ------------------------------------------------------------------

    async def create_checkout_session(
        self,
        user_id: str,
        tier: SubscriptionTier,
    ) -> DodoCheckoutSessionResponse:
        """
        Create a Dodo Payments checkout session.

        Returns a checkout URL that the frontend should redirect the user to.
        On success Dodo will POST a webhook to /api/webhooks/dodo.

        Raises:
            ValueError: if tier is FREE (no payment needed)
            httpx.HTTPStatusError: on Dodo API error
        """
        if tier == SubscriptionTier.FREE:
            raise ValueError("Cannot create a checkout session for the free tier.")

        product_id = _PRODUCT_IDS.get(tier)
        if not product_id:
            raise ValueError(f"Unknown subscription tier: {tier}")

        settings = self._settings
        payload: Dict[str, Any] = {
            "product_id": product_id,
            "customer": {"external_id": user_id},
            "success_url": f"{settings.frontend_url}/payment/success",
            "cancel_url": f"{settings.frontend_url}/payment/cancel",
            "metadata": {"user_id": user_id, "tier": tier.value},
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._base_url}/v1/checkout/sessions",
                json=payload,
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()

        logger.info("Dodo checkout session created for user %s (tier=%s)", user_id, tier)
        return DodoCheckoutSessionResponse(
            checkout_url=data["url"],
            payment_id=data["id"],
        )

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Fetch subscription details from Dodo."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/v1/subscriptions/{subscription_id}",
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def cancel_subscription(self, user_id: str) -> Dict[str, Any]:
        """
        Cancel the subscription for a user.

        Looks up the dodo_subscription_id from the DB via UserService,
        then calls Dodo to cancel it immediately.
        """
        from services.user_service import UserService

        user_service = UserService()
        sub_id = await user_service.get_dodo_subscription_id(user_id)
        if not sub_id:
            raise ValueError(f"No active subscription found for user {user_id}")

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(
                f"{self._base_url}/v1/subscriptions/{sub_id}",
                headers=self._headers,
            )
            resp.raise_for_status()

        logger.info("Subscription %s cancelled for user %s", sub_id, user_id)
        return {"status": "cancelled", "subscription_id": sub_id}

