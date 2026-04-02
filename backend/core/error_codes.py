"""
Structured Error Codes - Machine-readable error classification for backend + frontend

Provides consistent error codes for all failure modes, enabling frontend to:
- Distinguish retryable vs fatal errors
- Show appropriate error UX
- Make intelligent retry decisions

Each error code includes:
- code: string identifier (machine-readable)
- retryable: whether frontend should retry
- http_status: recommended HTTP status code
- description: human-readable description
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class ErrorCodeDef:
    """Definition of a standard error code."""
    code: str
    http_status: int
    retryable: bool
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API responses."""
        return {
            "code": self.code,
            "retryable": self.retryable,
            "description": self.description,
        }


class ErrorCodes:
    """Standard error codes for Consilience platform."""
    
    # Rate Limiting (429)
    RATE_LIMIT = ErrorCodeDef(
        code="RATE_LIMIT",
        http_status=429,
        retryable=True,
        description="API rate limit exceeded. Wait before retrying.",
    )
    
    # Timeouts (408)
    TIMEOUT = ErrorCodeDef(
        code="TIMEOUT",
        http_status=408,
        retryable=True,
        description="Request exceeded timeout. Can be retried.",
    )
    
    # Quota Exceeded (402)
    QUOTA_EXCEEDED = ErrorCodeDef(
        code="QUOTA_EXCEEDED",
        http_status=402,
        retryable=False,
        description="User reached monthly research quota. Upgrade plan to continue.",
    )
    
    # Orphaned Task (503)
    ORPHANED_TASK = ErrorCodeDef(
        code="ORPHANED_TASK",
        http_status=503,
        retryable=True,
        description="Task lost heartbeat. Retry the request.",
    )
    
    # Validation Error (400)
    VALIDATION_ERROR = ErrorCodeDef(
        code="VALIDATION_ERROR",
        http_status=400,
        retryable=False,
        description="Invalid input parameters.",
    )
    
    # Internal Server Error (500)
    INTERNAL_ERROR = ErrorCodeDef(
        code="INTERNAL_ERROR",
        http_status=500,
        retryable=True,
        description="Internal server error. Can be retried.",
    )
    
    # Not Found (404)
    NOT_FOUND = ErrorCodeDef(
        code="NOT_FOUND",
        http_status=404,
        retryable=False,
        description="Requested resource not found.",
    )
    
    # Unauthorized (401)
    UNAUTHORIZED = ErrorCodeDef(
        code="UNAUTHORIZED",
        http_status=401,
        retryable=False,
        description="Authentication required or failed.",
    )
    
    # Forbidden (403)
    FORBIDDEN = ErrorCodeDef(
        code="FORBIDDEN",
        http_status=403,
        retryable=False,
        description="User does not have permission for this resource.",
    )
    
    @staticmethod
    def get_by_code(code: str) -> Optional[ErrorCodeDef]:
        """Look up error code definition by code string."""
        for attr_name in dir(ErrorCodes):
            if not attr_name.startswith("_"):
                attr = getattr(ErrorCodes, attr_name)
                if isinstance(attr, ErrorCodeDef) and attr.code == code:
                    return attr
        return None
    
    @staticmethod
    def all_codes() -> Dict[str, ErrorCodeDef]:
        """Get all error code definitions."""
        result = {}
        for attr_name in dir(ErrorCodes):
            if not attr_name.startswith("_"):
                attr = getattr(ErrorCodes, attr_name)
                if isinstance(attr, ErrorCodeDef):
                    result[attr.code] = attr
        return result
