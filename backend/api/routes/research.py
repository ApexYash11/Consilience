"""Research routes for task management and orchestration."""

import asyncio
import logging
import os
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db, get_current_user, require_paid_tier, check_standard_quota, check_deep_quota, check_rate_limit
from ...models.research import ResearchState, ResearchDepth, TaskStatus
from ...services.research_service import ResearchService
from ...services.observability import safe_trace_async, safe_get_current_run_id, merge_metadata, log_metric
from ...services.task_recovery_service import TaskRecoveryService
from ...orchestrator.standard_orchestrator import run_research, set_agent_action_logger, set_metadata_persistence_callback
from ...orchestrator.deep_orchestrator import (
    run_deep_research,
    set_agent_action_logger as set_deep_agent_action_logger,
    set_metadata_persistence_callback as set_deep_metadata_persistence_callback,
)
from ...database.connection import AsyncSessionLocal
from ...services.deep_cost_estimator import estimate_deep_research_cost
from ...services.cost_service import CostService

logger = logging.getLogger(__name__)


# Request/Response models
class CreateResearchRequest(BaseModel):
    topic: str
    requirements: Optional[dict] = None
    depth: ResearchDepth = ResearchDepth.STANDARD


class CreateResearchResponse(BaseModel):
    task_id: str
    status: str
    estimated_cost_usd: float
    estimated_time_minutes: float


class ResearchStatusResponse(BaseModel):
    id: str  # Changed from task_id to match frontend
    status: str  # "queued", "running", "completed", "failed"
    progress: int  # Changed from progress_percent (0-100)
    currentStep: Optional[str] = None  # Current research step
    sources: list = []  # Sources discovered so far
    tokens: int  # Renamed from tokens_used
    costPerToken: float = 0.000006  # Cost per token
    estimatedRemaining: Optional[int] = None  # Estimated time remaining in seconds
    model: str = "claude-3-opus"  # Model being used
    error: Optional[str] = None  # Error message if failed


class ResearchResultResponse(BaseModel):
    task_id: str
    status: str
    final_paper: str
    sources: list = []
    contradictions: list = []
    total_cost: float
    total_tokens: int


class ResearchTaskListItem(BaseModel):
    """Simplified research task for list views."""
    task_id: str
    title: str
    description: str
    depth: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    estimated_cost_usd: Optional[float] = None
    actual_cost_usd: Optional[float] = None
    progress_percent: int = 0


class ResearchListResponse(BaseModel):
    """Paginated list of research tasks."""
    tasks: list[ResearchTaskListItem]
    total_count: int
    page: int
    page_size: int
    total_pages: int


router = APIRouter(tags=["research"])

# Background task tracking
_running_tasks: dict = {}  # type: ignore


async def _log_agent_action_to_db(
    task_id: UUID,
    agent_name: str,
    agent_type: str,
    action: str,
    tokens_used: int = 0,
    cost_usd: float = 0.0,
    input_data: Optional[dict] = None,
    output_data: Optional[dict] = None,
    error: Optional[str] = None,
):
    """
    Callback for logging agent actions to the database.
    This is called by the orchestrator after each agent completes.
    """
    try:
        # Get a fresh database session for this async operation
        async with AsyncSessionLocal() as session:
            await ResearchService.log_agent_action(
                session=session,
                task_id=task_id,
                agent_name=agent_name,
                agent_type=agent_type,
                action=action,
                input_data=input_data,
                output_data=output_data,
                tokens_used=tokens_used,
                cost_usd=cost_usd,
                error=error,
            )
    except Exception as e:
        logger.warning(f"Failed to log agent action {agent_name}: {e}")


async def _persist_metadata_to_db(
    task_id: UUID,
    current_step: str,
    sources: list,
    tokens_used: int = 0,
    cost: float = 0.0,
    model: str = "openrouter-llm",
):
    """
    Callback for persisting research metadata updates during execution.
    This enables live progress updates during research execution.
    """
    try:
        # Get a fresh database session for this async operation
        async with AsyncSessionLocal() as session:
            # Build metadata dict with current execution state
            metadata = {
                "current_step": current_step,
                "sources": sources,
                "model": model,
                "cost_per_token": cost / tokens if tokens > 0 else 0.0,  # Calculate from actual values
            }
            
            logger.info(
                f"Persisting metadata for task {task_id}: "
                f"step={current_step}, sources={len(sources)}, "
                f"tokens={tokens_used}, cost=${cost:.4f}, model={model}"
            )
            
            # Update task with current progress
            await ResearchService.update_research_task(
                session=session,
                task_id=task_id,
                tokens_used=tokens_used,
                actual_cost_usd=cost,
                metadata_json=metadata,
            )
    except Exception as e:
        logger.error(f"Failed to persist metadata for task {task_id}: {e}", exc_info=True)


async def _execute_research_background(
    task_id: UUID,
    state: ResearchState,
    session: AsyncSession,
):
    """
    Background task that runs the entire research workflow.
    This function is designed to run as an asyncio task without blocking.
    
    Wrapped with LangSmith tracing for observability:
    - Captures task metadata (topic, depth, user_id)
    - Tracks execution flow and costs
    - Enables state snapshots for debugging
    """
    try:
        # Set the agent logging and metadata callbacks for this execution
        set_agent_action_logger(_log_agent_action_to_db)
        set_metadata_persistence_callback(_persist_metadata_to_db)

        # Update task status to running
        await ResearchService.update_research_task(
            session=session,
            task_id=task_id,
            status=TaskStatus.RUNNING,
        )
        
        # Update heartbeat to signal task is alive (Problem 2: Orphaned Tasks)
        await TaskRecoveryService.update_heartbeat(str(task_id))
        
        logger.info(f"Starting research workflow for task {task_id}")

        # Fetch task record for metadata
        task_record = await ResearchService.get_research_task(session, task_id)
        user_id = "unknown"
        research_depth = "standard"
        if task_record and hasattr(task_record, 'user_id'):
            try:
                # Safely extract user_id from ORM object without evaluating Column as bool
                user_id_value = getattr(task_record, 'user_id', None)
                user_id = str(user_id_value) if user_id_value else "unknown"
            except Exception:
                user_id = "unknown"
        if task_record:
            research_depth = getattr(task_record, 'research_depth', 'standard') or 'standard'

        # Prepare trace metadata
        trace_metadata = {
            "task_id": str(task_id),
            "topic": state.topic[:100],  # Truncate to avoid large strings
            "research_depth": str(research_depth),
            "user_id": user_id,
            "num_sources_target": state.num_sources_target,
        }

        # Run orchestrator with tracing
        # The trace context sets up LangSmith tracing if enabled
        async with safe_trace_async(
            name=f"research_task_{task_id}",
            run_type="chain",
            metadata=trace_metadata,
            tags=["research", "standard", str(research_depth)],
        ) as run_id:
            # Get LangSmith run ID if tracing is enabled
            if run_id:
                logger.debug(f"Task {task_id} tracing enabled with run ID: {run_id}")
            
            # Run the orchestrator
            final_state = await run_research(state)

            cost = float(final_state.cost or 0.0)
            tokens = final_state.tokens_used or 0

            # Log metrics for observability
            log_metric(
                "research_completed",
                {
                    "task_id": str(task_id),
                    "cost": cost,
                    "tokens": tokens,
                    "sources": len(final_state.sources or []),
                },
            )

        # Update task with final results
        # Extract metadata_json safely from SQLAlchemy ORM object
        existing_metadata = {}
        if task_record and hasattr(task_record, 'metadata_json'):
            existing_metadata = task_record.metadata_json if isinstance(task_record.metadata_json, dict) else {}
        
        final_metadata = merge_metadata(
            existing_metadata,
            {"langsmith_run_id": run_id} if run_id else {},
        )
        
        # Update heartbeat one final time (Problem 2: Orphaned Tasks)
        await TaskRecoveryService.update_heartbeat(str(task_id))
        
        await ResearchService.update_research_task(
            session=session,
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            actual_cost_usd=cost,
            tokens_used=tokens,
            final_state=final_state,
            metadata_json=final_metadata,
        )
        logger.info(
            f"Research workflow completed for task {task_id}: "
            f"cost=${cost:.4f}, tokens={tokens}"
        )

        # Record usage for quota tracking
        try:
            if task_record is not None and task_record.user_id is not None:
                depth = ResearchDepth(str(research_depth))
                await CostService().record_usage(
                    user_id=str(task_record.user_id),
                    depth=depth,
                    tokens_used=tokens,
                    cost_usd=cost,
                )
        except Exception as usage_err:
            logger.warning(f"Failed to record usage for task {task_id}: {usage_err}")

    except Exception as e:
        logger.error(
            f"Research workflow failed for task {task_id}: {str(e)}", exc_info=True
        )
        
        # Log failure metric
        log_metric(
            "research_failed",
            {"task_id": str(task_id), "error": str(e)[:100]},
        )
        
        # Update heartbeat before marking as failed (Problem 2: Orphaned Tasks)
        await TaskRecoveryService.update_heartbeat(str(task_id))
        
        await ResearchService.update_research_task(
            session=session,
            task_id=task_id,
            status=TaskStatus.FAILED,
            error_message=str(e),
        )
    finally:
        # Clean up the task from tracking
        if str(task_id) in _running_tasks:  # type: ignore
            del _running_tasks[str(task_id)]  # type: ignore


@router.get("/list", response_model=ResearchListResponse, summary="List user's research tasks", description="Retrieve paginated list of all research tasks for the authenticated user.", tags=["research"])
async def list_research_tasks(
    page: int = 1,
    page_size: int = 10,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),  # enforces auth
) -> ResearchListResponse:
    """
    GET /api/research/list

    Retrieves paginated list of research tasks for the authenticated user.
    
    Query Parameters:
    - page: Page number (1-indexed), default 1
    - page_size: Number of tasks per page, default 10

    Returns:
    {
        "tasks": [
            {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "Research: Climate change impacts on agriculture",
                "description": "Standard research task for climate change impacts on agriculture",
                "depth": "standard",
                "status": "completed",
                "created_at": "2026-03-27T10:30:00Z",
                "completed_at": "2026-03-27T10:35:00Z",
                "estimated_cost_usd": 0.0,
                "actual_cost_usd": 0.0,
                "progress_percent": 100
            }
        ],
        "total_count": 25,
        "page": 1,
        "page_size": 10,
        "total_pages": 3
    }
    """
    try:
        # Normalize pagination parameters
        normalized_page = max(1, page)
        normalized_page_size = max(1, min(page_size, 100))  # Ensure page_size >= 1 and cap at 100
        
        # Fetch paginated research tasks
        tasks, total_count = await ResearchService.get_user_research_tasks(
            session=db,
            user_id=UUID(user.user_id),  # type: ignore
            page=normalized_page,
            page_size=normalized_page_size,
        )

        # Convert to list items
        task_items = []
        for task in tasks:
            # Determine progress based on status
            progress_percent = 0
            if task.status == TaskStatus.COMPLETED:
                progress_percent = 100
            elif task.status == TaskStatus.RUNNING:
                progress_percent = 50  # In-progress indicator
            elif task.status == TaskStatus.FAILED:
                progress_percent = 0
            
            item = ResearchTaskListItem(
                task_id=str(task.id),
                title=task.title or "",
                description=task.description or "",
                depth=str(task.research_depth),
                status=str(task.status),
                created_at=task.created_at,
                completed_at=task.completed_at,
                estimated_cost_usd=float(task.estimated_cost_usd) if task.estimated_cost_usd else None,
                actual_cost_usd=float(task.actual_cost_usd) if task.actual_cost_usd else None,
                progress_percent=progress_percent,
            )
            task_items.append(item)

        # Calculate total pages using normalized page_size
        total_pages = (total_count + normalized_page_size - 1) // normalized_page_size

        return ResearchListResponse(
            tasks=task_items,
            total_count=total_count,
            page=normalized_page,
            page_size=normalized_page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error(f"Failed to list research tasks: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list research tasks: {str(e)}"
        )


@router.post("/standard", response_model=CreateResearchResponse, summary="Create standard research task", description="Initiates a standard research task that runs in the background. Results are processed asynchronously.", tags=["research"])
async def create_standard_research(
    request: CreateResearchRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(check_standard_quota),  # enforces auth + quota
    _rate_limited=Depends(check_rate_limit),  # enforces rate limit
) -> CreateResearchResponse:
    """
    POST /api/research/standard

    Creates a new standard research task and starts it in the background.

    Request Body:
    {
        "topic": "Climate change impacts on agriculture",
        "requirements": {},
        "depth": "standard"
    }

    Returns:
    {
        "task_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "pending",
        "estimated_cost_usd": 0.0,
        "estimated_time_minutes": 5
    }
    """
    try:
        # Estimate cost
        cost_estimate = ResearchService.estimate_cost(request.depth)

        # Create research task in database
        task = await ResearchService.save_research_task(
            session=db,
            user_id=UUID(user.user_id),  # type: ignore
            topic=request.topic,
            research_depth=request.depth,
            title=f"Research: {request.topic}",
            description=f"Standard research task for {request.topic}",
            estimated_cost_usd=cost_estimate["estimated_cost_usd"],
        )
        logger.info(f"Created research task {task.id} for user {user.user_id}")  # type: ignore

        # Create ResearchState for workflow
        state = ResearchState(
            task_id=str(task.id),
            topic=request.topic,
            requirements=request.requirements or {},
            num_sources_target=15,
        )

        # Start research workflow as background asyncio task
        # This runs without blocking the API response
        task_id_str = str(task.id)  # type: ignore
        task_id_uuid = UUID(task_id_str)  # type: ignore

        async def run_and_log():
            async with AsyncSessionLocal() as session:
                await _execute_research_background(task_id_uuid, state, session)

        # Create and store the background task
        background_task = asyncio.create_task(run_and_log())
        _running_tasks[task_id_str] = background_task

        # Return immediately with task info
        return CreateResearchResponse(
            task_id=task_id_str,
            status=TaskStatus.PENDING.value,
            estimated_cost_usd=cost_estimate["estimated_cost_usd"],
            estimated_time_minutes=cost_estimate["estimated_time_minutes"],
        )

    except Exception as e:
        logger.error(f"Failed to create research task: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to create research task: {str(e)}"
        )


@router.get("/standard/{task_id}/status", response_model=ResearchStatusResponse, summary="Get standard research status", description="Retrieve the current status of a standard research task.", tags=["research"])
async def get_research_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),  # type: ignore
) -> ResearchStatusResponse:
    """
    GET /api/research/standard/{task_id}/status

    Gets the current status of a research task.

    Returns:
    {
        "task_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "running",
        "progress_percent": 35,
        "cost_so_far": 0.12,
        "tokens_used": 2500
    }
    """
    try:
        # Validate UUID format
        try:
            task_uuid = UUID(task_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid task_id format")

        task = await ResearchService.get_research_task(db, task_uuid)

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Verify user owns task - handle both UUID and string types
        task_user_id_str = str(task.user_id) if task.user_id else None
        current_user_id_str = str(user.user_id) if hasattr(user, 'user_id') and user.user_id else None  # type: ignore
        
        if not task_user_id_str or not current_user_id_str or task_user_id_str != current_user_id_str:
            logger.debug(f"Authorization failed: task_user={task_user_id_str}, current_user={current_user_id_str}")
            raise HTTPException(status_code=403, detail="Not authorized to access this task")

        # Handle both enum and string status types
        task_status = task.status  # type: ignore
        if isinstance(task_status, str):
            task_status = TaskStatus(task_status)
        
        # Extract metadata
        metadata = task.metadata_json or {}  # type: ignore
        if not isinstance(metadata, dict):
            metadata = {}
        
        # Extract sources and calculate progress
        sources = metadata.get("sources", [])
        num_sources = len(sources) if isinstance(sources, list) else 0
        
        # Calculate progress based on status and sources found
        if task_status == TaskStatus.RUNNING:
            # Base progress: 25% for just starting research
            base_progress = 25
            # Bonus: up to 40% based on sources found (estimate max of 100 sources)
            source_bonus = min(40, (num_sources / 100) * 40)
            # Bonus: up to 35% based on elapsed time
            if task.started_at:
                elapsed_seconds = (datetime.utcnow() - task.started_at).total_seconds()
                # Estimate 15 minutes total, so at full time we'd have 35% from time
                time_bonus = min(35, (elapsed_seconds / 900) * 35)
            else:
                time_bonus = 0
            progress = min(95, int(base_progress + source_bonus + time_bonus))
        else:
            # Use static mapping for non-running states
            progress_map = {
                TaskStatus.PENDING: 0,
                TaskStatus.COMPLETED: 100,
                TaskStatus.FAILED: 0,
                TaskStatus.CANCELLED: 0,
                TaskStatus.PAUSED: 50,
            }
            progress = progress_map.get(task_status, 0)
        
        # Extract current step from metadata
        current_step = metadata.get("current_step")
        
        # Extract model from metadata if set during execution, otherwise use from task config
        # Default to "openrouter-llm" for now since we're using OpenRouter
        model = metadata.get("model", "openrouter-llm")
        
        # Get actual tokens and costs from task (these are updated during execution)
        tokens = task.tokens_used or 0  # type: ignore
        actual_cost = task.actual_cost_usd or 0.0  # type: ignore
        estimated_cost = task.estimated_cost_usd or 0.0  # type: ignore
        
        # Calculate cost per token if we have token data
        cost_per_token = 0.0
        if tokens > 0 and actual_cost > 0:
            cost_per_token = actual_cost / tokens
        
        # Calculate estimated remaining time (simple heuristic)
        estimated_remaining = None
        if task_status == TaskStatus.RUNNING and progress > 0 and progress < 100:
            if task.started_at:
                elapsed_seconds = (datetime.utcnow() - task.started_at).total_seconds()
                # Linear estimate: if we're at X% progress after Y seconds, 
                # we should finish in (Y * 100 / X) - Y seconds
                estimated_remaining = max(0, int((elapsed_seconds * 100 / progress) - elapsed_seconds))
        
        # Extract error if task failed
        error = task.error_message if task.status == TaskStatus.FAILED else None  # type: ignore

        return ResearchStatusResponse(
            id=str(task.id),
            status=task_status.value if isinstance(task_status, TaskStatus) else str(task_status),
            progress=progress,
            currentStep=current_step,
            sources=sources,
            tokens=tokens,  # Use actual tokens from database
            costPerToken=cost_per_token,  # Calculate from actual values
            estimatedRemaining=estimated_remaining,
            model=model,  # Use metadata model or default to openrouter-llm
            error=error,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get research status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get research status")


@router.get("/standard/{task_id}/result", response_model=ResearchResultResponse, summary="Get standard research results", description="Retrieve the final results of a completed standard research task.", tags=["research"])
async def get_research_result(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),  # type: ignore
) -> ResearchResultResponse:
    """
    GET /api/research/standard/{task_id}/result

    Gets the final research paper and results.

    Returns:
    {
        "task_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "completed",
        "final_paper": "# Climate Change\n\nIntroduction...",
        "sources": [...],
        "contradictions": [...],
        "total_cost": 0.45,
        "total_tokens": 28000
    }
    """
    try:
        # Validate UUID format
        try:
            task_uuid = UUID(task_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Malformed UUID")

        task = await ResearchService.get_research_task(db, task_uuid)

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Verify user owns task - handle both UUID and string types
        task_user_id_str = str(task.user_id) if task.user_id else None
        current_user_id_str = str(user.user_id) if hasattr(user, 'user_id') and user.user_id else None  # type: ignore
        
        if not task_user_id_str or not current_user_id_str or task_user_id_str != current_user_id_str:
            logger.debug(f"Authorization failed: task_user={task_user_id_str}, current_user={current_user_id_str}")
            raise HTTPException(status_code=403, detail="Not authorized to access this task")

        # Check if task is completed
        task_status = task.status  # type: ignore
        if isinstance(task_status, str):
            task_status = TaskStatus(task_status)
            
        if task_status != TaskStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Task not completed. Current status: {task_status.value}",
            )

        # Extract result data from final_state_json if available, fallback to metadata_json
        result_data = task.final_state_json or task.metadata_json or {}  # type: ignore

        return ResearchResultResponse(
            task_id=str(task.id),
            status=task_status.value if isinstance(task_status, TaskStatus) else str(task_status),
            final_paper=result_data.get("final_paper", ""),  # type: ignore
            sources=result_data.get("sources", []),  # type: ignore
            contradictions=result_data.get("contradictions", []),  # type: ignore
            total_cost=float(task.actual_cost_usd or 0.0),  # type: ignore
            total_tokens=task.tokens_used or 0,  # type: ignore
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get research result: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get research result")


# ============================================================================
# DEEP RESEARCH ENDPOINTS (PAID TIER ONLY)
# ============================================================================


@router.post("/deep", response_model=CreateResearchResponse, summary="Create deep research task", description="Initiates a deep research task with multiple research rounds and synthesis. Requires paid subscription.", tags=["research"])
async def create_deep_research(
    request: CreateResearchRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(check_deep_quota),  # enforces paid tier + quota
    _rate_limited=Depends(check_rate_limit),  # enforces rate limit
) -> CreateResearchResponse:
    """
    POST /api/research/deep

    Creates a new deep research task and starts it in the background.

    **REQUIRES PAID TIER**

    Deep research features:
    - 10-15 parallel sub-agents instead of 5
    - 3 recursive research rounds (initial, gap analysis, controversy resolution)
    - Enhanced verification with semantic cross-referencing
    - 3-5 revision cycles
    - Persistent file-based context management
    - Estimated duration: ~10 minutes
    - Estimated cost: $5-15 per task

    Request Body:
    {
        "topic": "Climate change impacts on agriculture",
        "requirements": {"min_sources": 20, "include_contradictions": true},
        "depth": "deep"
    }

    Returns:
    {
        "task_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "pending",
        "estimated_cost_usd": 9.50,
        "estimated_time_minutes": 10
    }
    """
    try:
        # Verify deep research is requested
        if request.depth != ResearchDepth.DEEP:
            raise HTTPException(
                status_code=400,
                detail="This endpoint is for deep research only. Use /api/research/standard for standard research.",
            )

        # Estimate deep research cost
        cost_estimate = estimate_deep_research_cost()

        # Create research task in database
        task = await ResearchService.save_research_task(
            session=db,
            user_id=UUID(user.user_id),  # type: ignore
            topic=request.topic,
            research_depth=request.depth,
            title=f"Deep Research: {request.topic}",
            description=f"Deep research task with 3 rounds and semantic verification for {request.topic}",
            estimated_cost_usd=cost_estimate["estimated_cost_usd"],
        )
        logger.info(f"Created deep research task {task.id} for user {user.user_id}")  # type: ignore

        # Create ResearchState for workflow
        state = ResearchState(
            task_id=str(task.id),
            topic=request.topic,
            requirements=request.requirements or {},
            num_sources_target=20,  # Deep research targets more sources
        )

        # Start deep research workflow as background asyncio task
        task_id_str = str(task.id)  # type: ignore
        task_id_uuid = UUID(task_id_str)  # type: ignore

        async def run_and_log_deep():
            async with AsyncSessionLocal() as session:
                await _execute_deep_research_background(task_id_uuid, state, session)

        # Create and store the background task
        background_task = asyncio.create_task(run_and_log_deep())
        _running_tasks[task_id_str] = background_task

        # Return immediately with task info
        return CreateResearchResponse(
            task_id=task_id_str,
            status=TaskStatus.PENDING.value,
            estimated_cost_usd=cost_estimate["estimated_cost_usd"],
            estimated_time_minutes=cost_estimate["estimated_duration_minutes"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create deep research task: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to create deep research task: {str(e)}"
        )


@router.get("/deep/{task_id}/status", response_model=ResearchStatusResponse, summary="Get deep research status", description="Retrieve the current status of a deep research task.", tags=["research"])
async def get_deep_research_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),  # type: ignore
) -> ResearchStatusResponse:
    """
    GET /api/research/deep/{task_id}/status

    Gets the current status of a deep research task.

    Returns:
    {
        "task_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "running",
        "progress_percent": 45,
        "cost_so_far": 2.50,
        "tokens_used": 15000
    }
    """
    try:
        # Validate UUID format
        try:
            task_uuid = UUID(task_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid task_id format")

        task = await ResearchService.get_research_task(db, task_uuid)

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Verify user owns task - handle both UUID and string types
        task_user_id_str = str(task.user_id) if task.user_id else None
        current_user_id_str = str(user.user_id) if hasattr(user, 'user_id') and user.user_id else None  # type: ignore
        
        if not task_user_id_str or not current_user_id_str or task_user_id_str != current_user_id_str:
            logger.debug(f"Authorization failed: task_user={task_user_id_str}, current_user={current_user_id_str}")
            raise HTTPException(status_code=403, detail="Not authorized to access this task")

        # Verify it's a deep research task
        if not (task.metadata_json and task.metadata_json.get("research_depth") == "deep"):  # type: ignore
            raise HTTPException(status_code=404, detail="Task not found")

        # Estimate progress based on status
        progress_map = {
            TaskStatus.PENDING: 0,
            TaskStatus.RUNNING: 50,
            TaskStatus.COMPLETED: 100,
            TaskStatus.FAILED: 0,
        }
        
        # Handle both enum and string status types
        task_status = task.status  # type: ignore
        if isinstance(task_status, str):
            task_status = TaskStatus(task_status)
        
        progress = progress_map.get(task_status, 0)

        # Extract sources and current step from metadata for deep research
        metadata = task.metadata_json or {}  # type: ignore
        
        # Get model from metadata or default to openrouter-llm
        model = metadata.get("model", "openrouter-llm") if isinstance(metadata, dict) else "openrouter-llm"
        
        # Get actual tokens and costs from task
        tokens = task.tokens_used or 0  # type: ignore
        actual_cost = task.actual_cost_usd or 0.0  # type: ignore
        
        # Calculate cost per token if we have token data
        cost_per_token = 0.0
        if tokens > 0 and actual_cost > 0:
            cost_per_token = actual_cost / tokens
        
        return ResearchStatusResponse(
            id=str(task.id),
            status=task_status.value if isinstance(task_status, TaskStatus) else str(task_status),
            progress=progress,
            currentStep=metadata.get("current_step") if isinstance(metadata, dict) else None,
            sources=metadata.get("sources", []) if isinstance(metadata, dict) else [],
            tokens=tokens,  # Use actual tokens from database
            costPerToken=cost_per_token,  # Calculate from actual values
            estimatedRemaining=None,
            model=model,  # Use metadata model or default to openrouter-llm
            error=task.error_message if task.status == TaskStatus.FAILED else None,  # type: ignore
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get deep research status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to get deep research status"
        )


@router.get("/deep/{task_id}/result", response_model=ResearchResultResponse, summary="Get deep research results", description="Retrieve the final results of a completed deep research task.", tags=["research"])
async def get_deep_research_result(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),  # type: ignore
) -> ResearchResultResponse:
    """
    GET /api/research/deep/{task_id}/result

    Gets the final research paper and results from a deep research task.

    Returns comprehensive research output with:
    - Final paper (3-5 rounds of refinement)
    - All sources (20+ from deep research)
    - Contradictions found and analysis
    - Detailed cost and token breakdown

    Returns:
    {
        "task_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "completed",
        "final_paper": "# Research Paper\n\nComprehensive analysis...",
        "sources": [...],
        "contradictions": [...],
        "total_cost": 9.45,
        "total_tokens": 65000
    }
    """
    try:
        # Validate UUID format
        try:
            task_uuid = UUID(task_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Malformed UUID")

        task = await ResearchService.get_research_task(db, task_uuid)

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Verify user owns task - handle both UUID and string types
        task_user_id_str = str(task.user_id) if task.user_id else None
        current_user_id_str = str(user.user_id) if hasattr(user, 'user_id') and user.user_id else None  # type: ignore
        
        if not task_user_id_str or not current_user_id_str or task_user_id_str != current_user_id_str:
            logger.debug(f"Authorization failed: task_user={task_user_id_str}, current_user={current_user_id_str}")
            raise HTTPException(status_code=403, detail="Not authorized to access this task")

        # Verify it's a deep research task
        if not (task.metadata_json and task.metadata_json.get("research_depth") == "deep"):  # type: ignore
            raise HTTPException(status_code=404, detail="Task not found")

        # Check if task is completed
        task_status = task.status  # type: ignore
        if isinstance(task_status, str):
            task_status = TaskStatus(task_status)
            
        if task_status != TaskStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Task not completed. Current status: {task_status.value}",
            )

        # Extract result data from final_state_json
        result_data = task.final_state_json or task.metadata_json or {}  # type: ignore

        return ResearchResultResponse(
            task_id=str(task.id),
            status=task_status.value if isinstance(task_status, TaskStatus) else str(task_status),
            final_paper=result_data.get("final_paper", ""),  # type: ignore
            sources=result_data.get("sources", []),  # type: ignore
            contradictions=result_data.get("contradictions", []),  # type: ignore
            total_cost=float(task.actual_cost_usd or 0.0),  # type: ignore
            total_tokens=task.tokens_used or 0,  # type: ignore
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get deep research result: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to get deep research result"
        )


@router.delete("/{task_id}", summary="Delete research task", description="Delete a research task. Can only delete tasks owned by the current user.", tags=["research"])
async def delete_research_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),  # type: ignore
) -> dict:
    """
    DELETE /api/research/{task_id}

    Deletes a research task owned by the current user.
    
    Returns:
    {
        "success": true,
        "message": "Task deleted successfully"
    }
    """
    try:
        # Validate UUID format
        try:
            task_uuid = UUID(task_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid task_id format")

        # Get task from database
        task = await ResearchService.get_research_task(db, task_uuid)

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Verify user owns task - handle both UUID and string types
        task_user_id_str = str(task.user_id) if task.user_id else None
        current_user_id_str = str(user.user_id) if hasattr(user, 'user_id') and user.user_id else None  # type: ignore
        
        if not task_user_id_str or not current_user_id_str or task_user_id_str != current_user_id_str:
            logger.debug(f"Authorization failed: task_user={task_user_id_str}, current_user={current_user_id_str}")
            raise HTTPException(status_code=403, detail="Not authorized to delete this task")

        # Cancel running task if it exists
        if str(task_uuid) in _running_tasks:  # type: ignore
            background_task = _running_tasks[str(task_uuid)]  # type: ignore
            if not background_task.done():
                logger.info(f"Cancelling background task {task_uuid}")
                background_task.cancel()
            
            # Wait for task cancellation with timeout to prevent hanging
            try:
                await asyncio.wait_for(background_task, timeout=30.0)  # Increased from 5s to 30s
            except asyncio.CancelledError:
                logger.info(f"Background task {task_uuid} cancelled successfully")
            except asyncio.TimeoutError:
                logger.warning(
                    f"Background task {task_uuid} did not complete within 30s timeout. "
                    f"Task status: {task.status}. Proceeding with record update."
                )
                # Don't delete if still marked as RUNNING - just update to CANCELLED
                if task.status == TaskStatus.RUNNING:
                    await ResearchService.update_research_task(
                        db, task_uuid, status=TaskStatus.FAILED,
                        error_message="Task cancelled but did not terminate cleanly"
                    )
            except Exception as e:
                logger.error(f"Error waiting for task {task_uuid} cancellation: {str(e)}")
            finally:
                # Safely remove from running tasks - use pop with default to avoid KeyError
                # The background task's finally block may have already removed the entry
                _running_tasks.pop(str(task_uuid), None)  # type: ignore

        # Delete task from database
        try:
            await ResearchService.delete_research_task(db, task_uuid)
            logger.info(f"Deleted research task {task_id} for user {user.user_id}")  # type: ignore
        except Exception as delete_err:
            logger.error(f"Failed to delete task {task_id}: {delete_err}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to delete task")

        return {
            "success": True,
            "message": "Task deleted successfully",
            "task_id": task_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete research task {task_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to delete research task: {str(e)}"
        )


# ============================================================================
# BACKGROUND EXECUTION HELPERS
# ============================================================================


async def _execute_deep_research_background(
    task_id: UUID,
    state: ResearchState,
    session: AsyncSession,
):
    """
    Background task that runs the entire deep research workflow.
    
    Wrapped with LangSmith tracing for observability:
    - Captures task metadata (topic, depth, user_id)
    - Tracks execution flow and multi-agent coordination
    - Enables state snapshots for debugging agent decisions
    """
    try:
        # Set the agent logging callback
        set_deep_agent_action_logger(_log_agent_action_to_db)

        # Update task status to running
        await ResearchService.update_research_task(
            session=session,
            task_id=task_id,
            status=TaskStatus.RUNNING,
        )
        
        # Update heartbeat to signal task is alive (Problem 2: Orphaned Tasks)
        await TaskRecoveryService.update_heartbeat(str(task_id))
        
        logger.info(f"Starting deep research workflow for task {task_id}")

        # Fetch task record for metadata
        task_record = await ResearchService.get_research_task(session, task_id)
        user_id = "unknown"
        research_depth = "deep"
        if task_record and hasattr(task_record, 'user_id'):
            try:
                # Safely extract user_id from ORM object without evaluating Column as bool
                user_id_value = getattr(task_record, 'user_id', None)
                user_id = str(user_id_value) if user_id_value else "unknown"
            except Exception:
                user_id = "unknown"
        if task_record:
            research_depth = getattr(task_record, 'research_depth', 'deep') or 'deep'

        # Problem 7: Deep Research Quota Re-Check
        # Validate quota again before starting (in case other tasks consumed quota while pending)
        try:
            if user_id != "unknown":
                await CostService().check_quota_mid_execution(user_id, ResearchDepth.DEEP)
                logger.info(f"Quota check passed for task {task_id} before deep research")
        except ValueError as quota_err:
            logger.warning(f"Quota check failed for task {task_id}: {quota_err}")
            await ResearchService.update_research_task(
                session=session,
                task_id=task_id,
                status=TaskStatus.FAILED,
                error_message=f"Quota exhausted before task execution: {str(quota_err)}",
            )
            raise

        # Prepare trace metadata
        trace_metadata = {
            "task_id": str(task_id),
            "topic": state.topic[:100],
            "research_depth": str(research_depth),
            "user_id": user_id,
            "num_sources_target": state.num_sources_target,
            "research_mode": "deep",
        }

        # Run orchestrator with tracing
        async with safe_trace_async(
            name=f"deep_research_task_{task_id}",
            run_type="chain",
            metadata=trace_metadata,
            tags=["research", "deep", "multi-agent"],
        ) as run_id:
            # Get LangSmith run ID if tracing is enabled
            if run_id:
                logger.debug(f"Task {task_id} tracing enabled with run ID: {run_id}")
            
            # Run the deep research orchestrator
            final_state = await run_deep_research(state)

            cost = float(final_state.cost or 0.0)
            tokens = final_state.tokens_used or 0

            # Log metrics for observability
            log_metric(
                "deep_research_completed",
                {
                    "task_id": str(task_id),
                    "cost": cost,
                    "tokens": tokens,
                    "sources": len(final_state.verified_sources or []),
                    "contradictions": len(final_state.contradictions or []),
                    "synthesis_confidence": final_state.synthesis_confidence,
                },
            )

        # Update task with final results (with LangSmith correlation)
        # Extract metadata_json safely from SQLAlchemy ORM object
        existing_metadata = {}
        if task_record and hasattr(task_record, 'metadata_json'):
            existing_metadata = task_record.metadata_json if isinstance(task_record.metadata_json, dict) else {}
        
        final_metadata = merge_metadata(
            existing_metadata,
            {"langsmith_run_id": run_id} if run_id else {},
        )
        
        # Update heartbeat one final time (Problem 2: Orphaned Tasks)
        await TaskRecoveryService.update_heartbeat(str(task_id))
        
        await ResearchService.update_research_task(
            session=session,
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            actual_cost_usd=cost,
            tokens_used=tokens,
            final_state=final_state,
            metadata_json=final_metadata,
        )
        logger.info(
            f"Deep research workflow completed for task {task_id}: "
            f"cost=${cost:.4f}, tokens={tokens}"
        )

        # Record usage for quota tracking
        try:
            if task_record is not None and task_record.user_id is not None:
                depth = ResearchDepth(str(research_depth))
                await CostService().record_usage(
                    user_id=str(task_record.user_id),
                    depth=depth,
                    tokens_used=tokens,
                    cost_usd=cost,
                )
        except Exception as usage_err:
            logger.warning(f"Failed to record usage for deep research task {task_id}: {usage_err}")

    except Exception as e:
        logger.error(
            f"Deep research workflow failed for task {task_id}: {str(e)}", exc_info=True
        )
        
        # Log failure metric
        log_metric(
            "deep_research_failed",
            {"task_id": str(task_id), "error": str(e)[:100]},
        )
        
        # Update heartbeat before marking as failed (Problem 2: Orphaned Tasks)
        await TaskRecoveryService.update_heartbeat(str(task_id))
        
        await ResearchService.update_research_task(
            session=session,
            task_id=task_id,
            status=TaskStatus.FAILED,
            error_message=str(e),
        )
    finally:
        # Clean up the task from tracking
        if str(task_id) in _running_tasks:  # type: ignore
            del _running_tasks[str(task_id)]  # type: ignore
