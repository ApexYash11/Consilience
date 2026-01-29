"""Research routes for task management and orchestration."""
from fastapi import APIRouter, Depends, HTTPException
from models.research import ResearchTaskCreate, ResearchTaskResponse, ResearchDepth
from services.research_service import ResearchService

router = APIRouter(prefix="/api/research", tags=["research"])


@router.post("/estimate")
async def estimate_cost(request: ResearchTaskCreate, service: ResearchService = Depends()):
    """Estimate the cost and time for research."""
    return service.estimate_cost(request)


@router.post("/start", response_model=ResearchTaskResponse)
async def start_research(request: ResearchTaskCreate, service: ResearchService = Depends()):
    """Start a research task (standard or deep)."""
    return service.start_research_task(request)


@router.get("/status/{task_id}", response_model=ResearchTaskResponse)
async def get_status(task_id: str, service: ResearchService = Depends()):
    """Get status of a research task."""
    task = service.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
