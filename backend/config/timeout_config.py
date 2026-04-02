"""
Phase 3: Global timeout system and task lifecycle configuration.

Manages:
- Workflow timeout limits
- Heartbeat intervals  
- Orphan task detection
- Worker identification
"""

import os
from datetime import timedelta

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
WORKFLOW_TIMEOUT_SECONDS = int(
    os.getenv("CONSILIENCE_WORKFLOW_TIMEOUT_SECONDS", "1800")  # Default: 30 minutes
)

# PHASE 3: Heartbeat interval (seconds)
# How often to update task heartbeat during execution
TASK_HEARTBEAT_INTERVAL_SECONDS = int(
    os.getenv("CONSILIENCE_TASK_HEARTBEAT_INTERVAL_SECONDS", "30")  # Default: 30 seconds
)

# PHASE 3: Task sweep interval (seconds)
# How often recovery service scans for orphaned/expired tasks
TASK_SWEEP_INTERVAL_SECONDS = int(
    os.getenv("CONSILIENCE_TASK_SWEEP_INTERVAL_SECONDS", "120")  # Default: 2 minutes
)

# PHASE 3: Orphan timeout threshold (seconds)
# If task hasn't been heartbeat in this time, consider it orphaned
TASK_ORPHAN_TIMEOUT_SECONDS = int(
    os.getenv("CONSILIENCE_TASK_ORPHAN_TIMEOUT_SECONDS", "300")  # Default: 5 minutes
)

# PHASE 3: Convert to timedelta for easier comparison
WORKFLOW_TIMEOUT_TIMEDELTA = timedelta(seconds=WORKFLOW_TIMEOUT_SECONDS)
HEARTBEAT_INTERVAL_TIMEDELTA = timedelta(seconds=TASK_HEARTBEAT_INTERVAL_SECONDS)
ORPHAN_TIMEOUT_TIMEDELTA = timedelta(seconds=TASK_ORPHAN_TIMEOUT_SECONDS)

__all__ = [
    "WORKER_ID",
    "WORKFLOW_TIMEOUT_SECONDS",
    "TASK_HEARTBEAT_INTERVAL_SECONDS",
    "TASK_SWEEP_INTERVAL_SECONDS",
    "TASK_ORPHAN_TIMEOUT_SECONDS",
    "WORKFLOW_TIMEOUT_TIMEDELTA",
    "HEARTBEAT_INTERVAL_TIMEDELTA",
    "ORPHAN_TIMEOUT_TIMEDELTA",
]
