"""User management routes — usage dashboard and profile."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_current_user
from services.cost_service import CostService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["users"])


@router.get(
    "/usage",
    summary="Current month usage and quota",
    description="Get usage statistics and remaining quota for the authenticated user",
    response_description="Token usage, paper counts, and remaining quota for the current billing period.",
    tags=["users"],
)
async def get_usage(
    current_user=Depends(get_current_user),
):
    """
    Return usage statistics and remaining quota for the authenticated user.

    Response example:
    ```json
    {
        "user_id": "...",
        "period": "2026-03",
        "standard_research": {"used": 2, "quota": 5, "remaining": 3},
        "deep_research": {"used": 1, "quota": 5, "remaining": 4, "available": true},
        "tokens_this_month": 32000,
        "cost_this_month_usd": 12.50,
        "subscription_tier": "pro"
    }
    ```
    """
    try:
        summary = await CostService().get_usage_summary(current_user.user_id)
        return summary
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to get usage summary for user %s: %s", current_user.user_id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve usage")
