"""
Workflow Instrumentation - Non-intrusive structured logging for research task execution.

Provides structured logging for:
- Task creation and lifecycle transitions
- Agent execution start/end
- LLM calls
- Database operations
- Error handling and recovery

Does NOT modify any business logic - purely for observability.
"""

import logging
import json
from typing import Any, Dict, Optional
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)


class WorkflowInstrumentation:
    """Non-intrusive structured logging for workflow execution."""
    
    # Task lifecycle events
    @staticmethod
    def log_task_created(
        task_id: UUID,
        user_id: UUID,
        topic: str,
        research_depth: str,
        estimated_cost: float,
    ) -> None:
        """Log task creation event."""
        logger.info(
            "workflow_event",
            extra={
                "event_type": "task_created",
                "task_id": str(task_id),
                "user_id": str(user_id),
                "topic": topic,
                "research_depth": research_depth,
                "estimated_cost": estimated_cost,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    @staticmethod
    def log_task_started(
        task_id: UUID,
        worker_id: str,
        deadline_seconds: Optional[int] = None,
    ) -> None:
        """Log task execution start."""
        logger.info(
            "workflow_event",
            extra={
                "event_type": "task_started",
                "task_id": str(task_id),
                "worker_id": worker_id,
                "deadline_seconds": deadline_seconds,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    @staticmethod
    def log_task_status_change(
        task_id: UUID,
        from_status: str,
        to_status: str,
        reason: Optional[str] = None,
    ) -> None:
        """Log task status transition."""
        logger.info(
            "workflow_event",
            extra={
                "event_type": "task_status_changed",
                "task_id": str(task_id),
                "from_status": from_status,
                "to_status": to_status,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    @staticmethod
    def log_task_completed(
        task_id: UUID,
        tokens_used: int,
        actual_cost: float,
        execution_time_seconds: float,
    ) -> None:
        """Log successful task completion."""
        logger.info(
            "workflow_event",
            extra={
                "event_type": "task_completed",
                "task_id": str(task_id),
                "tokens_used": tokens_used,
                "actual_cost": actual_cost,
                "execution_time_seconds": execution_time_seconds,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    @staticmethod
    def log_task_failed(
        task_id: UUID,
        error_code: str,
        error_message: str,
        execution_time_seconds: float,
    ) -> None:
        """Log task failure."""
        logger.error(
            "workflow_event",
            extra={
                "event_type": "task_failed",
                "task_id": str(task_id),
                "error_code": error_code,
                "error_message": error_message,
                "execution_time_seconds": execution_time_seconds,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    # Agent execution events
    @staticmethod
    def log_agent_started(
        task_id: UUID,
        agent_name: str,
        agent_type: str,
        step_number: Optional[int] = None,
    ) -> None:
        """Log agent execution start."""
        logger.info(
            "workflow_event",
            extra={
                "event_type": "agent_started",
                "task_id": str(task_id),
                "agent_name": agent_name,
                "agent_type": agent_type,
                "step_number": step_number,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    @staticmethod
    def log_agent_completed(
        task_id: UUID,
        agent_name: str,
        tokens_used: int,
        cost_usd: float,
        execution_time_seconds: float,
        output_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log successful agent completion."""
        logger.info(
            "workflow_event",
            extra={
                "event_type": "agent_completed",
                "task_id": str(task_id),
                "agent_name": agent_name,
                "tokens_used": tokens_used,
                "cost_usd": cost_usd,
                "execution_time_seconds": execution_time_seconds,
                "output_summary": output_summary,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    @staticmethod
    def log_agent_failed(
        task_id: UUID,
        agent_name: str,
        error_message: str,
        error_code: Optional[str] = None,
        execution_time_seconds: Optional[float] = None,
    ) -> None:
        """Log agent failure."""
        logger.error(
            "workflow_event",
            extra={
                "event_type": "agent_failed",
                "task_id": str(task_id),
                "agent_name": agent_name,
                "error_message": error_message,
                "error_code": error_code,
                "execution_time_seconds": execution_time_seconds,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    # LLM call events
    @staticmethod
    def log_llm_call_started(
        task_id: UUID,
        agent_name: str,
        model: str,
    ) -> None:
        """Log LLM call start."""
        logger.debug(
            "workflow_event",
            extra={
                "event_type": "llm_call_started",
                "task_id": str(task_id),
                "agent_name": agent_name,
                "model": model,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    @staticmethod
    def log_llm_call_completed(
        task_id: UUID,
        agent_name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        execution_time_seconds: float,
    ) -> None:
        """Log successful LLM call completion."""
        logger.debug(
            "workflow_event",
            extra={
                "event_type": "llm_call_completed",
                "task_id": str(task_id),
                "agent_name": agent_name,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "cost_usd": cost_usd,
                "execution_time_seconds": execution_time_seconds,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    @staticmethod
    def log_llm_call_rate_limited(
        task_id: UUID,
        agent_name: str,
        model: str,
        retry_after_seconds: Optional[int] = None,
    ) -> None:
        """Log LLM rate limit error."""
        logger.warning(
            "workflow_event",
            extra={
                "event_type": "llm_call_rate_limited",
                "task_id": str(task_id),
                "agent_name": agent_name,
                "model": model,
                "retry_after_seconds": retry_after_seconds,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    # Database operation events
    @staticmethod
    def log_db_write(
        task_id: UUID,
        operation: str,
        table: str,
        rows_affected: int,
        execution_time_ms: float,
    ) -> None:
        """Log database write operation."""
        logger.debug(
            "workflow_event",
            extra={
                "event_type": "db_write",
                "task_id": str(task_id),
                "operation": operation,
                "table": table,
                "rows_affected": rows_affected,
                "execution_time_ms": execution_time_ms,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    @staticmethod
    def log_db_error(
        task_id: UUID,
        operation: str,
        table: str,
        error_message: str,
        execution_time_ms: Optional[float] = None,
    ) -> None:
        """Log database operation failure."""
        logger.error(
            "workflow_event",
            extra={
                "event_type": "db_error",
                "task_id": str(task_id),
                "operation": operation,
                "table": table,
                "error_message": error_message,
                "execution_time_ms": execution_time_ms,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    # Heartbeat and recovery events
    @staticmethod
    def log_heartbeat_updated(
        task_id: UUID,
        worker_id: str,
    ) -> None:
        """Log heartbeat update."""
        logger.debug(
            "workflow_event",
            extra={
                "event_type": "heartbeat_updated",
                "task_id": str(task_id),
                "worker_id": worker_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    @staticmethod
    def log_orphan_task_detected(
        task_id: UUID,
        last_heartbeat_age_seconds: int,
    ) -> None:
        """Log orphaned task detection."""
        logger.warning(
            "workflow_event",
            extra={
                "event_type": "orphan_task_detected",
                "task_id": str(task_id),
                "last_heartbeat_age_seconds": last_heartbeat_age_seconds,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    @staticmethod
    def log_task_recovered(
        task_id: UUID,
        recovery_action: str,
        reason: str,
    ) -> None:
        """Log task recovery action."""
        logger.info(
            "workflow_event",
            extra={
                "event_type": "task_recovered",
                "task_id": str(task_id),
                "recovery_action": recovery_action,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    # Error and retry events
    @staticmethod
    def log_retry_attempted(
        task_id: UUID,
        agent_name: str,
        attempt_number: int,
        reason: str,
        max_retries: int,
    ) -> None:
        """Log retry attempt."""
        logger.info(
            "workflow_event",
            extra={
                "event_type": "retry_attempted",
                "task_id": str(task_id),
                "agent_name": agent_name,
                "attempt_number": attempt_number,
                "reason": reason,
                "max_retries": max_retries,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    @staticmethod
    def log_max_retries_exceeded(
        task_id: UUID,
        agent_name: str,
        max_retries: int,
        final_error: str,
    ) -> None:
        """Log max retries exceeded."""
        logger.error(
            "workflow_event",
            extra={
                "event_type": "max_retries_exceeded",
                "task_id": str(task_id),
                "agent_name": agent_name,
                "max_retries": max_retries,
                "final_error": final_error,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    # Quota and cost events
    @staticmethod
    def log_quota_check(
        task_id: UUID,
        user_id: UUID,
        quota_type: str,
        current_usage: int,
        quota_limit: int,
        passes_check: bool,
    ) -> None:
        """Log quota check result."""
        logger.info(
            "workflow_event",
            extra={
                "event_type": "quota_check",
                "task_id": str(task_id),
                "user_id": str(user_id),
                "quota_type": quota_type,
                "current_usage": current_usage,
                "quota_limit": quota_limit,
                "passes_check": passes_check,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    @staticmethod
    def log_cost_recorded(
        task_id: UUID,
        user_id: UUID,
        research_depth: str,
        tokens_used: int,
        cost_usd: float,
    ) -> None:
        """Log cost recording."""
        logger.info(
            "workflow_event",
            extra={
                "event_type": "cost_recorded",
                "task_id": str(task_id),
                "user_id": str(user_id),
                "research_depth": research_depth,
                "tokens_used": tokens_used,
                "cost_usd": cost_usd,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
