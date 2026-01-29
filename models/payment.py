"""Payment-related models."""
from pydantic import BaseModel
from decimal import Decimal
from typing import List
from enum import Enum


class SubscriptionTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """Stripe subscription status."""
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
