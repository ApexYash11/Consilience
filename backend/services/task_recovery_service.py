"""
Task recovery service for handling orphaned and stale tasks.

Problem 2: Orphaned Tasks
- Detects tasks stuck in RUNNING status after a server crash
- Updates heartbeats for active tasks
- Marks orphaned tasks as FAILED with reason
- Implements startup recovery sweep
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.connection import AsyncSessionLocal
from ..database.schema import ResearchTaskDB
from ..models.research import TaskStatus

logger = logging.getLogger(__name__)


class TaskRecoveryService:
    """Handles detection and recovery of orphaned research tasks."""

    # Configuration (typically from settings, but hardcoded for now)
    HEARTBEAT_INTERVAL_SECONDS = 30  # Update heartbeat every 30s
    ORPHAN_TIMEOUT_SECONDS = 300  # 5 minutes with no heartbeat = orphaned
    CLEANUP_INTERVAL_SECONDS = 120  # Sweep for orphans every 2 minutes

    # Private class state for background tasks
    _heartbeat_task: Optional[asyncio.Task] = None
    _recovery_sweep_task: Optional[asyncio.Task] = None
    _is_running = False
    
    # Track which tasks this server instance is actively processing
    # Only we refresh heartbeats for these; orphan detection handles stale ones
    _active_task_ids: set = set()  # Set of task IDs currently being processed

    @classmethod
    async def startup(cls) -> None:
        """
        Called on app startup.
        - Performs initial recovery sweep for tasks orphaned by server crash
        - Starts background heartbeat and recovery tasks
        """
        logger.info("TaskRecoveryService: Starting up")
        
        # Step 1: Initial recovery sweep for crashed tasks
        await cls._initial_recovery_sweep()
        
        # Step 2: Start background tasks
        cls._is_running = True
        cls._heartbeat_task = asyncio.create_task(cls._background_heartbeat_loop())
        cls._recovery_sweep_task = asyncio.create_task(cls._background_recovery_sweep_loop())
        
        logger.info("TaskRecoveryService: Startup complete")

    @classmethod
    async def shutdown(cls) -> None:
        """Called on app shutdown. Clears active task tracking and cancels background tasks."""
        logger.info("TaskRecoveryService: Shutting down")
        cls._is_running = False
        
        # Clear active task tracking (on server shutdown, no more tasks are "active")
        cls._active_task_ids.clear()
        
        # Cancel and wait for background tasks to finish
        tasks_to_cancel = []
        if cls._heartbeat_task:
            cls._heartbeat_task.cancel()
            tasks_to_cancel.append(cls._heartbeat_task)
        if cls._recovery_sweep_task:
            cls._recovery_sweep_task.cancel()
            tasks_to_cancel.append(cls._recovery_sweep_task)
        
        # Wait for all tasks to finish, catching CancelledError
        if tasks_to_cancel:
            results = await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
            for result in results:
                if isinstance(result, asyncio.CancelledError):
                    pass  # Expected
                elif isinstance(result, Exception):
                    logger.warning(f"TaskRecoveryService: Task shutdown exception: {result}")
        
        logger.info("TaskRecoveryService: Shutdown complete")

    @classmethod
    async def update_heartbeat(cls, task_id: str) -> None:
        """
        Update the heartbeat timestamp for a running task.
        Called periodically by agents/orchestrators to signal task is still alive.
        """
        try:
            # Track this task as active (we're processing it)
            cls._active_task_ids.add(task_id)
            
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(ResearchTaskDB)
                    .where(ResearchTaskDB.id == task_id)
                    .values(last_heartbeat=datetime.utcnow())
                )
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to update heartbeat for task {task_id}: {e}")

    @classmethod
    def mark_task_completed(cls, task_id: str) -> None:
        """
        Mark a task as completed/no longer active on this server.
        Call when task finishes (success or failure) to stop tracking it.
        """
        cls._active_task_ids.discard(task_id)
        logger.debug(f"TaskRecoveryService: Removed task {task_id} from active tracking")

    @classmethod
    async def _initial_recovery_sweep(cls) -> None:
        """
        On startup, find tasks in RUNNING status and mark them as FAILED.
        These are tasks orphaned by a server crash.
        """
        try:
            async with AsyncSessionLocal() as session:
                # Find all tasks in RUNNING status
                result = await session.execute(
                    select(ResearchTaskDB).where(ResearchTaskDB.status == TaskStatus.RUNNING)
                )
                orphaned_tasks = result.scalars().all()
                
                if orphaned_tasks:
                    logger.warning(
                        f"TaskRecoveryService: Found {len(orphaned_tasks)} orphaned tasks on startup"
                    )
                    
                    # Mark each as FAILED with recovery reason
                    for task in orphaned_tasks:
                        task.status = TaskStatus.FAILED  # type: ignore
                        task.failure_reason = (  # type: ignore
                            "Task orphaned due to server restart. "
                            "Task was in RUNNING status when server crashed."
                        )
                        task.completed_at = datetime.utcnow()  # type: ignore
                        logger.info(f"TaskRecoveryService: Marked task {task.id} as FAILED (orphaned)")
                    
                    await session.commit()
                    logger.info(
                        f"TaskRecoveryService: Recovery sweep marked {len(orphaned_tasks)} tasks as FAILED"
                    )
        except Exception as e:
            logger.error(f"TaskRecoveryService: Initial recovery sweep failed: {e}")

    @classmethod
    async def _background_heartbeat_loop(cls) -> None:
        """
        Background task that periodically refreshes heartbeats for actively tracked tasks.
        Only refreshes tasks this server is actually processing to allow orphan detection.
        Relies on agents calling update_heartbeat() for worker-driven heartbeats.
        """
        while cls._is_running:
            try:
                await asyncio.sleep(cls.HEARTBEAT_INTERVAL_SECONDS)
                
                # Only refresh heartbeats for tasks we're actively tracking
                # This allows orphaned tasks (not being worked on) to be detected
                if cls._active_task_ids:
                    async with AsyncSessionLocal() as session:
                        await session.execute(
                            update(ResearchTaskDB)
                            .where(
                                (ResearchTaskDB.status == TaskStatus.RUNNING) &
                                (ResearchTaskDB.id.in_(cls._active_task_ids))
                            )
                            .values(last_heartbeat=datetime.utcnow())
                        )
                        await session.commit()
                        logger.debug(
                            f"TaskRecoveryService: Heartbeat loop refreshed {len(cls._active_task_ids)} active tasks"
                        )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"TaskRecoveryService: Heartbeat loop error: {e}")

    @classmethod
    async def _background_recovery_sweep_loop(cls) -> None:
        """
        Background task that periodically scans for orphaned tasks.
        Called every CLEANUP_INTERVAL_SECONDS to detect tasks with stale heartbeats.
        """
        while cls._is_running:
            try:
                await asyncio.sleep(cls.CLEANUP_INTERVAL_SECONDS)
                await cls._recovery_sweep()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"TaskRecoveryService: Recovery sweep error: {e}")

    @classmethod
    async def _recovery_sweep(cls) -> None:
        """
        Scan for tasks in RUNNING status whose heartbeat has gone stale.
        Mark them as FAILED with orphan reason.
        """
        try:
            now = datetime.utcnow()
            orphan_threshold = now - timedelta(seconds=cls.ORPHAN_TIMEOUT_SECONDS)
            
            async with AsyncSessionLocal() as session:
                # Find RUNNING tasks with stale heartbeat
                # Grace period: tasks with NULL heartbeat are only orphaned if older than 30s
                grace_period_threshold = now - timedelta(seconds=30)
                result = await session.execute(
                    select(ResearchTaskDB).where(
                        (ResearchTaskDB.status == TaskStatus.RUNNING) &
                        (
                            ((ResearchTaskDB.last_heartbeat.is_(None)) &  # type: ignore
                             (ResearchTaskDB.created_at < grace_period_threshold)) |
                            (ResearchTaskDB.last_heartbeat < orphan_threshold)
                        )
                    )
                )
                stale_tasks = result.scalars().all()
                
                if stale_tasks:
                    logger.warning(
                        f"TaskRecoveryService: Found {len(stale_tasks)} stale tasks during sweep"
                    )
                    
                    for task in stale_tasks:
                        task.status = TaskStatus.FAILED  # type: ignore
                        task.failure_reason = (  # type: ignore
                            f"Task orphaned: No heartbeat for {cls.ORPHAN_TIMEOUT_SECONDS}s. "
                            "Last heartbeat at: "
                            f"{task.last_heartbeat.isoformat() if task.last_heartbeat is not None else 'never'}"
                        )
                        task.completed_at = datetime.utcnow()  # type: ignore
                        logger.info(
                            f"TaskRecoveryService: Marked stale task {task.id} as FAILED "
                            f"(heartbeat: {task.last_heartbeat})"
                        )
                    
                    await session.commit()
                    logger.info(
                        f"TaskRecoveryService: Sweep marked {len(stale_tasks)} tasks as FAILED"
                    )
        except Exception as e:
            logger.error(f"TaskRecoveryService: Recovery sweep failed: {e}")

    @classmethod
    def is_running(cls) -> bool:
        """Check if background tasks are active."""
        return cls._is_running
