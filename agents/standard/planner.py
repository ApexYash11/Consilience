"""
Planner Agent: Breaks down research topic into specific, searchable queries.

Uses DeepSeek R1-0528 (free) for planning phase.
- Excellent reasoning capabilities matching o1
- 164K token context for comprehensive planning
- $0.00 cost
"""

import json
import logging
import re
import time
from datetime import datetime
from uuid import UUID

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from models.research import ResearchState, TaskStatus
from config.models import (
    get_model_for_phase,
    ModelPhase,
    ResearchMode,
    OPENROUTER_CONFIG,
)
from utils.cost_estimator import estimate_cost_from_response
from services.openrouter_client import extract_token_usage
from services.research_service import ResearchService
from agents.base_agent import BaseAgent
from database.connection import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Create agent instance (with retry config)
_planner = BaseAgent("planner", "planning")


async def planner_node(state: ResearchState) -> ResearchState:
    """
    Plan research with automatic retry on failures.
    """
    
    agent_name = "planner"
    agent_type = "planning"
    sequence_number = 1
    start_time = time.time()
    state_before_status = state.status
    
    logger.info(f"[{agent_name}] Starting for task {state.task_id}")
    
    try:
        # Initialize LLM with correct model
        model = get_model_for_phase(
            research_mode=ResearchMode.STANDARD,
            phase=ModelPhase.PLANNING,
        )

        llm = ChatOpenAI(
            model=model,
            temperature=0.7,
            **OPENROUTER_CONFIG,
        )

        # 1. Prepare prompt
        prompt = f"""You are a research planning expert. Break down the topic into 5 specific, searchable research queries.
Respond with a JSON array of query strings.

Topic: {state.topic}
Requirements: {json.dumps(state.requirements or {})}

Respond ONLY with JSON array of 5 queries: ["query1", "query2", "query3", "query4", "query5"]
"""
        
        # 2. Call LLM with retry
        response = await _planner.call_llm_with_retry(
            llm.ainvoke,
            [HumanMessage(content=prompt)],
            timeout_seconds=60.0,  # 1 minute per call
        )
        
        # 3. Extract tokens
        tokens = await extract_token_usage(response)
        cost_info = estimate_cost_from_response(response, model=model)
        duration = time.time() - start_time
        
        # 4. Log to token usage table (DB)
        async with AsyncSessionLocal() as session:
            await ResearchService.log_token_usage(
                session=session,
                task_id=UUID(state.task_id),
                agent_name="planner",
                model=model,
                prompt_tokens=tokens["prompt_tokens"],
                completion_tokens=tokens["completion_tokens"],
                cost_usd=cost_info["cost"],
                input_preview=prompt[:200],
                output_preview=response.content[:200],
                duration_seconds=duration,
            )
        
        # 5. Update state
        state.research_queries = parse_queries_from_response(response)
        state.research_plan = response.content[:500]  # Store first 500 chars as plan
        state.tokens_used = (state.tokens_used or 0) + tokens["total_tokens"]
        state.cost = (state.cost or 0.0) + cost_info["cost"]
        
        # Log agent action to DB (after successful completion)
        async with AsyncSessionLocal() as session:
            # 1. Log the action itself
            await ResearchService.log_agent_action(
                session=session,
                task_id=UUID(state.task_id),
                agent_name=agent_name,
                agent_type=agent_type,
                action="planning",
                tokens_used=tokens["total_tokens"],
                cost_usd=cost_info["cost"],
                input_data={"topic": state.topic, "requirements": state.requirements},
                output_data={"queries": state.research_queries, "plan": state.research_plan},
            )
            
            # 2. Save checkpoint (state snapshot)
            await ResearchService.save_checkpoint(
                session=session,
                task_id=UUID(state.task_id),
                agent_name=agent_name,
                agent_type=agent_type,
                sequence_number=sequence_number,
                state_snapshot=state,
                status_before=state_before_status,
                status_after=TaskStatus.RUNNING,
                duration_seconds=time.time() - start_time,
            )
        
        logger.info(f"[{agent_name}] Completed successfully")
        return state
        
    except Exception as e:
        logger.error(f"[{agent_name}] Failed: {str(e)}", exc_info=True)
        
        # Log failure to DB
        async with AsyncSessionLocal() as session:
            await ResearchService.log_agent_action(
                session=session,
                task_id=UUID(state.task_id),
                agent_name=agent_name,
                agent_type=agent_type,
                action="planning",
                error=str(e),  # Include error
            )
            
            # Save checkpoint (marked non-resumable)
            await ResearchService.save_checkpoint(
                session=session,
                task_id=UUID(state.task_id),
                agent_name=agent_name,
                agent_type=agent_type,
                sequence_number=sequence_number,
                state_snapshot=state,
                status_before=state_before_status,
                status_after=TaskStatus.FAILED,
                duration_seconds=time.time() - start_time,
                error=str(e),
            )
        
        state.status = TaskStatus.FAILED
        raise ValueError(f"[{agent_name}] failed: {str(e)}") from e


def parse_queries_from_response(response) -> list[str]:
    """
    Extract research queries from LLM response.
    
    Expects response to contain a JSON-formatted list of queries
    or numbered queries in plain text format.
    
    Handles null/missing response content safely.
    """
    try:
        # Extract content from response (handle null-safety)
        if response is None:
            logger.warning("Response is None")
            return ["research topic analysis"]
        
        content = response.content if hasattr(response, 'content') and response.content else str(response)
        if not content or not isinstance(content, str):
            logger.warning(f"Invalid response content: {type(content)}")
            return ["research topic analysis"]
        
        # Try to parse as JSON first
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return [str(q).strip() for q in data[:5]]  # Max 5 queries
            elif isinstance(data, dict) and 'queries' in data:
                return [str(q).strip() for q in data['queries'][:5]]
        except json.JSONDecodeError:
            pass
        
        # Fallback: extract numbered items
        lines = content.split('\n')
        queries = []
        for line in lines:
            line = line.strip()
            # Match: "1.", "1)", "1-", "1 -", "- " patterns more robustly
            # First branch: digits followed by (period/paren OR optional-space-hyphen) then space and content
            # Second branch: bullet point (- or *) followed by space and content
            match = re.match(r'^[\d]+(?:[\.\)]|\s?-)\s+(.+)$|^[\-\*]\s+(.+)$', line)
            if match:
                # Get the captured query (group 1 or 2, whichever matched)
                query = (match.group(1) or match.group(2)).strip()
                if query and len(query) > 5:  # Ignore very short lines
                    queries.append(query)
        
        # Return up to 5 queries, or fallback
        return queries[:5] if queries else ["research topic analysis"]
        
    except Exception as e:
        logger.warning(f"Failed to parse queries from response: {str(e)}")
        return ["research topic analysis"]