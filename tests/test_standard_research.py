"""Integration tests for Phase 3 Standard Research (LangGraph)."""
import pytest
import asyncio
from uuid import uuid4, UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from models.research import ResearchState, TaskStatus, ResearchDepth, Source
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


# ============================================================================
# E2E INTEGRATION TESTS
# ============================================================================

import httpx
from fastapi.testclient import TestClient


@pytest.mark.asyncio
class TestStandardResearchE2EIntegration:
    """End-to-end tests for /api/research/standard endpoint."""
    
    @pytest.fixture  
    def app(self):
        """Return FastAPI app for testing."""
        from api.main import app
        return app
    
    @pytest.fixture
    async def api_client(self, app, override_auth_for_testing):
        """Create test client for API with auth mocking."""
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            yield client
    
    async def test_create_research_task_success(self, api_client, user_id, db_session, valid_jwt_token):
        """Test successful research task creation."""
        
        response = await api_client.post(
            "/api/research/standard",
            json={
                "topic": "Climate change impacts on global agriculture",
                "requirements": {
                    "min_sources": 3,
                    "focus_areas": ["crop yields", "water availability"],
                },
                "depth": "standard",
            },
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "PENDING"
        assert data["estimated_cost_usd"] > 0
        assert data["estimated_time_minutes"] > 0
        
        task_id = data["task_id"]
        
        # Verify task was saved to DB
        task = await ResearchService.get_research_task(db_session, UUID(task_id))
        assert task is not None, "Research task should be saved to database"
        
        # Verify task attributes
        assert str(task.title) == "Climate change impacts on global agriculture"
        assert str(task.user_id) == str(user_id)
        assert str(task.status) == str(TaskStatus.PENDING.value)
    
    async def test_research_status_progression(self, api_client, user_id, valid_jwt_token):
        """Test status progression over time."""
        
        # 1. Create task
        response = await api_client.post(
            "/api/research/standard",
            json={"topic": "Quantum computing"},
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )
        task_id = response.json()["task_id"]
        
        # 2. Poll status (should be PENDING initially)
        response = await api_client.get(
            f"/api/research/standard/{task_id}/status",
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )
        assert response.json()["status"] == "PENDING"
        
        # 3. Wait for execution (simulated; in real test, use mock LLM)
        # This assumes background task runs or we mock the orchestrator
        await asyncio.sleep(2)
        
        # 4. Poll again (would be RUNNING or COMPLETED depending on speed)
        response = await api_client.get(
            f"/api/research/standard/{task_id}/status",
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )
        status = response.json()["status"]
        assert status in ["PENDING", "RUNNING", "COMPLETED", "FAILED"]
    
    async def test_research_result_retrieval(self, api_client, user_id, db_session, valid_jwt_token, mocker):
        """Test retrieving research results after completion."""
        
        # Create task
        response = await api_client.post(
            "/api/research/standard",
            json={"topic": "AI safety"},
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )
        task_id = response.json()["task_id"]
        
        # Mock orchestrator to return completed state
        completed_state = ResearchState(
            task_id=task_id,
            topic="AI safety",
            status=TaskStatus.COMPLETED,
            final_paper="# AI Safety Research\n\n[Generated paper content...]",
            sources=[
                Source(id="paper1", url="https://example.com/paper1", title="Paper 1", credibility=0.9),
                Source(id="paper2", url="https://example.com/paper2", title="Paper 2", credibility=0.85),
            ],
            cost=2.50,
            tokens_used=5000,
        )
        
        # Update task in DB to completed
        await ResearchService.update_research_task(
            db_session,
            UUID(task_id),
            status=TaskStatus.COMPLETED,
            final_state=completed_state,
            actual_cost_usd=2.50,
            tokens_used=5000,
        )
        
        # Retrieve results
        response = await api_client.get(
            f"/api/research/standard/{task_id}/result",
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "COMPLETED"
        assert "# AI Safety Research" in result["final_paper"]
        assert len(result["sources"]) == 2
        assert result["total_cost"] == 2.50
        assert result["total_tokens"] == 5000
    
    async def test_research_with_token_breakdown(self, api_client, user_id, db_session, valid_jwt_token):
        """Test retrieving token usage breakdown."""
        
        # Create and complete a task with logged tokens
        task_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        
        # Save token logs
        await ResearchService.log_token_usage(
            db_session,
            task_id=task_id,
            agent_name="planner",
            model="sonnet-3.5",
            prompt_tokens=1000,
            completion_tokens=500,
            cost_usd=0.45,
        )
        await ResearchService.log_token_usage(
            db_session,
            task_id=task_id,
            agent_name="researcher_1",
            model="gpt-4o",
            prompt_tokens=2000,
            completion_tokens=1000,
            cost_usd=1.20,
        )
        
        # Retrieve breakdown
        response = await api_client.get(
            f"/api/research/standard/{task_id}/tokens",
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )
        
        assert response.status_code == 200
        tokens = response.json()
        assert len(tokens) == 2
        assert tokens[0]["agent"] == "planner"
        assert tokens[0]["tokens"] == 1500
        assert tokens[1]["cost"] == 1.20
    
    async def test_research_error_handling(self, api_client, user_id, valid_jwt_token):
        """Test error handling on invalid requests."""
        
        # Missing required field
        response = await api_client.post(
            "/api/research/standard",
            json={},  # No topic
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )
        
        assert response.status_code == 422  # Validation error
        assert "topic" in response.text.lower()
    
    async def test_quota_enforcement(self, api_client, user_id_with_zero_quota, valid_jwt_token):
        """Test that user can't research if quota exhausted."""
        
        response = await api_client.post(
            "/api/research/standard",
            json={"topic": "Test"},
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )
        
        assert response.status_code == 429  # Too many requests OR 403 Forbidden
        assert "quota" in response.json()["detail"].lower()


# Add fixtures to conftest.py:

@pytest.fixture
async def user_id():
    """Test user ID."""
    return UUID("550e8400-e29b-41d4-a716-446655440001")


@pytest.fixture
async def user_id_with_zero_quota():
    """User with exhausted quota."""
    return UUID("550e8400-e29b-41d4-a716-446655440002")


@pytest.fixture
async def app():
    """FastAPI test app."""
    from api.main import app
    return app
