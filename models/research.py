"""Pydantic models for research tasks."""
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from typing import Optional, Dict, Any


class ResearchDepth(str, Enum):
    """Research depth levels."""
    STANDARD = "standard"
    DEEP = "deep"


class TaskStatus(str, Enum):
    """Research task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResearchConfig(BaseModel):
    depth: str = "standard"
    max_agents: int = 5
    max_revision_cycles: int = 3
    max_duration_minutes: int = 40
    enable_fact_checking: bool = False
    enable_citation_chain: bool = False


class ResearchTask(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: Optional[UUID]
    title: str
    description: str
    config: ResearchConfig = Field(default_factory=ResearchConfig)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

