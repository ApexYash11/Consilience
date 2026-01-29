"""Payment routes for subscriptions and billing."""
from fastapi import APIRouter, Depends, HTTPException
from models.payment import StripeCheckoutSessionCreate, StripeCheckoutSessionResponse
from services.payment_service import PaymentService

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.get("/plans")
async def get_plans(service: PaymentService = Depends()):
    """Get available subscription plans."""
    return service.get_plans()


@router.post("/checkout", response_model=StripeCheckoutSessionResponse)
async def create_checkout(request: StripeCheckoutSessionCreate, service: PaymentService = Depends()):
    """Create a Stripe checkout session for subscription."""
    return service.create_checkout_session(request)


@router.post("/webhook")
async def stripe_webhook():
    """Handle Stripe webhooks for payment updates."""
    # Placeholder for webhook logic
    return {"status": "received"}
