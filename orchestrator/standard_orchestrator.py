from langgraph.graph import StateGraph
from agents.standard.planner import planner_node
from agents.standard.researcher import researcher_node
from agents.standard.verifier import verifier_node
from agents.standard.detector import detector_node
from agents.standard.synthesizer import synthesizer_node
from agents.standard.reviewer import reviewer_node
from agents.standard.formatter import formatter_node
from models.research import ResearchState
import asyncio

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
    # Start → Planner
    graph.add_edge("START", "planner")

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
    graph.add_edge("formatter", "END")

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
    try:
        final_state = await research_graph.ainvoke(
            input=state,
            config={"recursion_limit": 50}
        )
        return final_state if isinstance(final_state, ResearchState) else ResearchState(**final_state)
    except Exception as e:
        from models.research import TaskStatus
        state.status = TaskStatus.FAILED
        raise ValueError(f"Research workflow failed: {str(e)}") from e
