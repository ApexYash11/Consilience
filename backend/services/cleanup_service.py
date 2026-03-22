"""
Cleanup service for managing research context files and directories.

Provides functionality to delete old research context directories to prevent
disk bloat in long-running deployments.
"""

import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Configuration
RESEARCH_CONTEXT_DIR = Path("research_context")
TTL_DAYS = 30  # Delete files older than 30 days


async def cleanup_old_research_context() -> int:
    """
    Delete research_context/ directories older than TTL_DAYS.

    This function is typically called during API startup to clean up stale
    research data from previous deployments.

    Returns:
        Number of directories deleted

    Raises:
        None (errors are logged, not raised)
    """
    if not RESEARCH_CONTEXT_DIR.exists():
        logger.info(f"Research context directory {RESEARCH_CONTEXT_DIR} does not exist, skipping cleanup")
        return 0

    cutoff_time = datetime.utcnow() - timedelta(days=TTL_DAYS)
    deleted_count = 0
    error_count = 0

    logger.info(f"Starting cleanup of research context directories older than {TTL_DAYS} days (cutoff: {cutoff_time.isoformat()})")

    try:
        for task_dir in RESEARCH_CONTEXT_DIR.iterdir():
            if not task_dir.is_dir():
                continue

            try:
                # Get directory modification time
                mod_time = datetime.utcfromtimestamp(task_dir.stat().st_mtime)

                if mod_time < cutoff_time:
                    shutil.rmtree(task_dir)
                    logger.info(f"Deleted old research context: {task_dir.name} (modified: {mod_time.isoformat()})")
                    deleted_count += 1
            except PermissionError as e:
                logger.warning(f"Permission denied when deleting {task_dir.name}: {e}")
                error_count += 1
            except Exception as e:
                logger.error(f"Failed to delete {task_dir.name}: {e}", exc_info=True)
                error_count += 1

    except Exception as e:
        logger.error(f"Cleanup failed with unexpected error: {e}", exc_info=True)
        return deleted_count

    logger.info(f"Cleanup complete: deleted {deleted_count} directories, {error_count} errors")
    return deleted_count


def get_research_context_stats() -> dict:
    """
    Get statistics about research context directory.

    Returns:
        Dictionary with:
        - total_dirs: Number of research context directories
        - total_size_mb: Total size in megabytes
        - oldest_dir: Name of oldest directory (if any)
        - oldest_time_days: Age of oldest directory in days
    """
    if not RESEARCH_CONTEXT_DIR.exists():
        return {
            "total_dirs": 0,
            "total_size_mb": 0.0,
            "oldest_dir": None,
            "oldest_time_days": None,
        }

    total_dirs = 0
    total_size = 0
    oldest_time = None
    oldest_dir_name = None

    try:
        for task_dir in RESEARCH_CONTEXT_DIR.iterdir():
            if not task_dir.is_dir():
                continue

            total_dirs += 1
            mod_time = datetime.utcfromtimestamp(task_dir.stat().st_mtime)

            if oldest_time is None or mod_time < oldest_time:
                oldest_time = mod_time
                oldest_dir_name = task_dir.name

            # Calculate directory size recursively
            for root, dirs, files in os.walk(task_dir):
                for file in files:
                    filepath = os.path.join(root, file)
                    try:
                        total_size += os.path.getsize(filepath)
                    except OSError:
                        pass
    except Exception as e:
        logger.error(f"Failed to calculate research context stats: {e}")
        return {
            "total_dirs": total_dirs,
            "total_size_mb": 0.0,
            "oldest_dir": None,
            "oldest_time_days": None,
            "error": str(e),
        }

    oldest_time_days = None
    if oldest_time:
        oldest_time_days = (datetime.utcnow() - oldest_time).days

    return {
        "total_dirs": total_dirs,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "oldest_dir": oldest_dir_name,
        "oldest_time_days": oldest_time_days,
    }
