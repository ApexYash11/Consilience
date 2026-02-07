"""Research service logic for task management and orchestration."""
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from database.schema import ResearchTaskDB, AgentActionDB, TokenUsageLogDB, ResearchCheckpointDB
from models.research import TaskStatus, ResearchDepth, ResearchState
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
        result = await session.execute(select(ResearchTaskDB).where(ResearchTaskDB.id == task_id))
        return result.scalar_one_or_none()

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
        logger.debug(f"Logged agent action: {agent_name}.{action} (tokens: {tokens_used}, cost: ${cost_usd:.4f})")
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
            select(AgentActionDB).where(AgentActionDB.task_id == task_id).order_by(AgentActionDB.started_at)
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
        checkpoint = ResearchCheckpointDB(
            task_id=task_id,
            agent_name=agent_name,
            agent_type=agent_type,
            sequence_number=sequence_number,
            state_snapshot_json=state_snapshot.model_dump(),
            status_before=status_before.value,
            status_after=status_after.value,
            duration_seconds=duration_seconds,
            is_resumable=error is None,
            error_message=error,
        )
        session.add(checkpoint)
        await session.commit()
        return checkpoint
