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
from ...orchestrator.standard_orchestrator import run_research, set_agent_action_logger
from ...orchestrator.deep_orchestrator import (
    run_deep_research,
    set_agent_action_logger as set_deep_agent_action_logger,
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
    task_id: str
    status: str
    progress_percent: int
    cost_so_far: float
    tokens_used: int


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
        # Set the agent logging callback for this execution
        set_agent_action_logger(_log_agent_action_to_db)

        # Update task status to running
        await ResearchService.update_research_task(
            session=session,
            task_id=task_id,
            status=TaskStatus.RUNNING,
        )
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
        # Fetch paginated research tasks
        tasks, total_count = await ResearchService.get_user_research_tasks(
            session=db,
            user_id=UUID(user.user_id),  # type: ignore
            page=max(1, page),  # Ensure page >= 1
            page_size=min(page_size, 100),  # Cap page_size at 100
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
                title=task.title,
                description=task.description,
                depth=str(task.research_depth),
                status=str(task.status),
                created_at=task.created_at,
                completed_at=task.completed_at,
                estimated_cost_usd=float(task.estimated_cost_usd) if task.estimated_cost_usd else None,
                actual_cost_usd=float(task.actual_cost_usd) if task.actual_cost_usd else None,
                progress_percent=progress_percent,
            )
            task_items.append(item)

        # Calculate total pages
        total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0

        return ResearchListResponse(
            tasks=task_items,
            total_count=total_count,
            page=page,
            page_size=page_size,
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

        # Verify user owns task
        if task.user_id != UUID(user.user_id):  # type: ignore
            raise HTTPException(status_code=403, detail="Not authorized")

        # Estimate progress based on status
        progress_map = {
            TaskStatus.PENDING: 0,
            TaskStatus.RUNNING: 50,
            TaskStatus.COMPLETED: 100,
            TaskStatus.FAILED: 0,
        }
        progress = progress_map.get(task.status, 0)  # type: ignore

        return ResearchStatusResponse(
            task_id=str(task.id),
            status=task.status.value,  # type: ignore
            progress_percent=progress,
            cost_so_far=float(task.actual_cost_usd or 0.0),  # type: ignore
            tokens_used=task.tokens_used or 0,  # type: ignore
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

        # Verify user owns task
        if task.user_id != UUID(user.user_id):  # type: ignore
            raise HTTPException(status_code=403, detail="Not authorized")

        # Check if task is completed
        if task.status != TaskStatus.COMPLETED:  # type: ignore
            raise HTTPException(
                status_code=400,
                detail=f"Task not completed. Current status: {task.status.value}",  # type: ignore
            )

        # Extract result data from final_state_json if available, fallback to metadata_json
        result_data = task.final_state_json or task.metadata_json or {}  # type: ignore

        return ResearchResultResponse(
            task_id=str(task.id),
            status=task.status.value,  # type: ignore
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

        # Verify user owns task
        if task.user_id != UUID(user.user_id):  # type: ignore
            raise HTTPException(status_code=403, detail="Not authorized")

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
        progress = progress_map.get(task.status, 0)  # type: ignore

        return ResearchStatusResponse(
            task_id=str(task.id),
            status=task.status.value,  # type: ignore
            progress_percent=progress,
            cost_so_far=float(task.actual_cost_usd or 0.0),  # type: ignore
            tokens_used=task.tokens_used or 0,  # type: ignore
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

        # Verify user owns task
        if task.user_id != UUID(user.user_id):  # type: ignore
            raise HTTPException(status_code=403, detail="Not authorized")

        # Verify it's a deep research task
        if not (task.metadata_json and task.metadata_json.get("research_depth") == "deep"):  # type: ignore
            raise HTTPException(status_code=404, detail="Task not found")

        # Check if task is completed
        if task.status != TaskStatus.COMPLETED:  # type: ignore
            raise HTTPException(
                status_code=400,
                detail=f"Task not completed. Current status: {task.status.value}",  # type: ignore
            )

        # Extract result data from final_state_json
        result_data = task.final_state_json or task.metadata_json or {}  # type: ignore

        return ResearchResultResponse(
            task_id=str(task.id),
            status=task.status.value,  # type: ignore
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
