"""
Phase 3: Global timeout system and task lifecycle configuration.

Manages:
- Workflow timeout limits
- Heartbeat intervals  
- Orphan task detection
- Worker identification
"""

import os
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


def parse_int_env(var_name: str, default: int) -> int:
    """
    Parse an integer environment variable with graceful error handling.
    
    Args:
        var_name: Name of environment variable to read
        default: Default value if not set or invalid
        
    Returns:
        Parsed integer value or default
        
    Raises:
        ValueError: If var_name is explicitly set but invalid
    """
    value = os.getenv(var_name)
    if value is None:
        return default
    
    try:
        return int(value)
    except ValueError:
        logger.error(
            f"Invalid value for {var_name}: expected integer, got '{value}'. "
            f"Using default: {default}"
        )
        return default


# PHASE 3: Get worker identification for multi-worker environments
WORKER_ID = os.getenv(
    "CONSILIENCE_WORKER_ID",
    default=None
)

# If not set, use hostname as fallback
if not WORKER_ID:
    import socket
    try:
        WORKER_ID = socket.gethostname()
    except Exception:
        WORKER_ID = "unknown-worker"

# PHASE 3: Global workflow timeout (seconds)
# Maximum time allowed for entire research workflow
WORKFLOW_TIMEOUT_SECONDS = parse_int_env(
    "CONSILIENCE_WORKFLOW_TIMEOUT_SECONDS", 
    1800  # Default: 30 minutes
)

# PHASE 3: Heartbeat interval (seconds)
# How often to update task heartbeat during execution
TASK_HEARTBEAT_INTERVAL_SECONDS = parse_int_env(
    "CONSILIENCE_TASK_HEARTBEAT_INTERVAL_SECONDS",
    30  # Default: 30 seconds
)

# PHASE 3: Task sweep interval (seconds)
# How often recovery service scans for orphaned/expired tasks
TASK_SWEEP_INTERVAL_SECONDS = parse_int_env(
    "CONSILIENCE_TASK_SWEEP_INTERVAL_SECONDS",
    120  # Default: 2 minutes
)

# PHASE 3: Orphan timeout threshold (seconds)
# If task hasn't been heartbeat in this time, consider it orphaned
TASK_ORPHAN_TIMEOUT_SECONDS = parse_int_env(
    "CONSILIENCE_TASK_ORPHAN_TIMEOUT_SECONDS",
    300  # Default: 5 minutes
)

# PHASE 3: Convert to timedelta for easier comparison
WORKFLOW_TIMEOUT_TIMEDELTA = timedelta(seconds=WORKFLOW_TIMEOUT_SECONDS)
HEARTBEAT_INTERVAL_TIMEDELTA = timedelta(seconds=TASK_HEARTBEAT_INTERVAL_SECONDS)
ORPHAN_TIMEOUT_TIMEDELTA = timedelta(seconds=TASK_ORPHAN_TIMEOUT_SECONDS)

# ============================================================================
# PHASE 5: Detector Performance Optimization Configuration
# ============================================================================

# Maximum number of source pair comparisons before sampling kicks in (LLM cost optimization)
DETECTOR_MAX_COMPARISONS = parse_int_env(
    "CONSILIENCE_DETECTOR_MAX_COMPARISONS", 
    150  # Default: compare max 150 pairs for 100+ sources
)

# Maximum concurrent detector comparisons (async batching control)
DETECTOR_MAX_CONCURRENCY = parse_int_env(
    "CONSILIENCE_DETECTOR_MAX_CONCURRENCY",
    5  # Default: 5 concurrent comparisons
)

# Minimum comparisons to include (prevents overly aggressive sampling)
# Clamp to ensure min never exceeds max
base_min = max(10, DETECTOR_MAX_COMPARISONS // 5)
DETECTOR_MIN_COMPARISONS = min(base_min, DETECTOR_MAX_COMPARISONS)

__all__ = [
    "WORKER_ID",
    "WORKFLOW_TIMEOUT_SECONDS",
    "TASK_HEARTBEAT_INTERVAL_SECONDS",
    "TASK_SWEEP_INTERVAL_SECONDS",
    "TASK_ORPHAN_TIMEOUT_SECONDS",
    "WORKFLOW_TIMEOUT_TIMEDELTA",
    "HEARTBEAT_INTERVAL_TIMEDELTA",
    "ORPHAN_TIMEOUT_TIMEDELTA",
    "DETECTOR_MAX_COMPARISONS",
    "DETECTOR_MAX_CONCURRENCY",
    "DETECTOR_MIN_COMPARISONS",
]
