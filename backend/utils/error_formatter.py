"""
Error Response Formatter - Uniform error response structure

Provides utilities to format error responses with structured error codes,
maintaining backward compatibility while adding machine-readable error classification.
"""

import logging
from typing import Any, Dict, Optional
from pydantic import BaseModel

from ..core.error_codes import ErrorCodes, ErrorCodeDef

logger = logging.getLogger(__name__)


class StructuredErrorResponse(BaseModel):
    """
    Standard error response format for all API errors.
    
    Maintains backward compatibility ("detail" field) while adding
    Machine-readable error_code and retryable flag for frontend.
    """
    
    detail: str  # Backward compatible - human readable message
    error_code: str  # Machine readable error code (e.g., "RATE_LIMIT")
    retryable: bool  # Whether frontend should retry
    error_context: Optional[Dict[str, Any]] = None  # Additional context if available


def format_error_response(
    message: str,
    error_code_def: ErrorCodeDef,
    error_context: Optional[Dict[str, Any]] = None,
) -> StructuredErrorResponse:
    """
    Format an error response with structured error code.
    
    Args:
        message: Human-readable error message (for 'detail' field)
        error_code_def: ErrorCodeDef defining the error type
        error_context: Optional context dict (e.g., remaining_quota, retry_after_seconds)
        
    Returns:
        StructuredErrorResponse ready to be used in FastAPI HTTPException or endpoint response
    """
    return StructuredErrorResponse(
        detail=message,
        error_code=error_code_def.code,
        retryable=error_code_def.retryable,
        error_context=error_context,
    )


def format_rate_limit_error(
    retry_after_seconds: Optional[int] = None,
    agent_name: str = "unknown",
) -> StructuredErrorResponse:
    """Format a rate limit (429) error response."""
    message = f"API rate limit exceeded (agent: {agent_name}). Please retry after waiting."
    context: Dict[str, Any] = {}
    if retry_after_seconds:
        context["retry_after_seconds"] = retry_after_seconds
        message += f" Retry after {retry_after_seconds}s."
    
    return format_error_response(message, ErrorCodes.RATE_LIMIT, context or None)


def format_timeout_error(
    timeout_seconds: float,
    task_id: Optional[str] = None,
) -> StructuredErrorResponse:
    """Format a timeout (408) error response."""
    message = f"Request exceeded timeout ({timeout_seconds:.1f}s)"
    if task_id:
        message += f" for task {task_id}"
    message += ". Can be retried."
    
    context: Dict[str, Any] = {"timeout_seconds": timeout_seconds}
    if task_id:
        context["task_id"] = task_id
    
    return format_error_response(message, ErrorCodes.TIMEOUT, context)


def format_quota_exceeded_error(
    research_type: str = "deep",
    remaining: int = 0,
    quota: int = 0,
) -> StructuredErrorResponse:
    """Format a quota exceeded (402) error response."""
    message = (
        f"Monthly {research_type} research quota exceeded. "
        f"Used {quota - remaining}/{quota}. Upgrade your plan to continue."
    )
    
    context: Dict[str, Any] = {
        "research_type": research_type,
        "remaining": remaining,
        "quota": quota,
    }
    
    return format_error_response(message, ErrorCodes.QUOTA_EXCEEDED, context)


def format_orphaned_task_error(
    task_id: str,
    stale_minutes: int = 5,
) -> StructuredErrorResponse:
    """Format an orphaned task (503) error response."""
    message = (
        f"Task {task_id} lost heartbeat (stale for {stale_minutes}+ minutes). "
        "The task may have failed. Please retry your request."
    )
    
    context: Dict[str, Any] = {
        "task_id": task_id,
        "stale_minutes": stale_minutes,
    }
    
    return format_error_response(message, ErrorCodes.ORPHANED_TASK, context)


def format_validation_error(
    message: str,
    field: Optional[str] = None,
    provided_value: Optional[Any] = None,
) -> StructuredErrorResponse:
    """Format a validation (400) error response."""
    context: Dict[str, Any] = {}
    if field:
        context["field"] = field
        message = f"Validation error in field '{field}': {message}"
    if provided_value is not None:
        context["provided_value"] = str(provided_value)
    
    return format_error_response(message, ErrorCodes.VALIDATION_ERROR, context or None)


def format_internal_error(
    message: str = "Internal server error",
    error_type: Optional[str] = None,
    request_id: Optional[str] = None,
) -> StructuredErrorResponse:
    """Format an internal (500) error response."""
    context: Dict[str, Any] = {}
    if error_type:
        context["error_type"] = error_type
        message = f"{error_type}: {message}"
    if request_id:
        context["request_id"] = request_id
    
    return format_error_response(message, ErrorCodes.INTERNAL_ERROR, context or None)
