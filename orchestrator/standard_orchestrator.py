from langgraph.graph import StateGraph
from agents.standard.planner import planner_node
from agents.standard.researcher import researcher_node
from agents.standard.verifier import verifier_node
from agents.standard.detector import detector_node
from agents.standard.synthesizer import synthesizer_node
from agents.standard.reviewer import reviewer_node
from agents.standard.formatter import formatter_node
from models.research import ResearchState, TaskStatus
import asyncio
from datetime import datetime
from typing import Callable, Optional
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

# Global callback for agent action logging
_agent_action_logger: Optional[Callable] = None


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


def create_research_graph():
    """
    Creates a LangGraph state machine for standard research workflow.
    
    Flow:
        START
          ↓
        Planner (breaks topic into queries)
          ↓
        Researchers (5 parallel agents search sources)
          ↓
        Verifier (validates credibility)
          ↓
        Detector (finds contradictions)
          ↓
        Synthesizer (writes draft paper)
          ↓
        Reviewer (critiques draft)
          ↓
        Formatter (finalizes output)
          ↓
        END
    
    Returns:
        Compiled LangGraph that can execute the workflow
    """
    graph = StateGraph(ResearchState)

    # Add nodes (each node is a research step)
    graph.add_node("planner", planner_node)
    graph.add_node("researcher_0", lambda state: researcher_node(state, 0))  # type: ignore
    graph.add_node("researcher_1", lambda state: researcher_node(state, 1))  # type: ignore
    graph.add_node("researcher_2", lambda state: researcher_node(state, 2))  # type: ignore
    graph.add_node("researcher_3", lambda state: researcher_node(state, 3))  # type: ignore
    graph.add_node("researcher_4", lambda state: researcher_node(state, 4))  # type: ignore
    graph.add_node("verifier", verifier_node)
    graph.add_node("detector", detector_node)
    graph.add_node("synthesizer", synthesizer_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("formatter", formatter_node)

    # Add edges (define workflow execution order)
    # Set the entry point to planner
    graph.set_entry_point("planner")

    # Planner → All researchers (parallel execution)
    graph.add_edge("planner", "researcher_0")
    graph.add_edge("planner", "researcher_1")
    graph.add_edge("planner", "researcher_2")
    graph.add_edge("planner", "researcher_3")
    graph.add_edge("planner", "researcher_4")

    # All researchers must complete before Verifier starts (join point)
    graph.add_edge("researcher_0", "verifier")
    graph.add_edge("researcher_1", "verifier")
    graph.add_edge("researcher_2", "verifier")
    graph.add_edge("researcher_3", "verifier")
    graph.add_edge("researcher_4", "verifier")

    # Sequential nodes after verification
    graph.add_edge("verifier", "detector")
    graph.add_edge("detector", "synthesizer")
    graph.add_edge("synthesizer", "reviewer")
    graph.add_edge("reviewer", "formatter")
    
    # Set the finish point
    graph.set_finish_point("formatter")

    return graph.compile()


# Compile the graph once on module load
research_graph = create_research_graph()


async def run_research(state: ResearchState) -> ResearchState:
    """
    Execute the entire standard research workflow.
    
    Args:
        state: ResearchState with task_id and topic
        
    Returns:
        ResearchState with final_paper and all intermediate results
        
    Raises:
        ValueError: If workflow fails at any step
    """
    # Track execution timing
    execution_start = datetime.utcnow()
    state.start_time = execution_start
    
    try:
        final_state = await research_graph.ainvoke(
            input=state,
            config={"recursion_limit": 50}
        )
        
        # Ensure state is a ResearchState object
        if not isinstance(final_state, ResearchState):
            final_state = ResearchState(**final_state)

        # Preserve the original start time we recorded before invocation
        try:
            final_state.start_time = final_state.start_time or execution_start
        except Exception:
            final_state.start_time = execution_start

        # Update execution metadata
        final_state.end_time = datetime.utcnow()
        final_state.status = TaskStatus.COMPLETED
        
        logger.info(
            f"Research workflow completed for task {final_state.task_id}: "
            f"cost=${final_state.cost:.4f}, tokens={final_state.tokens_used}"
        )
        return final_state
    
    except Exception as e:
        state.status = TaskStatus.FAILED
        state.end_time = datetime.utcnow()
        logger.error(f"Research workflow failed for task {state.task_id}: {str(e)}", exc_info=True)
        raise ValueError(f"Research workflow failed: {str(e)}") from e
