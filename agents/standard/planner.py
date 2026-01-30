"""
Planner Agent: Breaks down research topic into specific, searchable queries.

Uses DeepSeek R1-0528 (free) for planning phase.
- Excellent reasoning capabilities matching o1
- 164K token context for comprehensive planning
- $0.00 cost
"""

from langchain_openai import ChatOpenAI
from models.research import ResearchState, TaskStatus
from config.models import (
    get_model_for_phase,
    ModelPhase,
    ResearchMode,
    OPENROUTER_CONFIG,
)
from utils.cost_estimator import estimate_cost_from_response
import json
import logging
import re

logger = logging.getLogger(__name__)


def planner_node(state: ResearchState) -> ResearchState:
    """
    PLANNER NODE - Research Query Decomposition

    **Input**: ResearchState with:
        - task_id: Unique identifier
        - topic: Research subject
        - requirements: User constraints/preferences

    **Output**: ResearchState with:
        - research_queries: List of 5 specific search queries
        - research_plan: Strategy explanation

    **Purpose**:
        Break down a broad research topic into specific, searchable queries.
        Creates the blueprint that researchers will execute in parallel.

    **Example**:
        Input topic: "Climate change impacts on agriculture"
        Output queries: [
            "climate change crop yields 2024",
            "global warming food security effects",
            "agricultural adaptation climate change",
            "extreme weather agriculture economic impact",
            "sustainable farming climate resilience"
        ]

    **Model**: DeepSeek R1-0528 (free)
        - Matches o1 performance on reasoning
        - 164K context window
        - $0.00 cost
    """
    try:
        # Initialize LLM with correct model
        model = get_model_for_phase(
            research_mode=ResearchMode.STANDARD,
            phase=ModelPhase.PLANNING,
        )

        llm = ChatOpenAI(
            model=model,
            temperature=0.7,
            max_completion_tokens=2000,
            **OPENROUTER_CONFIG,
        )

        # Build prompt with research context
        prompt = f"""You are a world-class research planning expert with deep knowledge across all academic domains.

Your task: Break down a research topic into 5 specific, searchable queries that will find the best academic sources.

RESEARCH TOPIC
--------------
{state.topic}

REQUIREMENTS & CONSTRAINTS
---------------------------
{json.dumps(state.requirements, indent=2) if state.requirements else "None specified"}

YOUR TASK
---------
1. Analyze the topic for key concepts and subtopics
2. Consider different angles and perspectives
3. Create 5 highly specific, searchable queries that:
   - Are distinct from each other (different angles)
   - Use concrete keywords for better search results
   - Cover breadth and depth of the topic
   - Respect the user's requirements

4. Briefly explain your research strategy

RESPONSE FORMAT
---------------
Return a JSON object with:
{{
    "queries": [
        "specific query 1",
        "specific query 2",
        "specific query 3",
        "specific query 4",
        "specific query 5"
    ],
    "strategy": "Brief explanation of research approach and why these queries",
    "confidence": "High/Medium/Low - your confidence in covering the topic"
}}

CRITICAL: Return ONLY valid JSON, no additional text."""

        # Call LLM
        response = llm.invoke(prompt)

        # Parse response
        content = response.content
        if not isinstance(content, str):
            content = str(content)

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                logger.error(f"Failed to parse planner response: {content}")
                raise ValueError("Invalid JSON in planner response")

        # Validate output
        if "queries" not in result or not isinstance(result["queries"], list):
            raise ValueError("Planner response missing 'queries' field")

        if len(result["queries"]) < 5:
            logger.warning(
                f"Planner returned {len(result['queries'])} queries, expected 5"
            )

        # Update state with planning results
        state.research_queries = result["queries"]
        state.research_plan = result.get("strategy", "Research strategy not provided")

        # Track tokens and cost
        cost_info = estimate_cost_from_response(response, model)
        state.tokens_used = (state.tokens_used or 0) + cost_info.get("total_tokens", 0)
        state.cost = (state.cost or 0.0) + cost_info.get("cost", 0.0)

        logger.info(
            f"Planner created {len(state.research_queries)} queries for topic: {state.topic}"
        )

        return state

    except Exception as e:
        logger.error(f"Planner node failed: {str(e)}", exc_info=True)
        state.status = TaskStatus.FAILED
        raise ValueError(f"Planning failed: {str(e)}") from e