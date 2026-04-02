"""Research service logic for task management and orchestration."""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, select

from ..database.schema import (
    ResearchTaskDB,
    AgentActionDB,
    TokenUsageLogDB,
    ResearchCheckpointDB,
)
from ..models.research import TaskStatus, ResearchDepth, ResearchState
from ..config.timeout_config import WORKER_ID, WORKFLOW_TIMEOUT_TIMEDELTA
import logging

logger = logging.getLogger(__name__)


class ResearchService:
    """Service for managing research tasks and agent actions."""

    @staticmethod
    async def save_research_task(
        session: AsyncSession,
        user_id: UUID,
        topic: str,
        research_depth: ResearchDepth = ResearchDepth.STANDARD,
        title: Optional[str] = None,
        description: Optional[str] = None,
        config_json: Optional[Dict[str, Any]] = None,
        estimated_cost_usd: Optional[float] = None,
    ) -> ResearchTaskDB:
        """
        Save a new research task to the database.

        Args:
            session: AsyncSession for database operations
            user_id: UUID of the user initiating the task
            topic: Research topic
            research_depth: STANDARD or DEEP
            title: Optional task title (defaults to topic)
            description: Optional task description
            config_json: Optional research configuration
            estimated_cost_usd: Optional cost estimate

        Returns:
            ResearchTaskDB: Persisted task object
        """
        task = ResearchTaskDB(
            user_id=user_id,
            title=title or topic,
            description=description or f"Research task for: {topic}",
            research_depth=research_depth,
            config_json=config_json or {},
            status=TaskStatus.PENDING,
            estimated_cost_usd=estimated_cost_usd,
        )
        session.add(task)
        await session.flush()
        await session.commit()
        logger.info(f"Created research task {task.id} for user {user_id}")
        return task

    @staticmethod
    async def get_research_task(
        session: AsyncSession,
        task_id: UUID,
    ) -> Optional[ResearchTaskDB]:
        """
        Retrieve a research task by ID.

        Args:
            session: AsyncSession for database operations
            task_id: UUID of the task

        Returns:
            ResearchTaskDB or None if not found
        """
        from sqlalchemy import select

        result = await session.execute(
            select(ResearchTaskDB).where(ResearchTaskDB.id == task_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_research_tasks(
        session: AsyncSession,
        user_id: UUID,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[ResearchTaskDB], int]:
        """
        Retrieve paginated research tasks for a user, ordered by created_at descending.

        Args:
            session: AsyncSession for database operations
            user_id: UUID of the user
            page: Page number (1-indexed)
            page_size: Number of tasks per page

        Returns:
            Tuple of (task list, total count)
        """
        from sqlalchemy import select, func, desc

        # Validate pagination parameters
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1:
            raise ValueError("page_size must be >= 1")

        # Get total count
        count_result = await session.execute(
            select(func.count(ResearchTaskDB.id)).where(
                ResearchTaskDB.user_id == user_id
            )
        )
        total_count = count_result.scalar() or 0

        # Get paginated results
        offset = (page - 1) * page_size
        result = await session.execute(
            select(ResearchTaskDB)
            .where(ResearchTaskDB.user_id == user_id)
            .order_by(desc(ResearchTaskDB.created_at))
            .offset(offset)
            .limit(page_size)
        )
        tasks = list(result.scalars().all())
        
        return tasks, total_count

    @staticmethod
    async def update_research_task_with_retry(
        session: AsyncSession,
        task_id: UUID,
        status: Optional[TaskStatus] = None,
        actual_cost_usd: Optional[float] = None,
        tokens_used: Optional[int] = None,
        final_state: Optional[ResearchState] = None,
        error_message: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Optional[ResearchTaskDB]:
        """
        PHASE 2 FIX: Update research task with optimistic locking and retry.
        
        Uses row_version column for safe concurrent updates. If a concurrent
        write occurs, this method will retry up to max_retries times, re-fetching
        the latest state and re-applying the update.
        
        Args:
            session: AsyncSession for database operations
            task_id: UUID of the task
            status: New task status
            actual_cost_usd: Final cost
            tokens_used: Total tokens
            final_state: ResearchState with results
            error_message: Error details
            metadata_json: Additional metadata
            max_retries: Maximum retry attempts (default 3)
        
        Returns:
            Updated ResearchTaskDB or None if not found
        """
        for attempt in range(max_retries):
            try:
                # Fetch current task state (gets current row_version)
                task = await ResearchService.get_research_task(session, task_id)
                if not task:
                    return None
                
                # Get current row_version before modification
                current_version = getattr(task, 'row_version', 0) or 0
                
                # Build update dict with only the fields being changed
                update_dict = {}
                
                if status is not None:
                    update_dict['status'] = status
                    # Update timing based on status
                    if status == TaskStatus.RUNNING and (not hasattr(task, 'started_at') or task.started_at is None):
                        update_dict['started_at'] = datetime.utcnow()
                    elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                        update_dict['completed_at'] = datetime.utcnow()
                
                if actual_cost_usd is not None:
                    update_dict['actual_cost_usd'] = actual_cost_usd
                
                if tokens_used is not None:
                    update_dict['tokens_used'] = tokens_used
                
                if final_state:
                    update_dict['final_state_json'] = final_state.dict()
                
                if error_message:
                    update_dict['error_message'] = error_message
                
                if metadata_json:
                    update_dict['metadata_json'] = metadata_json
                
                # Increment row_version for optimistic lock
                update_dict['row_version'] = current_version + 1
                
                # Execute UPDATE with optimistic lock condition
                # Only update if row_version matches what we read
                stmt = (
                    update(ResearchTaskDB)
                    .where(ResearchTaskDB.id == task_id)
                    .where(ResearchTaskDB.row_version == current_version)
                    .values(**update_dict)
                )
                
                result = await session.execute(stmt)
                await session.commit()
                
                if result.rowcount == 0:
                    # Optimistic lock failed - another writer modified this row
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Optimistic lock conflict on task {task_id}, attempt {attempt + 1}/{max_retries}. Retrying..."
                        )
                        # Refresh session to discard stale state
                        await session.rollback()
                        continue
                    else:
                        logger.error(
                            f"Optimistic lock conflict on task {task_id} after {max_retries} retries. Giving up."
                        )
                        return None
                
                # Success - fetch updated task and return
                task = await ResearchService.get_research_task(session, task_id)
                logger.info(f"Updated research task {task_id} to status {status} (row_version={current_version} -> {current_version + 1})")
                return task
                
            except Exception as e:
                logger.error(f"Error updating research task {task_id} (attempt {attempt + 1}/{max_retries}): {e}")
                await session.rollback()
                if attempt == max_retries - 1:
                    raise
                # Retry on any exception
                continue
        
        return None

    @staticmethod
    async def update_research_task(
        session: AsyncSession,
        task_id: UUID,
        status: Optional[TaskStatus] = None,
        actual_cost_usd: Optional[float] = None,
        tokens_used: Optional[int] = None,
        final_state: Optional[ResearchState] = None,
        error_message: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> Optional[ResearchTaskDB]:
        """
        Update a research task's status and results.

        Args:
            session: AsyncSession for database operations
            task_id: UUID of the task
            status: New task status
            actual_cost_usd: Final cost (overrides estimate)
            tokens_used: Total tokens consumed
            final_state: ResearchState with results (serialized as JSON)
            error_message: Error details if task failed
            metadata_json: Additional metadata

        Returns:
            Updated ResearchTaskDB or None if not found
        """
        task = await ResearchService.get_research_task(session, task_id)
        if not task:
            return None

        # Update basic fields
        if status is not None:
            task.status = status  # type: ignore
        if actual_cost_usd is not None:
            task.actual_cost_usd = actual_cost_usd  # type: ignore
        if tokens_used is not None:
            task.tokens_used = tokens_used  # type: ignore

        # Update timing
        if status == TaskStatus.RUNNING and task.started_at is None:  # type: ignore
            task.started_at = datetime.utcnow()  # type: ignore
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            task.completed_at = datetime.utcnow()  # type: ignore

        # Store final state separately to avoid overwriting metadata_json
        if final_state:
            task.final_state_json = final_state.dict()  # type: ignore

        # Store error
        if error_message:
            task.error_message = error_message  # type: ignore

        # Store additional metadata
        if metadata_json:
            task.metadata_json = metadata_json  # type: ignore

        await session.commit()
        logger.info(f"Updated research task {task_id} to status {status}")
        return task

    @staticmethod
    async def delete_research_task(
        session: AsyncSession,
        task_id: UUID,
    ) -> bool:
        """
        Delete a research task and all associated records.

        Args:
            session: AsyncSession for database operations
            task_id: UUID of the task to delete

        Returns:
            True if task was deleted, False if not found
        """
        from sqlalchemy import delete
        
        # First delete associated records
        await session.execute(
            delete(ResearchCheckpointDB).where(ResearchCheckpointDB.task_id == task_id)
        )
        await session.execute(
            delete(AgentActionDB).where(AgentActionDB.task_id == task_id)
        )
        await session.execute(
            delete(TokenUsageLogDB).where(TokenUsageLogDB.task_id == task_id)
        )
        
        # Then delete the task itself
        result = await session.execute(
            delete(ResearchTaskDB).where(ResearchTaskDB.id == task_id)
        )
        await session.commit()
        
        deleted_count = result.rowcount or 0
        if deleted_count > 0:
            logger.info(f"Deleted research task {task_id}")
        
        return deleted_count > 0

    @staticmethod
    async def log_agent_action(
        session: AsyncSession,
        task_id: UUID,
        agent_name: str,
        agent_type: str,
        action: str,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        error: Optional[str] = None,
    ) -> AgentActionDB:
        """
        Log an individual agent's action to the agent_actions table.

        Args:
            session: AsyncSession for database operations
            task_id: UUID of the parent research task
            agent_name: Name of the agent (e.g., 'planner', 'researcher_0')
            agent_type: Type of agent (e.g., 'planner', 'researcher', 'verifier')
            action: Action performed (e.g., 'plan_queries', 'search_sources')
            input_data: Input to the agent
            output_data: Output from the agent
            tokens_used: Token count for this action
            cost_usd: Cost for this action
            error: Error message if action failed

        Returns:
            AgentActionDB: Persisted agent action record
        """
        agent_action = AgentActionDB(
            task_id=task_id,
            agent_name=agent_name,
            agent_type=agent_type,
            action=action,
            input_data_json=input_data,
            output_data_json=output_data,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            error=error,
        )
        session.add(agent_action)
        await session.flush()
        await session.commit()
        logger.debug(
            f"Logged agent action: {agent_name}.{action} (tokens: {tokens_used}, cost: ${cost_usd:.4f})"
        )
        return agent_action

    @staticmethod
    async def get_agent_actions(
        session: AsyncSession,
        task_id: UUID,
    ) -> list:  # type: ignore
        """
        Retrieve all agent actions for a task.

        Args:
            session: AsyncSession for database operations
            task_id: UUID of the task

        Returns:
            List of AgentActionDB records
        """
        from sqlalchemy import select

        result = await session.execute(
            select(AgentActionDB)
            .where(AgentActionDB.task_id == task_id)
            .order_by(AgentActionDB.started_at)
        )
        return list(result.scalars().all())

    @staticmethod
    def estimate_cost(depth: ResearchDepth) -> Dict[str, Any]:
        """
        Estimate costs based on research depth.

        Args:
            depth: ResearchDepth (STANDARD or DEEP)

        Returns:
            Dictionary with estimated cost and time
        """
        if depth == ResearchDepth.STANDARD:
            return {
                "estimated_cost_usd": 0.0,  # Standard uses free models
                "estimated_time_minutes": 5,
            }
        else:  # DEEP
            return {
                "estimated_cost_usd": 2.5,  # Deep uses paid Kimi K2.5
                "estimated_time_minutes": 15,
            }

    @staticmethod
    async def log_token_usage(
        session: AsyncSession,
        task_id: UUID,
        agent_name: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        input_preview: Optional[str] = None,
        output_preview: Optional[str] = None,
        duration_seconds: Optional[float] = None,
    ) -> TokenUsageLogDB:
        """
        Log individual token usage per LLM call.

        Called from agent nodes after each LLM invocation.
        Enables cost breakdown and token analysis.
        """
        log_entry = TokenUsageLogDB(
            task_id=task_id,
            agent_name=agent_name,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost_usd,
            input_preview=input_preview,
            output_preview=output_preview,
            duration_seconds=duration_seconds,
        )
        session.add(log_entry)
        await session.commit()
        return log_entry

    # PHASE 3: Task lifecycle management methods
    
    @staticmethod
    async def set_deadline_and_worker(
        session: AsyncSession,
        task_id: UUID,
        worker_id: str = WORKER_ID,
    ) -> Optional[ResearchTaskDB]:
        """
        PHASE 3: Set deadline_at and worker_id when task starts execution.
        
        Args:
            session: AsyncSession for database operations
            task_id: UUID of the task
            worker_id: Worker identifier (defaults to CONSILIENCE_WORKER_ID or hostname)
        
        Returns:
            Updated task or None if not found
        """
        task = await ResearchService.get_research_task(session, task_id)
        if not task:
            return None
        
        # Set deadline: now + configured timeout
        now = datetime.utcnow()
        deadline = now + WORKFLOW_TIMEOUT_TIMEDELTA
        
        # Update task with deadline and worker
        stmt = (
            update(ResearchTaskDB)
            .where(ResearchTaskDB.id == task_id)
            .values(
                deadline_at=deadline,
                worker_id=worker_id,
                last_heartbeat_at=now,
            )
        )
        
        await session.execute(stmt)
        await session.commit()
        
        logger.info(
            f"[Phase 3] Set deadline and worker for task {task_id}: "
            f"deadline={deadline}, worker={worker_id}"
        )
        
        return await ResearchService.get_research_task(session, task_id)

    @staticmethod
    def is_deadline_exceeded(task: ResearchTaskDB) -> bool:
        """
        PHASE 3: Check if task has exceeded its deadline.
        
        Args:
            task: ResearchTaskDB record
        
        Returns:
            True if deadline_at exists and is in the past, False otherwise
        """
        if not hasattr(task, 'deadline_at') or task.deadline_at is None:
            return False
        
        now = datetime.utcnow()
        return now > task.deadline_at

    @staticmethod
    def get_remaining_time(task: ResearchTaskDB) -> Optional[float]:
        """
        PHASE 3: Get remaining time in seconds until deadline.
        
        Args:
            task: ResearchTaskDB record
        
        Returns:
            Remaining seconds, or None if no deadline set
        """
        if not hasattr(task, 'deadline_at') or task.deadline_at is None:
            return None
        
        now = datetime.utcnow()
        if now > task.deadline_at:
            return 0.0
        
        remaining = (task.deadline_at - now).total_seconds()
        return max(0.0, remaining)

    @staticmethod
    def get_remaining_time_static(deadline_at: Optional[datetime]) -> Optional[float]:
        """
        PHASE 3: Get remaining time in seconds until a deadline.
        
        Static version that takes a datetime directly (doesn't require a task object).
        
        Args:
            deadline_at: Deadline datetime
        
        Returns:
            Remaining seconds, or None if deadline is None
        """
        if deadline_at is None:
            return None
        
        now = datetime.utcnow()
        if now > deadline_at:
            return 0.0
        
        remaining = (deadline_at - now).total_seconds()
        return max(0.0, remaining)

    @staticmethod
    def is_task_terminal(status: TaskStatus) -> bool:
        """
        PHASE 3: Check if task is in a terminal state.
        
        Terminal states: COMPLETED, FAILED, CANCELLED
        Non-terminal: PENDING, RUNNING, PAUSED
        
        Args:
            status: TaskStatus enum
        
        Returns:
            True if status is terminal
        """
        terminal_states = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
        return status in terminal_states

    @staticmethod
    async def validate_state_transition(
        session: AsyncSession,
        task_id: UUID,
        old_status: TaskStatus,
        new_status: TaskStatus,
    ) -> bool:
        """
        PHASE 3: Validate task state transitions.
        
        Valid transitions:
        - PENDING → RUNNING
        - RUNNING → COMPLETED
        - RUNNING → FAILED
        - RUNNING → CANCELLED (or any → CANCELLED for safety)
        
        Args:
            session: AsyncSession for database operations
            task_id: UUID of task
            old_status: Current status
            new_status: Desired new status
        
        Returns:
            True if transition is valid
        """
        task = await ResearchService.get_research_task(session, task_id)
        if not task:
            logger.warning(f"[Phase 3] Cannot validate transition for non-existent task {task_id}")
            return False
        
        current_actual = getattr(task, 'status', old_status)
        
        # If already in terminal state, no transitions allowed except to CANCELLED for safety
        if ResearchService.is_task_terminal(current_actual):
            if new_status == TaskStatus.CANCELLED:
                logger.info(f"[Phase 3] Allowing CANCELLED transition for already-terminal task {task_id}")
                return True
            logger.warning(
                f"[Phase 3] Transition to {new_status} rejected: task {task_id} already in terminal state {current_actual}"
            )
            return False
        
        # Allow any non-terminal → CANCELLED for safety (cleanup after crash)
        if new_status == TaskStatus.CANCELLED:
            return True
        
        # Define valid transitions
        valid_transitions = {
            TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
            TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED},
            TaskStatus.PAUSED: {TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED},
        }
        
        allowed_next_states = valid_transitions.get(current_actual, set())
        is_valid = new_status in allowed_next_states
        
        if not is_valid:
            logger.warning(
                f"[Phase 3] Invalid state transition {current_actual} → {new_status} for task {task_id}"
            )
        
        return is_valid

    @staticmethod
    async def update_heartbeat(
        session: AsyncSession,
        task_id: UUID,
    ) -> Optional[ResearchTaskDB]:
        """
        PHASE 3: Update task heartbeat to signal it's alive.
        
        Called periodically during task execution to prevent
        orphan detection. Non-blocking operation.
        
        Args:
            session: AsyncSession for database operations
            task_id: UUID of task
        
        Returns:
            Updated task or None if not found
        """
        try:
            now = datetime.utcnow()
            
            stmt = (
                update(ResearchTaskDB)
                .where(ResearchTaskDB.id == task_id)
                .values(last_heartbeat_at=now)
            )
            
            result = await session.execute(stmt)
            await session.commit()
            
            if result.rowcount > 0:
                logger.debug(f"[Phase 3] Heartbeat updated for task {task_id}")
                return await ResearchService.get_research_task(session, task_id)
            else:
                logger.warning(f"[Phase 3] Heartbeat update failed: task {task_id} not found")
                return None
                
        except Exception as e:
            await session.rollback()
            logger.exception(f"[Phase 3] Error updating heartbeat for task {task_id}: {e}")
            # Don't raise - heartbeat is non-critical
            return None

    @staticmethod
    async def mark_timeout(
        session: AsyncSession,
        task_id: UUID,
    ) -> Optional[ResearchTaskDB]:
        """
        PHASE 3: Mark task as FAILED due to timeout.
        
        Args:
            session: AsyncSession for database operations
            task_id: UUID of task
        
        Returns:
            Updated task or None if not found/failed
        """
        task = await ResearchService.get_research_task(session, task_id)
        if not task:
            return None
        
        # Use optimistic locking update
        return await ResearchService.update_research_task_with_retry(
            session=session,
            task_id=task_id,
            status=TaskStatus.FAILED,
            error_message="Workflow exceeded global time limit",
            metadata_json={
                "error_code": "TIMEOUT",
                "error_context_json": {
                    "reason": "workflow exceeded time limit",
                    "deadline_at": str(task.deadline_at) if task.deadline_at else None,
                }
            },
            max_retries=3,
        )

    @staticmethod
    async def mark_orphaned_task(
        session: AsyncSession,
        task_id: UUID,
        reason: str = "Heartbeat timeout",
    ) -> Optional[ResearchTaskDB]:
        """
        PHASE 3: Mark task as FAILED due to being orphaned.
        
        Args:
            session: AsyncSession for database operations
            task_id: UUID of task
            reason: Description of why orphaned
        
        Returns:
            Updated task or None if not found/failed
        """
        return await ResearchService.update_research_task_with_retry(
            session=session,
            task_id=task_id,
            status=TaskStatus.FAILED,
            error_message=f"Task recovered as orphaned: {reason}",
            metadata_json={
                "error_code": "ORPHANED_TASK",
                "error_context_json": {
                    "reason": reason,
                }
            },
            max_retries=3,
        )

    @staticmethod
    async def reserve_deep_quota(
        session: AsyncSession,
        user_id: UUID,
    ) -> bool:
        """
        PHASE 4: Atomically reserve deep research quota (increment inflight count).
        
        Uses transactional UPDATE to safely increment deep_quota_inflight ONLY if
        total quota available (inflight + actual_usage < monthly_quota).
        
        This prevents race conditions where multiple concurrent requests could
        bypass the quota limit.
        
        Args:
            session: AsyncSession for database operations
            user_id: UUID of user
            
        Returns:
            True if quota reserved successfully, False if quota exceeded
            
        Raises:
            Exception: On database error
        """
        from ..database.schema import UserDB
        
        try:
            # Atomic transactional check-and-increment:
            # UPDATE users
            # SET deep_quota_inflight = deep_quota_inflight + 1
            # WHERE id = ? AND (monthly_deep_quota_used + deep_quota_inflight < monthly_deep_quota)
            
            stmt = (
                update(UserDB)
                .where(
                    UserDB.id == user_id,
                    # Safety check: Allow reserve only if inflight + used < quota
                    (UserDB.monthly_deep_quota_used + UserDB.deep_quota_inflight) < UserDB.monthly_deep_quota
                )
                .values(deep_quota_inflight=UserDB.deep_quota_inflight + 1)
            )
            
            result = await session.execute(stmt)
            await session.commit()
            
            reserved = result.rowcount > 0
            
            if reserved:
                logger.info(
                    f"[Phase 4] Deep quota reserved for user {user_id} "
                    f"(inflight now +1)"
                )
            else:
                logger.warning(
                    f"[Phase 4] Failed to reserve deep quota for user {user_id} "
                    f"(quota exceeded or user not found)"
                )
            
            return reserved
            
        except Exception as e:
            logger.exception(
                f"[Phase 4] Error reserving deep quota for user {user_id}: {e}"
            )
            await session.rollback()
            raise

    @staticmethod
    async def release_deep_quota(
        session: AsyncSession,
        user_id: UUID,
        mark_used: bool = False,
    ) -> bool:
        """
        PHASE 4: Atomically release deep research quota.
        
        On task completion: mark_used=True decrements inflight and increments actual usage.
        On task failure: mark_used=False just decrements inflight (don't count failed task against quota).
        
        Args:
            session: AsyncSession for database operations
            user_id: UUID of user
            mark_used: If True, increment monthly_deep_quota_used (count as completed).
                      If False, just decrement inflight without counting.
            
        Returns:
            True if update succeeded, False otherwise
            
        Raises:
            Exception: On database error
        """
        from ..database.schema import UserDB
        
        try:
            if mark_used:
                # Completion case: decrement inflight AND increment actual usage
                stmt = (
                    update(UserDB)
                    .where(UserDB.id == user_id)
                    .values(
                        deep_quota_inflight=UserDB.deep_quota_inflight - 1,
                        monthly_deep_quota_used=UserDB.monthly_deep_quota_used + 1,
                    )
                )
                logger.debug(
                    f"[Phase 4] Releasing deep quota for user {user_id} "
                    f"(marking as used)"
                )
            else:
                # Failure case: just decrement inflight, don't count usage
                stmt = (
                    update(UserDB)
                    .where(UserDB.id == user_id)
                    .values(
                        deep_quota_inflight=UserDB.deep_quota_inflight - 1,
                    )
                )
                logger.debug(
                    f"[Phase 4] Releasing deep quota for user {user_id} "
                    f"(no usage counted, task failed)"
                )
            
            result = await session.execute(stmt)
            await session.commit()
            
            success = result.rowcount > 0
            
            if not success:
                logger.warning(
                    f"[Phase 4] Failed to release quota for user {user_id} "
                    f"(user not found)"
                )
            
            return success
            
        except Exception as e:
            logger.exception(
                f"[Phase 4] Error releasing deep quota for user {user_id}: {e}"
            )
            await session.rollback()
            raise

    @staticmethod
    async def get_quota_status(
        session: AsyncSession,
        user_id: UUID,
    ) -> Optional[Dict[str, int]]:
        """
        Get current deep quota status for a user.
        
        Args:
            session: AsyncSession for database operations
            user_id: UUID of user
            
        Returns:
            Dict with keys: quota, used, inflight, available
            or None if user not found
        """
        from ..database.schema import UserDB
        
        try:
            stmt = select(UserDB).where(UserDB.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                return None
            
            quota = user.monthly_deep_quota or 0
            used = user.monthly_deep_quota_used or 0
            inflight = user.deep_quota_inflight or 0
            available = max(0, quota - used - inflight)
            
            return {
                "quota": quota,
                "used": used,
                "inflight": inflight,
                "available": available,
                "total_reserved": used + inflight,
            }
            
        except Exception as e:
            logger.exception(
                f"[Phase 4] Error getting quota status for user {user_id}: {e}"
            )
            return None


    @staticmethod
    async def save_checkpoint(
        session: AsyncSession,
        task_id: UUID,
        agent_name: str,
        agent_type: str,
        sequence_number: int,
        state_snapshot: ResearchState,
        status_before: TaskStatus,
        status_after: TaskStatus,
        duration_seconds: float,
        error: Optional[str] = None,
    ) -> ResearchCheckpointDB:
        """
        Save state checkpoint after agent completes.

        Enables resume if agent fails.
        """
        # Handle both string and enum types for status fields
        status_before_value = status_before.value if isinstance(status_before, TaskStatus) else str(status_before)
        status_after_value = status_after.value if isinstance(status_after, TaskStatus) else str(status_after)
        
        checkpoint = ResearchCheckpointDB(
            task_id=task_id,
            agent_name=agent_name,
            agent_type=agent_type,
            sequence_number=sequence_number,
            state_snapshot_json=state_snapshot.model_dump(mode='json', exclude={'created_at', 'updated_at'}),
            status_before=status_before_value,
            status_after=status_after_value,
            duration_seconds=duration_seconds,
            is_resumable=error is None,
            error_message=error,
        )
        session.add(checkpoint)
        await session.commit()
        return checkpoint
