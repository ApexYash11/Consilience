"""
Dodo Payments webhook handler.

Receives and processes subscription lifecycle events from Dodo Payments.

Security requirements:
- Every request MUST pass HMAC-SHA256 signature verification before any
  business logic runs. Processing an unverified payload is a critical
  integrity failure (OWASP A08).
- Raw request body is read once and passed to verification; never trust
  parsed JSON before the signature is confirmed.
"""

import hashlib
import hmac
import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException, Request, status

from ...core.config import get_settings
from ...models.payment import SubscriptionStatus, SubscriptionTier
from ...services.user_service import UserService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def _verify_dodo_signature(payload: bytes, signature_header: str, secret: str) -> None:
    """
    Verify an HMAC-SHA256 webhook signature from Dodo Payments.

    Dodo sends the signature as:
        X-Dodo-Signature: sha256=<hex_digest>

    Raises:
        HTTPException 400 if signature is missing or malformed.
        HTTPException 401 if signature does not match.
    """
    if not signature_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Dodo-Signature header",
        )

    parts = signature_header.split("=", 1)
    if len(parts) != 2 or parts[0] != "sha256":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed X-Dodo-Signature header (expected sha256=<digest>)",
        )

    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, parts[1]):
        logger.warning("Dodo webhook signature mismatch — request rejected")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook signature verification failed",
        )


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/dodo",
    status_code=status.HTTP_200_OK,
    summary="Dodo Payments webhook receiver",
)
async def dodo_webhook(
    request: Request,
    x_dodo_signature: str = Header(None, alias="X-Dodo-Signature"),
) -> Dict[str, str]:
    """
    Receive and process Dodo Payments subscription lifecycle events.

    Supported events:
    - subscription.active      → upgrade user to PAID tier
    - subscription.cancelled   → downgrade user to FREE tier
    - payment.succeeded        → record successful payment
    - payment.failed           → log payment failure (no tier change unless sub cancelled)

    All unrecognised events are acknowledged (200) and ignored to prevent
    Dodo from retrying indefinitely.
    """
    settings = get_settings()
    webhook_secret = settings.dodo_webhook_secret

    if not webhook_secret:
        # In production this is a configuration error — fail loudly
        logger.error("DODO_WEBHOOK_SECRET is not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured",
        )

    # Read raw body BEFORE parsing so signature is verified on exact received bytes
    raw_body = await request.body()

    _verify_dodo_signature(raw_body, x_dodo_signature or "", webhook_secret)

    # Parse only after verification passes
    try:
        event: Dict[str, Any] = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    event_type: str = event.get("type", "")
    event_data: Dict[str, Any] = event.get("data", {})

    logger.info("Dodo webhook received: type=%s id=%s", event_type, event.get("id"))

    user_service = UserService()

    try:
        if event_type == "subscription.active":
            await _handle_subscription_active(event_data, user_service)

        elif event_type == "subscription.cancelled":
            await _handle_subscription_cancelled(event_data, user_service)

        elif event_type == "payment.succeeded":
            # Informational — tier is already set via subscription.active
            logger.info(
                "Payment succeeded: amount=%s customer=%s",
                event_data.get("amount"),
                event_data.get("customer_id"),
            )

        elif event_type == "payment.failed":
            logger.warning(
                "Payment failed: customer=%s reason=%s",
                event_data.get("customer_id"),
                event_data.get("failure_reason"),
            )

        else:
            logger.debug("Unhandled Dodo event type: %s — acknowledged", event_type)

    except Exception as exc:
        # Log the error but still return 200 to prevent Dodo retrying
        # the same event. A retry won't fix a bug; investigate via logs.
        logger.error("Error processing Dodo event %s: %s", event_type, exc, exc_info=True)

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

async def _handle_subscription_active(
    data: Dict[str, Any], user_service: UserService
) -> None:
    """Grant paid tier when a subscription becomes active."""
    customer_id: str = data.get("customer_id", "")
    subscription_id: str = data.get("subscription_id", "")
    product_id: str = data.get("product_id", "")
    metadata: Dict[str, Any] = data.get("metadata", {})

    user_id: str = metadata.get("user_id", "")
    tier_str: str = metadata.get("tier", "pro")

    if not user_id:
        # Fall back to customer ID lookup if metadata missing
        user = await user_service.get_user_by_dodo_customer(customer_id)
        if not user:
            logger.error("subscription.active: cannot resolve user for customer %s", customer_id)
            return
        user_id = str(user.id)

    tier = SubscriptionTier.PRO if "enterprise" not in tier_str.lower() else SubscriptionTier.ENTERPRISE

    await user_service.update_subscription(
        user_id=user_id,
        tier=tier,
        status=SubscriptionStatus.ACTIVE,
        dodo_customer_id=customer_id,
        dodo_subscription_id=subscription_id,
    )
    logger.info("subscription.active: user %s upgraded to %s", user_id, tier)


async def _handle_subscription_cancelled(
    data: Dict[str, Any], user_service: UserService
) -> None:
    """Revoke paid tier when a subscription is cancelled."""
    customer_id: str = data.get("customer_id", "")
    metadata: Dict[str, Any] = data.get("metadata", {})

    user_id: str = metadata.get("user_id", "")

    if not user_id:
        user = await user_service.get_user_by_dodo_customer(customer_id)
        if not user:
            logger.error("subscription.cancelled: cannot resolve user for customer %s", customer_id)
            return
        user_id = str(user.id)

    await user_service.revoke_paid_tier(user_id)
    logger.info("subscription.cancelled: user %s downgraded to FREE", user_id)
