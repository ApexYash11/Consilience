"""Pydantic models for research tasks."""
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from typing import Optional, Dict, Any, List


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


class Source(BaseModel):
    """Represents a research source (paper, article, etc.)"""
    id: str
    title: str
    authors: Optional[List[str]] = None
    publication: Optional[str] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    credibility: float = Field(default=0.5, ge=0.0, le=1.0)
    verified: bool = False
    excerpt: Optional[str] = None
    relevance_score: float = Field(default=0.5, ge=0, le=1)


class Contradiction(BaseModel):
    """Represents conflicting information from two sources"""
    source_a_id: str
    source_b_id: str
    claim_a: str
    claim_b: str
    severity: str = Field(default="minor", description="critical, major, minor")
    description: str


class ResearchState(BaseModel):
    """
    The state object that flows through the LangGraph workflow.
    Each node adds/updates fields as it processes the research.
    """
    # Input
    task_id: str
    topic: str
    requirements: Dict[str, Any] = Field(default_factory=dict)
    num_sources_target: int = 15

    # Planner output
    research_queries: List[str] = Field(default_factory=list)
    research_plan: str = ""

    # Researchers output
    sources: List[Source] = Field(default_factory=list)

    # Verifier output
    verified_sources: List[Source] = Field(default_factory=list)
    verification_notes: str = ""

    # Detector output
    contradictions: List[Contradiction] = Field(default_factory=list)
    contradiction_analysis: str = ""

    # Synthesizer output
    draft_paper: str = ""
    draft_outline: List[str] = Field(default_factory=list)

    # Reviewer output
    review_feedback: str = ""
    issues_found: List[str] = Field(default_factory=list)
    revision_needed: bool = False

    # Formatter output
    final_paper: str = ""

    # Metadata
    status: TaskStatus = TaskStatus.PENDING
    cost: float = 0.0
    tokens_used: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    class Config:
        """Pydantic config for serialization."""
        use_enum_values = True
