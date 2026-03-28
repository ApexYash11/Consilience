"""Pydantic models for research tasks."""

from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from typing import Optional, Dict, Any, List, Annotated
from operator import add


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
    user_id: Optional[UUID] = None
    title: str
    description: str
    config: ResearchConfig = Field(default_factory=ResearchConfig)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
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


def _merge_lists(existing: List, new_values: List | None) -> List:
    """Merge lists from concurrent updates - extend existing with new."""
    if new_values is None:
        return existing or []
    if existing is None:
        return new_values or []
    # Extend existing list with new values
    result = (existing or []).copy()
    result.extend(new_values or [])
    return result


def _sum_floats(existing: float, new_value: float | None) -> float:
    """Sum floats from concurrent updates."""
    if new_value is None:
        return existing or 0.0
    return (existing or 0.0) + (new_value or 0.0)


def _sum_ints(existing: int, new_value: int | None) -> int:
    """Sum integers from concurrent updates."""
    if new_value is None:
        return existing or 0
    return (existing or 0) + (new_value or 0)


class ResearchState(BaseModel):
    """
    The state object that flows through the LangGraph workflow.
    Each node adds/updates fields as it processes the research.
    
    Fields with concurrent updates use Annotated with reducer functions
    to properly merge multiple writes from parallel agents.
    """

    # Input
    task_id: str
    topic: str
    requirements: Dict[str, Any] = Field(default_factory=dict)
    num_sources_target: int = 15

    # Planner output
    research_queries: List[str] = Field(default_factory=list)
    research_plan: str = ""

    # Researchers output - Multiple agents write to this concurrently
    sources: Annotated[List[Source], _merge_lists] = Field(default_factory=list)

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

    # Metadata - Incremented by concurrent agents
    status: TaskStatus = TaskStatus.PENDING
    cost: Annotated[float, _sum_floats] = 0.0
    tokens_used: Annotated[int, _sum_ints] = 0

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    execution_metrics: Optional[Dict[str, Any]] = None

    # Error handling - Multiple agents can add errors concurrently
    errors: Annotated[List[str], _merge_lists] = Field(default_factory=list)

    # Routing decisions (used in conditional edges)
    revision_needed: bool = False  # Set by Reviewer if major issues found
    synthesis_confidence: float = 1.0  # 0.0-1.0, set by Synthesizer
    source_quality_score: float = 0.0  # 0.0-1.0, set by Verifier
    verifier_rejection_count: int = 0  # Track failed verification attempts
    max_revision_attempts: int = 2  # Prevent infinite loops
    current_revision_attempt: int = 0  # Track current attempt
    fallback_triggered: bool = False  # Did we trigger fallback search?

    class Config:
        """Pydantic config for serialization."""

        use_enum_values = True
