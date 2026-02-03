"""Research routes for task management and orchestration."""
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user
from models.research import ResearchState, ResearchDepth, TaskStatus
from services.research_service import ResearchService
from orchestrator.standard_orchestrator import run_research, set_agent_action_logger
from database.connection import AsyncSessionLocal

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
    estimated_time_minutes: int


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


router = APIRouter(prefix="/api/research", tags=["research"])

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

        # Run the orchestrator
        final_state = await run_research(state)

        # Update task with final results
        await ResearchService.update_research_task(
            session=session,
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            actual_cost_usd=float(final_state.cost or 0.0),
            tokens_used=final_state.tokens_used,
            final_state=final_state,
        )
        logger.info(
            f"Research workflow completed for task {task_id}: "
            f"cost=${final_state.cost:.4f}, tokens={final_state.tokens_used}"
        )

    except Exception as e:
        logger.error(f"Research workflow failed for task {task_id}: {str(e)}", exc_info=True)
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


@router.post("/standard", response_model=CreateResearchResponse)
async def create_standard_research(
    request: CreateResearchRequest,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),  # type: ignore
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
            user_id=UUID(user.id),  # type: ignore
            topic=request.topic,
            research_depth=request.depth,
            title=f"Research: {request.topic}",
            description=f"Standard research task for {request.topic}",
            estimated_cost_usd=cost_estimate["estimated_cost_usd"],
        )
        logger.info(f"Created research task {task.id} for user {user.id}")  # type: ignore

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
        raise HTTPException(status_code=500, detail=f"Failed to create research task: {str(e)}")


@router.get("/standard/{task_id}/status", response_model=ResearchStatusResponse)
async def get_research_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),  # type: ignore
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
        if task.user_id != UUID(user.id):  # type: ignore
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


@router.get("/standard/{task_id}/result", response_model=ResearchResultResponse)
async def get_research_result(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),  # type: ignore
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
        if task.user_id != UUID(user.id):  # type: ignore
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Check if task is completed
        if task.status != TaskStatus.COMPLETED:  # type: ignore
            raise HTTPException(
                status_code=400,
                detail=f"Task not completed. Current status: {task.status.value}"  # type: ignore
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


