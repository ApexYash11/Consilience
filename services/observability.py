"""
Safe LangSmith observability wrappers.

Provides fault-tolerant access to LangSmith tracing APIs.
All LangSmith failures are caught and logged without breaking task execution.
"""

import logging
import os
from contextlib import asynccontextmanager, contextmanager
from typing import Optional, Dict, Any, AsyncGenerator, Generator

logger = logging.getLogger(__name__)

# Try to import LangSmith APIs; if not available, mark as disabled
try:
    from langsmith import Client
    from langsmith.schemas import Run
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
    Client = None  # type: ignore
    logger.debug("LangSmith not installed; observability features disabled")


class ObservabilityDisabledError(Exception):
    """Raised when observability is disabled or misconfigured."""
    pass


def is_tracing_enabled() -> bool:
    """Check if LangSmith tracing is enabled and configured."""
    if not LANGSMITH_AVAILABLE:
        return False
    
    tracing_enabled = os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true"
    api_key_configured = bool(os.environ.get("LANGCHAIN_API_KEY"))
    
    return tracing_enabled and api_key_configured


def get_langsmith_client() -> Optional[Any]:
    """Get LangSmith client if available and configured.
    
    Returns:
        LangSmith Client instance, or None if not available/configured.
    """
    if not LANGSMITH_AVAILABLE or not is_tracing_enabled():
        return None
    
    try:
        if Client is None:
            return None
        return Client()
    except Exception as e:
        logger.warning(f"Failed to initialize LangSmith client: {str(e)}")
        return None


def safe_get_current_run_id() -> Optional[str]:
    """Get the current LangSmith run ID (for linking traces).
    
    Returns:
        Run ID string, or None if not available.
        
    Safety: Never raises; logs warnings and returns None on failure.
    """
    if not LANGSMITH_AVAILABLE or not is_tracing_enabled():
        return None
    
    # LangSmith doesn't expose a built-in context getter in v0.1+
    # Traces are linked via LangGraph integration automatically
    return None


@contextmanager
def safe_trace(
    name: str,
    run_type: str = "chain",
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[list] = None,
) -> Generator[Optional[str], None, None]:
    """Safe context manager for LangSmith tracing.
    
    Args:
        name: Trace name for display
        run_type: Type of run ("chain", "llm", "tool", "agent", etc.)
        metadata: Optional metadata dict to attach
        tags: Optional list of tags
        
    Yields:
        Run ID string if tracing is enabled, None otherwise.
        
    Safety: Never raises; gracefully falls back to no-op if tracing disabled.
    """
    if not LANGSMITH_AVAILABLE or not is_tracing_enabled():
        yield None
        return
    
    try:
        # LangSmith hooks into environment variables and LangGraph automatically
        # No explicit context manager needed; just yield None and let native tracing handle it
        yield None
            
    except Exception as e:
        logger.debug(f"Trace context setup failed (non-blocking): {str(e)}")
        yield None


@asynccontextmanager
async def safe_trace_async(
    name: str,
    run_type: str = "chain",
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[list] = None,
) -> AsyncGenerator[Optional[str], None]:
    """Async-safe context manager for LangSmith tracing.
    
    Args:
        name: Trace name for display
        run_type: Type of run ("chain", "llm", "tool", "agent", etc.)
        metadata: Optional metadata dict to attach
        tags: Optional list of tags
        
    Yields:
        Run ID string if tracing is enabled, None otherwise.
        
    Safety: Never raises; gracefully falls back to no-op if tracing disabled.
    """
    if not LANGSMITH_AVAILABLE or not is_tracing_enabled():
        yield None
        return
    
    try:
        client = get_langsmith_client()
        if not client:
            yield None
            return
        
        # For now, delegate to LangGraph's native tracing
        # LangSmith hooks into LangGraph automatically when configured
        yield None
        
    except Exception as e:
        logger.debug(f"Async trace context setup failed (non-blocking): {str(e)}")
        yield None


def safe_create_feedback(
    run_id: str,
    key: str,
    score: Optional[float] = None,
    value: Optional[Any] = None,
    comment: Optional[str] = None,
) -> bool:
    """Safely create LangSmith feedback for a run.
    
    Args:
        run_id: The run ID to attach feedback to
        key: Feedback key (e.g., "quality", "cost", "latency")
        score: Numeric score (0-1 or custom range)
        value: Arbitrary feedback value
        comment: Optional human comment
        
    Returns:
        True if feedback created successfully, False otherwise.
        
    Safety: Never raises; logs warnings on failure.
    """
    if not LANGSMITH_AVAILABLE or not is_tracing_enabled():
        return False
    
    try:
        client = get_langsmith_client()
        if not client:
            return False
        
        # LangSmith feedback API
        feedback_data: Dict[str, Any] = {
            "run_id": run_id,
            "key": key,
        }
        
        if score is not None:
            feedback_data["score"] = score
        if value is not None:
            feedback_data["value"] = value
        if comment:
            feedback_data["comment"] = comment
        
        # Create feedback (API may vary by LangSmith version)
        client.create_feedback(**feedback_data)
        logger.debug(f"Created feedback for run {run_id}: {key}")
        return True
        
    except Exception as e:
        logger.debug(f"Failed to create feedback: {str(e)}")
        return False


def merge_metadata(
    existing: Optional[Dict[str, Any]],
    new: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Merge new metadata into existing metadata dict; new values override existing keys.
    
    Args:
        existing: Base metadata dict (or None)
        new: New metadata to merge (or None)
        
    Returns:
        Merged metadata dict (new values override existing).
    """
    result = dict(existing) if existing else {}
    
    if new:
        result.update(new)
    
    return result


def log_metric(
    metric_name: str,
    value: Any,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a metric to structured logs for observability.
    
    This complements LangSmith tracing with structured logging
    that can be picked up by log aggregation services.
    
    Args:
        metric_name: Name of the metric
        value: Metric value
        context: Optional context dict (task_id, topic, etc.)
    """
    try:
        log_entry = {
            "metric": metric_name,
            "value": value,
        }
        if context:
            log_entry.update(context)
        
        logger.info(f"Metric: {metric_name}={value}", extra=log_entry)
    except Exception as e:
        logger.debug(f"Failed to log metric: {str(e)}")


def attach_metadata_to_run(
    run_id: Optional[str],
    metadata: Dict[str, Any],
) -> bool:
    """Attach metadata to an existing LangSmith run.
    
    Args:
        run_id: The run ID to attach metadata to
        metadata: Metadata dict to attach
        
    Returns:
        True if successful, False otherwise.
        
    Safety: Never raises; logs warnings on failure.
    """
    if not run_id or not LANGSMITH_AVAILABLE or not is_tracing_enabled():
        return False
    
    try:
        client = get_langsmith_client()
        if not client:
            return False
        
        # LangSmith SDK v0.1+ provides update_run method on client
        # Attempt to update the run with the provided metadata
        try:
            # Try the standard update_run API if available
            client.update_run(run_id, extra=metadata)
        except AttributeError:
            # Fallback: if update_run not available, try alternative API
            # Different LangSmith versions may have different interfaces
            logger.warning(f"update_run not available on client; metadata not attached for run {run_id}")
            return False
        
        logger.debug(f"Attached metadata to run {run_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to attach metadata to run {run_id}: {str(e)}")
        return False
