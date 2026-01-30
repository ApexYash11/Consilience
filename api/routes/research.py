"""Research routes for task management and orchestration."""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from uuid import uuid4
from datetime import datetime
from typing import Optional


# Placeholder models and functions
class UserResponse(BaseModel):
    id: str
    email: str
    subscription_tier: str = "free"

class ResearchState(BaseModel):  # type: ignore
    task_id: str
    topic: str
    requirements: dict
    start_time: datetime
    cost: float = 0.0
    
    # Use the default BaseModel.dict() implementation so callers get real state data.

class Task(BaseModel):  # type: ignore
    id: str = ""
    user_id: str = ""
    status: str = "pending"
    metadata: dict = {}
    actual_cost: float = 0.0
    result_data: dict = {}

def get_current_user():  # type: ignore
    """Placeholder for authentication"""
    return UserResponse(id="user_id", email="user@example.com")

async def save_research_task(*args, **kwargs):  # type: ignore
    """Placeholder for database save"""
    return Task(id=str(uuid4()), user_id=kwargs.get('user_id', ''))

async def get_research_task(*args, **kwargs):  # type: ignore
    """Placeholder for database fetch"""
    return Task(id=args[0] if args else "", user_id="user_id")

async def update_research_task(*args, **kwargs):  # type: ignore
    """Placeholder for database update"""
    return Task(id=kwargs.get('task_id', ''))

async def run_research(*args, **kwargs):  # type: ignore
    """Placeholder for orchestrator"""
    return ResearchState(
        task_id="",
        topic="",
        requirements={},
        start_time=datetime.utcnow(),
        cost=0.0
    )

router = APIRouter(prefix="/api/research", tags=["research"])


@router.post("/standard")
async def create_standard_research(
    topic: str,
    background_tasks: BackgroundTasks,
    requirements: Optional[dict] = None,
    user: UserResponse = Depends(get_current_user)  # type: ignore
) -> dict:
    """
    POST /api/research/standard
    
    Creates a new standard research task
    
    Body:
    {
        "topic": "Climate change impacts on agriculture",
        "requirements": {"length": 15, "depth": "standard"}
    }
    
    Returns:
    {
        "task_id": "uuid-xxx",
        "status": "pending",
        "estimated_cost": 0.45,
        "estimated_time_minutes": 3
    }
    """
    
    # Check user tier
    if user.subscription_tier != "free":  # type: ignore
        raise HTTPException(status_code=403, detail="Only free tier")
    
    # Create research state
    state = ResearchState(
        task_id=str(uuid4()),
        topic=topic,
        requirements=requirements or {},
        start_time=datetime.utcnow()
    )
    
    # Save to database
    task = await save_research_task(
        user_id=user.id,
        task_type="standard",
        topic=topic,
        status="pending"
    )
    
    # Start workflow in background
    background_tasks.add_task(
        execute_research,
        task_id=task.id,
        state=state
    )
    
    return {  # type: ignore
        "task_id": task.id,
        "status": "pending",
        "estimated_cost": 0.45,
        "estimated_time_minutes": 3
    }


@router.get("/standard/{task_id}/status")
async def get_research_status(
    task_id: str,
    user: UserResponse = Depends(get_current_user)  # type: ignore
) -> dict:
    """
    GET /api/research/standard/{task_id}/status
    
    Gets the current status of a research task
    
    Returns:
    {
        "task_id": "uuid-xxx",
        "status": "in_progress",
        "current_step": "researchers",
        "progress": 35,  # percentage
        "cost_so_far": 0.12,
        "estimated_completion_minutes": 2
    }
    """
    
    task = await get_research_task(task_id)  # type: ignore

    # Return 404 if task not found
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    # Verify user owns task
    if task.user_id != user.id:  # type: ignore
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return {  # type: ignore
        "task_id": task.id,
        "status": task.status,
        "current_step": task.metadata.get("current_step"),
        "progress": task.metadata.get("progress", 0),
        "cost_so_far": task.actual_cost,
        "estimated_completion_minutes": 2
    }


@router.get("/standard/{task_id}/result")
async def get_research_result(
    task_id: str,
    user: UserResponse = Depends(get_current_user)  # type: ignore
) -> dict:
    """
    GET /api/research/standard/{task_id}/result
    
    Gets the final research paper
    
    Returns:
    {
        "task_id": "uuid-xxx",
        "status": "completed",
        "final_paper": "# Climate Change\n\n...",
        "sources": [...],
        "contradictions": [...],
        "total_cost": 0.45,
        "total_tokens": 28000
    }
    """
    
    task = await get_research_task(task_id)  # type: ignore

    # Return 404 if task not found
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.user_id != user.id:  # type: ignore
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if task.status != "completed":  # type: ignore
        raise HTTPException(status_code=400, detail="Task not completed")
    
    # Safely extract result data to avoid KeyError when keys are missing
    result = task.result_data or {}
    return {
        "task_id": task.id,
        "status": task.status,
        "final_paper": result.get("final_paper", ""),
        "sources": result.get("sources", []),
        "contradictions": result.get("contradictions", []),
        "total_cost": task.actual_cost,
        "total_tokens": result.get("tokens_used", 0),
    }


async def execute_research(task_id: str, state: ResearchState):
    """
    Background task that runs the entire workflow
    """
    try:
        # Run the graph
        final_state = await run_research(state)  # type: ignore
        
        # Save results
        await update_research_task(  # type: ignore
            task_id=task_id,
            status="completed",
            result_data=final_state.dict(),  # type: ignore
            actual_cost=final_state.cost  # type: ignore
        )
    except Exception as e:
        await update_research_task(  # type: ignore
            task_id=task_id,
            status="failed",
            error=str(e)
        )
