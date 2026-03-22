"""
Deep Research Orchestrator using LangGraph.

Orchestrates advanced research workflows with:
- 10-15 parallel sub-agents via deep researcher
- 3+ recursive research rounds
- Enhanced verification (semantic cross-referencing)
- Multi-round fact-checking with revision cycles
- Full context persistence via file system
"""

import logging
from typing import Optional, Callable, cast, Dict, Any
from uuid import UUID

from langgraph.graph import StateGraph

from ..agents.standard.planner import planner_node
from ..agents.deep.deep_researcher import deep_researcher_node
from ..agents.standard.verifier import verifier_node
from ..agents.standard.detector import detector_node
from ..agents.standard.synthesizer import synthesizer_node
from ..agents.standard.reviewer import reviewer_node
from ..agents.standard.formatter import formatter_node
from ..models.research import ResearchState, TaskStatus
from ..services.research_service import ResearchService
from ..database.connection import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Global callback for agent action logging
_agent_action_logger: Optional[Callable] = None


def set_agent_action_logger(logger_func: Callable):
    """Set the global agent action logging callback."""
    global _agent_action_logger
    _agent_action_logger = logger_func


async def _log_agent_action(
    task_id: UUID,
    agent_name: str,
    agent_type: str,
    tokens_used: int = 0,
    cost_usd: float = 0.0,
    input_data: Optional[dict] = None,
    output_data: Optional[dict] = None,
    error: Optional[str] = None,
):
    """Log agent action via the registered callback."""
    if _agent_action_logger:
        try:
            await _agent_action_logger(
                task_id=task_id,
                agent_name=agent_name,
                agent_type=agent_type,
                action=agent_type,
                tokens_used=tokens_used,
                cost_usd=cost_usd,
                input_data=input_data,
                output_data=output_data,
                error=error,
            )
        except Exception as e:
            logger.warning(f"Failed to log agent action {agent_name}: {e}")


# Node wrapper coroutines (required by LangGraph)

async def deep_researcher_wrapper(state: ResearchState) -> ResearchState:
    """Wrapper for deep researcher node."""
    async with AsyncSessionLocal() as session:
        return await deep_researcher_node(state, session)


async def verifier_deep_wrapper(state: ResearchState) -> ResearchState:
    """Wrapper for verifier with enhanced error handling."""
    # For deep research, we use the same verifier but allow failures
    try:
        return verifier_node(state)
    except Exception as e:
        logger.error(f"Verifier failed in deep research: {e}")
        state.errors.append(f"Verifier error (continuing): {str(e)}")
        # Don't fail the whole workflow; continue with unverified sources
        state.verified_sources = state.sources
        return state


async def detector_deep_wrapper(state: ResearchState) -> ResearchState:
    """Wrapper for detector with contradiction tracking."""
    result = detector_node(state)
    # Store contradictions for potential follow-up research
    if result.contradictions:
        logger.info(f"Detector found {len(result.contradictions)} contradictions")
    return result


async def synthesizer_deep_wrapper(state: ResearchState) -> ResearchState:
    """Wrapper for synthesizer with revision support."""
    result = synthesizer_node(state)
    # Set initial revision attempt
    if not hasattr(result, 'current_revision_attempt'):
        result.current_revision_attempt = 0
    return result


async def reviewer_deep_wrapper(state: ResearchState) -> ResearchState:
    """
    Wrapper for reviewer with multi-round fact-checking.
    For deep research, reviewer can trigger multiple revision cycles.
    """
    try:
        result = reviewer_node(state)
        return result
    except Exception as e:
        logger.error(f"Reviewer failed: {e}")
        state.errors.append(f"Reviewer error: {str(e)}")
        # Move to formatter anyway
        return state


async def formatter_deep_wrapper(state: ResearchState) -> ResearchState:
    """Wrapper for formatter with enhanced output."""
    return formatter_node(state)


def create_deep_research_graph():
    """
    Build LangGraph StateGraph for deep research workflows.
    
    Flow:
    
    START
        ↓
    PLANNER (break into 5+ queries for deep research)
        ↓
    DEEP-RESEARCHER (10-15 sub-agents, 3 research rounds, context persistence)
        ├─ Round 1: Initial research with 10 sub-agents
        ├─ Round 2: Gap analysis + 5 follow-up sub-agents
        └─ Round 3: Controversy resolution + 3 specialized sub-agents
        ↓
    VERIFIER (validate sources, allow some failures for deep research)
        ├─ If all sources rejected → DEEP-RESEARCHER (retry)
        └─ Else → DETECTOR
        ↓
    DETECTOR (find contradictions, more thorough)
        ↓
    SYNTHESIZER (draft paper with source cross-refs)
        ├─ If confidence < 0.5 → SYNTHESIZER-REDO
        └─ Else → REVIEWER
        ↓
    REVIEWER (fact-check, find issues)
        ├─ If issues found & attempt < 4 → SYNTHESIZER
        ├─ Increment attempt, revision_needed = False
        └─ Else → FORMATTER
        ↓
    FORMATTER (final output)
        ↓
    END
    """
    
    workflow = StateGraph(ResearchState)
    
    # Add all nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("deep_researcher", deep_researcher_wrapper)
    workflow.add_node("verifier", verifier_deep_wrapper)
    # Researcher retry node - increments rejection count
    async def researcher_retry_wrapper(state: ResearchState) -> ResearchState:
        """Increment rejection count and return unchanged state."""
        state.verifier_rejection_count += 1
        return state
    
    workflow.add_node("researcher_retry", researcher_retry_wrapper)
    workflow.add_node("detector", detector_deep_wrapper)
    workflow.add_node("synthesizer", synthesizer_deep_wrapper)
    workflow.add_node("synthesizer_redo", synthesizer_deep_wrapper)
    workflow.add_node("reviewer", reviewer_deep_wrapper)
    workflow.add_node("formatter", formatter_deep_wrapper)
    
    # Set entry point
    workflow.set_entry_point("planner")
    
    # Add edges (deterministic path)
    workflow.add_edge("planner", "deep_researcher")
    
    # Verifier routing
    def route_after_verifier(state: ResearchState) -> str:
        """Route based on source quality score."""
        if state.source_quality_score < 0.2 and state.verifier_rejection_count < 1:
            return "researcher_retry"
        else:
            return "detector"
    
    workflow.add_conditional_edges(
        "verifier",
        route_after_verifier,
        {
            "researcher_retry": "researcher_retry",
            "detector": "detector",
        }
    )
    
    # Researcher retry routes back to deep researcher for another attempt
    workflow.add_edge("researcher_retry", "deep_researcher")
    
    # Detector -> Synthesizer
    workflow.add_edge("detector", "synthesizer")
    
    # Synthesizer routing (deep research allows more attempts)
    def route_after_synthesizer(state: ResearchState) -> str:
        """Route based on synthesis confidence."""
        if state.synthesis_confidence < 0.4:
            return "synthesizer_redo"
        else:
            return "reviewer"
    
    workflow.add_conditional_edges(
        "synthesizer",
        route_after_synthesizer,
        {
            "synthesizer_redo": "synthesizer_redo",
            "reviewer": "reviewer",
        }
    )
    
    # Synthesizer redo routes back to reviewer
    workflow.add_edge("synthesizer_redo", "reviewer")
    
    # Prepare revision node (increments attempt counter)
    async def prepare_revision_wrapper(state: ResearchState) -> ResearchState:
        """Increment revision attempt and clear revision flag."""
        state.current_revision_attempt += 1
        state.revision_needed = False
        return state
    
    workflow.add_node("prepare_revision", prepare_revision_wrapper)
    
    # Reviewer routing (deep research: max 3 revision attempts)
    def route_after_reviewer(state: ResearchState) -> str:
        """Route based on revision needs and attempt count."""
        if state.revision_needed and state.current_revision_attempt < 3:
            return "prepare_revision"
        else:
            return "formatter"
    
    workflow.add_conditional_edges(
        "reviewer",
        route_after_reviewer,
        {
            "prepare_revision": "prepare_revision",
            "formatter": "formatter",
        }
    )
    
    # Prepare revision routes to synthesizer
    workflow.add_edge("prepare_revision", "synthesizer")
    
    # Formatter is terminal
    workflow.set_finish_point("formatter")
    
    # Compile and return
    graph = workflow.compile()
    logger.info("Deep research graph compiled successfully")
    return graph


async def run_deep_research(initial_state: ResearchState) -> ResearchState:
    """
    Execute the deep research workflow.
    
    Args:
        initial_state: Initial research state with topic and requirements
        
    Returns:
        Final research state with results
    """
    logger.info(f"Starting deep research workflow for task {initial_state.task_id}")
    
    try:
        # Create the graph
        graph = create_deep_research_graph()
        
        # Prepare LangSmith config with metadata for observability
        config: Dict[str, Any] = {
            "run_name": f"deep_research_{initial_state.task_id}",
            "tags": ["research", "deep", "multi-agent", "orchestration"],
            "metadata": {
                "task_id": str(initial_state.task_id),  # Convert UUID to string for JSON serialization
                "topic": initial_state.topic[:100],  # Truncate to avoid large metadata
                "research_depth": "deep",
                "research_mode": "deep",
                "num_sources_target": initial_state.num_sources_target,
                "num_queries": len(initial_state.research_queries or []),
            }
        }
        
        # Execute the workflow with enhanced config
        final_state = cast(ResearchState, await graph.ainvoke(initial_state, config=config))  # type: ignore
        
        logger.info(
            f"Deep research workflow completed for task {initial_state.task_id}: "
            f"final cost=${final_state.cost:.2f}, tokens={final_state.tokens_used}"
        )
        
        return final_state
        
    except Exception as e:
        logger.error(f"Deep research workflow failed for task {initial_state.task_id}: {e}", exc_info=True)
        initial_state.status = TaskStatus.FAILED
        initial_state.errors.append(f"Workflow error: {str(e)}")
        return initial_state

