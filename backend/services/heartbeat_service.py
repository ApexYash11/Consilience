"""
PHASE 3: Heartbeat service for keeping tasks alive during execution.

Periodically updates task heartbeat to prevent orphan detection.
Runs as a background task independent of individual research workflows.
"""

import asyncio
import logging
from datetime import datetime
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.connection import AsyncSessionLocal
from ..database.schema import ResearchTaskDB
from ..models.research import TaskStatus
from ..config.timeout_config import TASK_HEARTBEAT_INTERVAL_SECONDS
from .research_service import ResearchService

logger = logging.getLogger(__name__)


class HeartbeatService:
    """Service for managing task heartbeats during execution."""
    
    _heartbeat_tasks: dict[str, asyncio.Task] = {}
    _lock = asyncio.Lock()
    
    @staticmethod
    async def start_heartbeat(task_id: UUID) -> None:
        """
        PHASE 3: Start heartbeat for a task.
        
        Spawns a background task that periodically updates heartbeat
        until the task completes.
        
        Args:
            task_id: UUID of the task to heartbeat
        """
        task_id_str = str(task_id)
        
        async with HeartbeatService._lock:
            if task_id_str in HeartbeatService._heartbeat_tasks:
                logger.warning(f"[Phase 3] Heartbeat already active for task {task_id}")
                return
            
            # Create heartbeat coroutine
            heartbeat_coro = HeartbeatService._heartbeat_loop(task_id)
            heartbeat_task = asyncio.create_task(heartbeat_coro)
            HeartbeatService._heartbeat_tasks[task_id_str] = heartbeat_task
            
            logger.info(f"[Phase 3] Heartbeat started for task {task_id}")
    
    @staticmethod
    async def stop_heartbeat(task_id: UUID) -> None:
        """
        PHASE 3: Stop heartbeat for a task.
        
        Called when task completes (successfully or fails).
        
        Args:
            task_id: UUID of the task
        """
        task_id_str = str(task_id)
        
        async with HeartbeatService._lock:
            if task_id_str not in HeartbeatService._heartbeat_tasks:
                return
            
            task = HeartbeatService._heartbeat_tasks[task_id_str]
            task.cancel()
            
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning(f"[Phase 3] Error canceling heartbeat for task {task_id}: {e}")
            finally:
                del HeartbeatService._heartbeat_tasks[task_id_str]
                logger.info(f"[Phase 3] Heartbeat stopped for task {task_id}")
    
    @staticmethod
    async def _heartbeat_loop(task_id: UUID) -> None:
        """
        PHASE 3: Main heartbeat loop for a task.
        
        Runs indefinitely, updating task heartbeat every N seconds
        until task completes or is cancelled.
        
        Args:
            task_id: UUID of the task
        """
        logger.debug(f"[Phase 3] Heartbeat loop started for task {task_id}")
        
        try:
            while True:
                await asyncio.sleep(TASK_HEARTBEAT_INTERVAL_SECONDS)
                
                try:
                    # Get fresh session for this update
                    async with AsyncSessionLocal() as session:
                        # Update heartbeat
                        updated = await ResearchService.update_heartbeat(session, task_id)
                        
                        if updated is None:
                            logger.warning(f"[Phase 3] Task {task_id} not found during heartbeat update")
                            # Task disappeared - stop heartbeat
                            break
                        
                        # Check if task is terminal (completed/failed)
                        # Extract status value while still in session context
                        task_status = getattr(updated, 'status', None)
                        if task_status is not None:
                            if ResearchService.is_task_terminal(task_status):
                                logger.debug(f"[Phase 3] Task {task_id} is terminal ({task_status}), stopping heartbeat")
                                break
                                
                except Exception as e:
                    logger.error(f"[Phase 3] Error updating heartbeat for task {task_id}: {e}")
                    # Continue despite error - heartbeat is best-effort
                    continue
                    
        except asyncio.CancelledError:
            logger.debug(f"[Phase 3] Heartbeat loop cancelled for task {task_id}")
            raise
        except Exception as e:
            logger.error(f"[Phase 3] Unexpected error in heartbeat loop for task {task_id}: {e}")
        finally:
            logger.debug(f"[Phase 3] Heartbeat loop ended for task {task_id}")

    @staticmethod
    async def get_active_heartbeats() -> list[str]:
        """
        PHASE 3: Get all tasks with active heartbeats.
        
        Returns:
            List of task IDs (as strings)
        """
        async with HeartbeatService._lock:
            return list(HeartbeatService._heartbeat_tasks.keys())

    @staticmethod
    async def cleanup_all() -> None:
        """
        PHASE 3: Stop all active heartbeats.
        
        Called during application shutdown.
        """
        async with HeartbeatService._lock:
            task_ids = list(HeartbeatService._heartbeat_tasks.keys())
        
        for task_id_str in task_ids:
            try:
                task_id = UUID(task_id_str)
                await HeartbeatService.stop_heartbeat(task_id)
            except Exception as e:
                logger.error(f"[Phase 3] Error stopping heartbeat for {task_id_str}: {e}")
