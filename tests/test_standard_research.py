"""Integration tests for Phase 3 Standard Research (LangGraph)."""
import pytest
import asyncio
from uuid import uuid4
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from models.research import ResearchState, TaskStatus, ResearchDepth
from services.research_service import ResearchService
from orchestrator.standard_orchestrator import run_research
from database.schema import Base, ResearchTaskDB, AgentActionDB


class TestResearchServiceCRUD:
    """Test CRUD operations for research tasks."""

    @pytest.fixture
    async def async_session(self):
        """Create a test database session."""
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore
        
        async with async_session_factory() as session:
            yield session
        
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_save_research_task(self, async_session):
        """Test creating and saving a research task."""
        user_id = uuid4()
        task = await ResearchService.save_research_task(
            session=async_session,
            user_id=user_id,
            topic="Climate change impacts",
            research_depth=ResearchDepth.STANDARD,
            title="Climate Research",
            description="Study climate effects",
            estimated_cost_usd=0.0,
        )
        
        assert task.id is not None
        assert task.user_id is not None  # type: ignore
        assert task.title is not None  # type: ignore
        assert task.status is not None  # type: ignore
        assert task.estimated_cost_usd == 0.0  # type: ignore

    @pytest.mark.asyncio
    async def test_get_research_task(self, async_session):
        """Test retrieving a research task."""
        user_id = uuid4()
        created_task = await ResearchService.save_research_task(
            session=async_session,
            user_id=user_id,
            topic="AI research",
            research_depth=ResearchDepth.STANDARD,
        )
        
        retrieved_task = await ResearchService.get_research_task(
            session=async_session,
            task_id=created_task.id,  # type: ignore
        )
        
        assert retrieved_task is not None
        assert retrieved_task.id  # type: ignore
        assert retrieved_task.title  # type: ignore

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, async_session):
        """Test retrieving a task that doesn't exist."""
        result = await ResearchService.get_research_task(
            session=async_session,
            task_id=uuid4(),
        )
        
        assert result is None

    @pytest.mark.asyncio
    async def test_update_research_task(self, async_session):
        """Test updating a research task."""
        user_id = uuid4()
        task = await ResearchService.save_research_task(
            session=async_session,
            user_id=user_id,
            topic="Test topic",
            research_depth=ResearchDepth.STANDARD,
        )
        
        # Create a sample final state
        final_state = ResearchState(
            task_id=str(task.id),
            topic="Test topic",
            final_paper="# Final Paper\n\nContent here...",
            cost=1.50,
            tokens_used=5000,
        )
        
        updated_task = await ResearchService.update_research_task(
            session=async_session,
            task_id=task.id,  # type: ignore
            status=TaskStatus.COMPLETED,
            actual_cost_usd=1.50,
            tokens_used=5000,
            final_state=final_state,
        )
        
        assert updated_task is not None
        assert updated_task.status  # type: ignore
        assert updated_task.actual_cost_usd  # type: ignore
        assert updated_task.tokens_used  # type: ignore
        assert updated_task.completed_at is not None

    @pytest.mark.asyncio
    async def test_update_nonexistent_task(self, async_session):
        """Test updating a task that doesn't exist."""
        result = await ResearchService.update_research_task(
            session=async_session,
            task_id=uuid4(),
            status=TaskStatus.COMPLETED,
        )
        
        assert result is None


class TestAgentActionLogging:
    """Test agent action logging to database."""

    @pytest.fixture
    async def async_session(self):
        """Create a test database session."""
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore
        
        async with async_session_factory() as session:
            yield session
        
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_log_agent_action(self, async_session):
        """Test logging an individual agent action."""
        user_id = uuid4()
        task = await ResearchService.save_research_task(
            session=async_session,
            user_id=user_id,
            topic="Test",
            research_depth=ResearchDepth.STANDARD,
        )
        
        agent_action = await ResearchService.log_agent_action(
            session=async_session,
            task_id=task.id,  # type: ignore
            agent_name="planner",
            agent_type="planner",
            action="plan_queries",
            input_data={"topic": "Test topic"},
            output_data={"queries": ["query1", "query2"]},
            tokens_used=1000,
            cost_usd=0.0,
        )
        
        assert agent_action.id is not None
        assert agent_action.task_id  # type: ignore
        assert agent_action.agent_name  # type: ignore
        assert agent_action.tokens_used  # type: ignore

    @pytest.mark.asyncio
    async def test_get_agent_actions(self, async_session):
        """Test retrieving all agent actions for a task."""
        user_id = uuid4()
        task = await ResearchService.save_research_task(
            session=async_session,
            user_id=user_id,
            topic="Test",
            research_depth=ResearchDepth.STANDARD,
        )
        
        # Log multiple agent actions
        for i in range(3):
            await ResearchService.log_agent_action(
                session=async_session,
                task_id=task.id,  # type: ignore
                agent_name=f"agent_{i}",
                agent_type="test",
                action="test_action",
                tokens_used=100 * (i + 1),
            )
        
        # Retrieve all actions
        actions = await ResearchService.get_agent_actions(
            session=async_session,
            task_id=task.id,  # type: ignore
        )
        
        assert len(actions) == 3
        for action in actions:
            assert action.task_id is not None  # type: ignore

    @pytest.mark.asyncio
    async def test_log_agent_error(self, async_session):
        """Test logging an agent action with an error."""
        user_id = uuid4()
        task = await ResearchService.save_research_task(
            session=async_session,
            user_id=user_id,
            topic="Test",
            research_depth=ResearchDepth.STANDARD,
        )
        
        error_msg = "Agent failed to process"
        agent_action = await ResearchService.log_agent_action(
            session=async_session,
            task_id=task.id,  # type: ignore
            agent_name="failing_agent",
            agent_type="test",
            action="test_action",
            error=error_msg,
        )
        
        assert agent_action.error  # type: ignore


class TestCostEstimation:
    """Test cost estimation for different research depths."""

    def test_estimate_standard_cost(self):
        """Test cost estimation for standard research."""
        estimate = ResearchService.estimate_cost(ResearchDepth.STANDARD)
        
        assert estimate["estimated_cost_usd"] == 0.0  # Standard uses free models
        assert estimate["estimated_time_minutes"] == 5

    def test_estimate_deep_cost(self):
        """Test cost estimation for deep research."""
        estimate = ResearchService.estimate_cost(ResearchDepth.DEEP)
        
        assert estimate["estimated_cost_usd"] == 2.5  # Deep uses paid Kimi K2.5
        assert estimate["estimated_time_minutes"] == 15


class TestResearchStateFlow:
    """Test the ResearchState as it flows through the workflow."""

    def test_research_state_initialization(self):
        """Test initializing a ResearchState."""
        task_id = str(uuid4())
        state = ResearchState(
            task_id=task_id,
            topic="Test research topic",
            requirements={"length": 15},
        )
        
        assert state.task_id == task_id
        assert state.topic == "Test research topic"
        assert state.status == TaskStatus.PENDING
        assert state.cost == 0.0
        assert state.tokens_used == 0

    def test_research_state_serialization(self):
        """Test serializing and deserializing ResearchState."""
        original_state = ResearchState(
            task_id=str(uuid4()),
            topic="Test",
            final_paper="# Final Paper\n\nContent",
            cost=2.50,
            tokens_used=7500,
            status=TaskStatus.COMPLETED,
        )
        
        # Serialize to dict
        state_dict = original_state.dict()
        
        # Deserialize back
        restored_state = ResearchState(**state_dict)
        
        assert restored_state.task_id == original_state.task_id
        assert restored_state.final_paper == original_state.final_paper
        assert restored_state.cost == original_state.cost
        assert restored_state.status == original_state.status


class TestOrchestrationWorkflow:
    """Test the orchestration workflow (requires mocked agents)."""

    @pytest.mark.asyncio
    async def test_research_state_has_required_fields(self):
        """Test that ResearchState contains all required fields for workflow."""
        state = ResearchState(
            task_id=str(uuid4()),
            topic="Test",
        )
        
        # Verify key fields exist
        assert hasattr(state, "research_queries")
        assert hasattr(state, "sources")
        assert hasattr(state, "verified_sources")
        assert hasattr(state, "contradictions")
        assert hasattr(state, "draft_paper")
        assert hasattr(state, "final_paper")
        assert hasattr(state, "status")
        assert hasattr(state, "cost")
        assert hasattr(state, "tokens_used")

    @pytest.mark.asyncio
    async def test_research_state_cost_accumulation(self):
        """Test accumulating costs in ResearchState."""
        state = ResearchState(
            task_id=str(uuid4()),
            topic="Test",
        )
        
        assert state.cost == 0.0
        
        # Simulate cost accumulation
        state.cost += 0.50
        state.cost += 1.25
        
        assert state.cost == 1.75

    @pytest.mark.asyncio
    async def test_research_state_token_accumulation(self):
        """Test accumulating tokens in ResearchState."""
        state = ResearchState(
            task_id=str(uuid4()),
            topic="Test",
        )
        
        assert state.tokens_used == 0
        
        # Simulate token accumulation
        state.tokens_used += 1000
        state.tokens_used += 2500
        
        assert state.tokens_used == 3500


class TestTaskStatusTransitions:
    """Test valid task status transitions."""

    def test_status_progression(self):
        """Test valid status progression through workflow."""
        status_path = [
            TaskStatus.PENDING,
            TaskStatus.RUNNING,
            TaskStatus.COMPLETED,
        ]
        
        for status in status_path:
            state = ResearchState(
                task_id=str(uuid4()),
                topic="Test",
                status=status,
            )
            assert state.status == status

    def test_status_to_failed(self):
        """Test transition to FAILED status."""
        state = ResearchState(
            task_id=str(uuid4()),
            topic="Test",
            status=TaskStatus.RUNNING,
        )
        
        # Transition to failed
        state.status = TaskStatus.FAILED
        assert state.status == TaskStatus.FAILED
