"""Payment-related models (Dodo Payments)."""

from pydantic import BaseModel
from decimal import Decimal
from typing import List
from enum import Enum


class SubscriptionTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """Dodo Payments subscription status."""

    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    TRIALING = "trialing"
    INCOMPLETE = "incomplete"


class SubscriptionPlan(BaseModel):
    tier: SubscriptionTier
    name: str
    price_monthly_usd: Decimal
    features: List[str]


class DodoCheckoutSessionCreate(BaseModel):
    """Request to create a Dodo Payments checkout session."""

    user_id: str
    tier: SubscriptionTier


class DodoCheckoutSessionResponse(BaseModel):
    """Response from Dodo Payments checkout creation."""

    checkout_url: str
    payment_id: str
