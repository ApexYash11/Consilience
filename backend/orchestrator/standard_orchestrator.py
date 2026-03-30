from langgraph.graph import StateGraph
from ..agents.standard.planner import planner_node
from ..agents.standard.researcher import researcher_node
from ..agents.standard.verifier import verifier_node
from ..agents.standard.detector import detector_node
from ..agents.standard.synthesizer import synthesizer_node
from ..agents.standard.reviewer import reviewer_node
from ..agents.standard.formatter import formatter_node
from ..models.research import ResearchState, TaskStatus
from ..services.research_service import ResearchService
from ..database.connection import AsyncSessionLocal
import asyncio
from datetime import datetime
from typing import Callable, Optional, Dict, Any
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

# Global callback for agent action logging
_agent_action_logger: Optional[Callable] = None

# Global callback for metadata persistence during research execution
_metadata_persistence_callback: Optional[Callable] = None


def set_agent_action_logger(logger_func: Callable):
    """
    Set the global agent action logging callback.
    
    The callback should accept:
    - task_id: UUID
    - agent_name: str
    - agent_type: str
    - tokens_used: int
    - cost_usd: float
    - input_data: dict
    - output_data: dict
    - error: Optional[str]
    """
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
                action=agent_type,  # action = agent type for simplicity
                tokens_used=tokens_used,
                cost_usd=cost_usd,
                input_data=input_data,
                output_data=output_data,
                error=error,
            )
        except Exception as e:
            logger.warning(f"Failed to log agent action {agent_name}: {e}")


def set_metadata_persistence_callback(callback_func: Callable):
    """
    Set the global metadata persistence callback for live progress tracking.
    
    The callback should accept:
    - task_id: UUID
    - current_step: str (name of current research phase)
    - sources: List[dict] (sources found so far)
    - tokens_used: int
    - cost: float
    - model: str (LLM model being used)
    """
    global _metadata_persistence_callback
    _metadata_persistence_callback = callback_func


async def _persist_metadata(
    task_id: UUID,
    current_step: str,
    sources: list,
    tokens_used: int = 0,
    cost: float = 0.0,
    model: str = "claude-3-opus",
):
    """Persist metadata update via the registered callback."""
    if _metadata_persistence_callback:
        try:
            await _metadata_persistence_callback(
                task_id=task_id,
                current_step=current_step,
                sources=sources,
                tokens_used=tokens_used,
                cost=cost,
                model=model,
            )
        except Exception as e:
            logger.warning(f"Failed to persist metadata for task {task_id}: {e}")


def _create_node_wrapper_with_persistence(
    node_func,
    step_name: str,
    node_name: str = None,
):
    """
    Wrap a node function to persist metadata after execution.
    
    This ensures that frontend sees live updates as each phase completes,
    instead of waiting for the entire workflow to finish.
    
    Args:
        node_func: The async node function to wrap
        step_name: Name of the current step (e.g., "planning", "researching")
        node_name: Optional name for logging (defaults to node_func.__name__)
    """
    async def wrapped_node(state: ResearchState) -> ResearchState:
        # Execute the node
        result_state = await node_func(state)
        
        # Immediately persist metadata so frontend gets live updates
        try:
            task_uuid = (
                result_state.task_id 
                if isinstance(result_state.task_id, UUID) 
                else UUID(result_state.task_id)
            )
            
            # Prepare sources list from current state
            sources_list = []
            if result_state.sources:
                sources_list = [{
                    "id": s.id if hasattr(s, 'id') else str(hash(s)),
                    "title": s.title if hasattr(s, 'title') else str(s),
                    "authors": s.authors if hasattr(s, 'authors') else "",
                    "publication": s.publication if hasattr(s, 'publication') else "",
                    "year": s.year if hasattr(s, 'year') else 0,
                    "url": s.url if hasattr(s, 'url') else "",
                    "credibility": s.credibility if hasattr(s, 'credibility') else 0.0,
                } for s in result_state.sources]
            
            # Persist this phase's progress
            await _persist_metadata(
                task_id=task_uuid,
                current_step=step_name,
                sources=sources_list,
                tokens_used=result_state.tokens_used or 0,
                cost=result_state.cost or 0.0,
            )
            logger.info(f"Persisted metadata for step {step_name} (task {result_state.task_id})")
        except Exception as e:
            logger.warning(f"Failed to persist metadata for step {step_name}: {e}")
        
        return result_state
    
    return wrapped_node


def create_research_graph():
    """
    Build LangGraph StateGraph with conditional routing.
    
    Flow with conditions:
    
    START
        ↓
    PLANNER (initial planning)
        ↓
    RESEARCHERS × 5 (parallel)
        ↓
    VERIFIER (validate sources)
        ├─ If source_quality_score < 0.3 → RESEARCHER-RETRY
        └─ Else → DETECTOR
        ↓
    RESEARCHER-RETRY (fallback search with different queries)
        ↓
    VERIFIER (re-validate)
        ├─ If still poor quality → ERROR
        └─ Else → DETECTOR
        ↓
    DETECTOR (find contradictions)
        ↓
    SYNTHESIZER (draft paper)
        ├─ If synthesis_confidence < 0.5 → SYNTHESIZER-REDO
        └─ Else → REVIEWER
        ↓
    REVIEWER (fact-check)
        ├─ If revision_needed & attempt < 2 → SYNTHESIZER
        ├─ Attempt += 1, revision_needed = False
        └─ Else → FORMATTER
        ↓
    FORMATTER (final output)
        ↓
    END
    """
    
    workflow = StateGraph(ResearchState)
    
    # 1. Add all node definitions (async functions that accept and return ResearchState)
    # Wrap nodes with persistence callbacks for live progress updates
    wrapped_planner = _create_node_wrapper_with_persistence(planner_node, "planning")
    workflow.add_node("planner", wrapped_planner)
    
    # Helper to wrap researcher_node for specific indices with persistence
    async def researcher_1_wrapper(state):
        result = await researcher_node(state, 0)
        # Persist after researchers complete (sources found)
        try:
            task_uuid = result.task_id if isinstance(result.task_id, UUID) else UUID(result.task_id)
            sources_list = [{
                "id": s.id if hasattr(s, 'id') else str(hash(s)),
                "title": s.title if hasattr(s, 'title') else str(s),
                "authors": s.authors if hasattr(s, 'authors') else "",
                "publication": s.publication if hasattr(s, 'publication') else "",
                "year": s.year if hasattr(s, 'year') else 0,
                "url": s.url if hasattr(s, 'url') else "",
                "credibility": s.credibility if hasattr(s, 'credibility') else 0.0,
            } for s in result.sources] if result.sources else []
            await _persist_metadata(
                task_id=task_uuid,
                current_step="researching",
                sources=sources_list,
                tokens_used=result.tokens_used or 0,
                cost=result.cost or 0.0,
            )
        except Exception as e:
            logger.warning(f"Failed to persist researcher_1 metadata: {e}")
        return result
    
    async def researcher_2_wrapper(state):
        result = await researcher_node(state, 1)
        return result
    
    async def researcher_3_wrapper(state):
        result = await researcher_node(state, 2)
        return result
    
    async def researcher_4_wrapper(state):
        result = await researcher_node(state, 3)
        return result
    
    async def researcher_5_wrapper(state):
        result = await researcher_node(state, 4)
        return result
    
    workflow.add_node("researcher_1", researcher_1_wrapper)
    workflow.add_node("researcher_2", researcher_2_wrapper)
    workflow.add_node("researcher_3", researcher_3_wrapper)
    workflow.add_node("researcher_4", researcher_4_wrapper)
    workflow.add_node("researcher_5", researcher_5_wrapper)
    
    # Wrap major phase nodes
    wrapped_verifier = _create_node_wrapper_with_persistence(verifier_node, "verifying")
    wrapped_detector = _create_node_wrapper_with_persistence(detector_node, "detecting")
    wrapped_synthesizer = _create_node_wrapper_with_persistence(synthesizer_node, "synthesizing")
    wrapped_reviewer = _create_node_wrapper_with_persistence(reviewer_node, "reviewing")
    wrapped_formatter = _create_node_wrapper_with_persistence(formatter_node, "formatting")
    
    workflow.add_node("verifier", wrapped_verifier)
    wrapped_retry = _create_node_wrapper_with_persistence(researcher_retry_node, "researching_retry")
    workflow.add_node("researcher_retry", wrapped_retry)
    workflow.add_node("detector", wrapped_detector)
    workflow.add_node("synthesizer", wrapped_synthesizer)
    wrapped_redo = _create_node_wrapper_with_persistence(synthesizer_redo_node, "synthesizing_redo")
    workflow.add_node("synthesizer_redo", wrapped_redo)
    workflow.add_node("reviewer", wrapped_reviewer)
    workflow.add_node("formatter", wrapped_formatter)
    
    # 2. Add deterministic edges (always taken)
    # Don't add edges from START; use set_entry_point() instead
    
    # PLANNER → RESEARCHERS (5-way fan-out for parallel execution)
    # LangGraph automatically synchronizes multiple incoming edges to a single node
    # so the verifier waits for all 5 researchers to complete before proceeding
    workflow.add_edge("planner", "researcher_1")
    workflow.add_edge("planner", "researcher_2")
    workflow.add_edge("planner", "researcher_3")
    workflow.add_edge("planner", "researcher_4")
    workflow.add_edge("planner", "researcher_5")
    
    # RESEARCHERS → VERIFIER (convergence point)
    # All 5 researchers feed into verifier, which synchronizes their output
    # into a single ResearchState with merged sources list
    workflow.add_edge("researcher_1", "verifier")
    workflow.add_edge("researcher_2", "verifier")
    workflow.add_edge("researcher_3", "verifier")
    workflow.add_edge("researcher_4", "verifier")
    workflow.add_edge("researcher_5", "verifier")
    
    # 3. Add CONDITIONAL edges with multi-path routing
    # These edges make intelligent decisions based on state metrics
    
    # VERIFIER ROUTING: Quality-based fallback mechanism
    # Routes to retry if sources are poor, or proceeds directly to detection
    # This implements a feedback loop for source improvement
    def route_after_verifier(state: ResearchState) -> str:
        """
        Route after verification:
        - source_quality_score < 0.3 and not yet retried → fallback search (researcher_retry)
        - source_quality_score < 0.3 and already retried → accept and continue (detector)
        - source_quality_score >= 0.3 → proceed directly (detector)
        
        Threshold explanation:
        - 0.0-0.3: Poor quality - may lack credibility, freshness, or diversity
        - 0.3-0.7: Acceptable quality - mixed credibility and freshness
        - 0.7-1.0: High quality - credible, fresh, diverse sources
        """
        if state.source_quality_score < 0.3:
            if state.fallback_triggered:
                # Already retried once; quality still poor
                logger.warning(f"Source quality still poor after retry: {state.source_quality_score}")
                return "detector"  # Proceed with poor data (better than fail)
            else:
                logger.info("Source quality low; triggering fallback search")
                state.fallback_triggered = True
                return "researcher_retry"
        return "detector"
    
    workflow.add_conditional_edges(
        "verifier",
        route_after_verifier,
        {
            "detector": "detector",
            "researcher_retry": "researcher_retry",
        }
    )
    
    workflow.add_edge("researcher_retry", "verifier")  # Loop back to verification
    
    # Continue deterministic chain
    workflow.add_edge("detector", "synthesizer")
    
    # SYNTHESIZER ROUTING: Confidence-based refinement loop
    # If confidence in synthesis is low, runs synthesizer_redo for improvement
    # Otherwise proceeds to reviewer for fact-checking
    def route_after_synthesizer(state: ResearchState) -> str:
        """
        Route based on synthesis confidence:
        - synthesis_confidence < 0.5: Insufficient confidence, try different synthesis approach
        - synthesis_confidence >= 0.5: Confident synthesis, proceed to review
        
        Confidence explanation:
        - 0.0-0.3: Low confidence - contradictions, gaps, unresolved questions
        - 0.3-0.7: Medium confidence - mostly coherent but some uncertainty
        - 0.7-1.0: High confidence - well-supported, coherent argument
        """
        if state.synthesis_confidence < 0.5:
            logger.info(f"Synthesis confidence low ({state.synthesis_confidence}); redoing with different approach")
            return "synthesizer_redo"
        return "reviewer"
    
    workflow.add_conditional_edges(
        "synthesizer",
        route_after_synthesizer,
        {
            "synthesizer_redo": "synthesizer_redo",
            "reviewer": "reviewer",
        }
    )
    
    workflow.add_edge("synthesizer_redo", "reviewer")
    
    # REVIEWER ROUTING: Revision loop with attempt limit
    # Allows up to max_revision_attempts to fix issues found during review
    # After max attempts or if no revision needed, proceeds to formatting
    def route_after_reviewer(state: ResearchState) -> str:
        """
        Route based on revision feedback:
        - revision_needed=True AND attempt < max → goes back to synthesizer
        - revision_needed=False OR attempt >= max → proceeds to formatter
        
        Attempt counter prevents infinite revision loops.
        Max default: 2 revision attempts (synthesis → review → synthesis → review → formatter)
        """
        if (
            state.revision_needed 
            and state.current_revision_attempt < state.max_revision_attempts
        ):
            logger.info(
                f"Revision needed (attempt {state.current_revision_attempt + 1}/"
                f"{state.max_revision_attempts}); returning to synthesis"
            )
            state.current_revision_attempt += 1
            state.revision_needed = False  # Reset for next cycle
            return "synthesizer"
        return "formatter"
    
    workflow.add_conditional_edges(
        "reviewer",
        route_after_reviewer,
        {
            "synthesizer": "synthesizer",
            "formatter": "formatter",
        }
    )
    
    # Don't add edge to END; use set_finish_point() instead
    # workflow.add_edge("formatter", "END")
    
    # 4. Set start and end
    workflow.set_entry_point("planner")
    workflow.set_finish_point("formatter")
    
    return workflow.compile()


# NEW: Retry researcher node
async def researcher_retry_node(state: ResearchState) -> ResearchState:
    """
    Fallback research when initial sources are poor quality.
    
    Uses revised queries focused on contradicting perspectives,
    underrepresented viewpoints, or complementary sources.
    """
    logger.info(f"Running researcher retry (fallback) for task {state.task_id}")
    
    # Generate retry queries emphasizing different angles
    retry_queries = await generate_retry_queries(
        original_topic=state.topic,
        original_queries=state.research_queries,
        contradiction_hints=state.contradictions,
    )
    
    state.research_queries = retry_queries
    
    # Re-run 5 researchers with new queries (parallel)
    # [5 parallel researcher calls like before]
    
    return state


# NEW: Redo synthesizer node
async def synthesizer_redo_node(state: ResearchState) -> ResearchState:
    """
    Re-synthesize paper with emphasis on identified gaps or contradictions.
    """
    logger.info(f"Re-synthesizing paper (confidence was {state.synthesis_confidence})")
    
    # Modified prompt emphasizing need for certainty and complete coverage
    # [Similar to synthesizer_node but with different emphasis]
    
    return state


async def generate_retry_queries(
    original_topic: str,
    original_queries: list[str],
    contradiction_hints: Optional[list] = None,
) -> list[str]:
    """
    Generate alternative search queries when initial results have low quality.
    
    Focus on:
    - Contradicting perspectives
    - Underrepresented viewpoints
    - Complementary sources
    - Academic papers vs news articles
    """
    # Placeholder: in production, use LLM to generate smart retry queries
    logger.info(f"Generating retry queries for: {original_topic}")
    
    # Return modified versions of original queries
    retry_queries = [f"{q} recent research" for q in original_queries[:3]] if original_queries else []
    return retry_queries if retry_queries else original_queries


    # Build the research graph at module load time
_research_graph = create_research_graph()


async def run_research(initial_state: ResearchState) -> ResearchState:
    """Execute research workflow with live metadata persistence at each phase."""
    
    initial_state.start_time = datetime.utcnow()
    initial_state.status = TaskStatus.RUNNING
    
    try:
        # Prepare LangSmith config with metadata for observability
        config: Dict[str, Any] = {
            "run_name": f"research_{initial_state.task_id}",
            "tags": ["research", "standard", "orchestration"],
            "metadata": {
                "task_id": str(initial_state.task_id),  # Convert UUID to string for JSON serialization
                "topic": initial_state.topic[:100],  # Truncate to avoid large metadata
                "research_depth": "standard",
                "num_sources_target": initial_state.num_sources_target,
                "num_queries": len(initial_state.research_queries or []),
            }
        }
        
        # Invoke compiled graph with wrapped nodes that auto-persist after each phase
        # No need to manually persist after - the node wrappers handle it
        final_state_dict = await _research_graph.ainvoke(
            initial_state,
            config=config  # type: ignore
        )
        
        # Convert dict back to ResearchState Pydantic model
        final_state = ResearchState(**final_state_dict) if isinstance(final_state_dict, dict) else final_state_dict
        
        # Mark as completed
        final_state.status = TaskStatus.COMPLETED
        final_state.end_time = datetime.utcnow()
        
        return final_state
        
    except asyncio.TimeoutError as e:
        logger.error(f"Workflow timeout: {str(e)}")
        initial_state.status = TaskStatus.FAILED
        initial_state.end_time = datetime.utcnow()
        raise
    except Exception as e:
        logger.error(f"Workflow error: {str(e)}", exc_info=True)
        initial_state.status = TaskStatus.FAILED
        initial_state.end_time = datetime.utcnow()
        raise
