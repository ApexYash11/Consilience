"""Payment routes for subscriptions and billing (Dodo Payments)."""

from fastapi import APIRouter, Depends, HTTPException, status
from models.payment import DodoCheckoutSessionCreate, DodoCheckoutSessionResponse, SubscriptionPlan
from services.payment_service import PaymentService
from api.dependencies import get_current_user
from typing import List

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.get("/plans", response_model=List[SubscriptionPlan], summary="List available subscription plans")
async def get_plans():
    """Return all available subscription plans with pricing."""
    return PaymentService.get_plans()


@router.post("/checkout", response_model=DodoCheckoutSessionResponse, summary="Create checkout session")
async def create_checkout(
    request: DodoCheckoutSessionCreate,
    current_user=Depends(get_current_user),
):
    """Create a Dodo Payments checkout session. Returns a URL to redirect the user to."""
    service = PaymentService()
    return await service.create_checkout_session(user_id=current_user.user_id, tier=request.tier)


@router.post("/cancel", summary="Cancel current subscription")
async def cancel_subscription(
    current_user=Depends(get_current_user),
):
    """Cancel the authenticated user's active subscription."""
    service = PaymentService()
    return await service.cancel_subscription(user_id=current_user.user_id)
