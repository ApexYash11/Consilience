"""
Deep Researcher Agent: Advanced research with recursive refinement.

Uses Claude 3.5 Sonnet (premium) or GPT-4 for deep research phase.
- Excellent reasoning and analysis
- Can spawn sub-agents for specialized search
- Manages persistent context via file system
- Recursive research rounds (up to 3)
- Enhanced fact-checking and cross-referencing
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from uuid import UUID

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from models.research import ResearchState, Source, TaskStatus
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
from tools.file_system import (
    write_file,
    read_file,
    append_file,
    write_todos,
    read_todos,
    update_todo_status,
)

logger = logging.getLogger(__name__)

# Create agent instance with retry config
_deep_researcher = BaseAgent("deep_researcher", "research")


class DeepResearchContext:
    """Manages the context and state for a deep research session."""
    
    def __init__(self, task_id: UUID):
        self.task_id = task_id
        self.research_round = 0
        self.max_rounds = 3
        self.all_sources: List[Source] = []
        self.research_history: List[Dict[str, Any]] = []
        self.contradictions_found: List[Dict[str, Any]] = []
        
    async def initialize(self) -> None:
        """Initialize the research context (create directories, etc.)."""
        from tools.file_system import ensure_task_directory
        ensure_task_directory(self.task_id)
        logger.info(f"Initialized deep research context for task {self.task_id}")
    
    async def save_round_results(
        self,
        sources: List[Source],
        analysis: str,
    ) -> None:
        """Save results from the current research round to persistent storage."""
        self.research_round += 1
        
        # Format sources for file storage
        sources_json = json.dumps([s.model_dump() for s in sources], indent=2)
        
        # Write round results
        await write_file(
            task_id=self.task_id,
            filename=f"research_round_{self.research_round}.json",
            content=sources_json,
        )
        
        # Append analysis
        await append_file(
            task_id=self.task_id,
            filename="research_analysis.md",
            content=f"\n## Round {self.research_round}\n{analysis}\n",
        )
        
        # Update all sources
        self.all_sources.extend(sources)
        self.research_history.append({
            "round": self.research_round,
            "sources_found": len(sources),
            "timestamp": datetime.now().isoformat(),
        })
        
        logger.info(f"Saved round {self.research_round} results for task {self.task_id}")
    
    async def get_research_gap_analysis(self) -> str:
        """
        Analyze gaps in current research and suggest next steps.
        Returns a string describing areas needing more investigation.
        """
        if not self.all_sources:
            return "Need to find initial sources on the topic."
        
        # Categorize sources by topic area
        categories: Dict[str, int] = {}
        for source in self.all_sources:
            category = source.excerpt[:30] if source.excerpt else "general"
            categories[category] = categories.get(category, 0) + 1
        
        # Identify gaps
        gaps = []
        if len(self.all_sources) < 10:
            gaps.append(f"Low source count: {len(self.all_sources)}/10 target")
        
        # Check for controversial areas
        if self.contradictions_found:
            gaps.append(f"Found {len(self.contradictions_found)} contradictions needing investigation")
        
        # Check coverage
        if len(categories) < 3:
            gaps.append("Research is too narrow; need sources from different angles")
        
        return "Gaps identified:\n" + "\n".join(f"- {gap}" for gap in gaps)


async def deep_researcher_node(
    state: ResearchState,
    session: Optional[AsyncSession] = None,
) -> ResearchState:
    """
    Deep researcher node with recursive refinement and file system context.
    
    This is a more sophisticated research agent that:
    1. Conducts parallel research with 10-15 sub-agents
    2. Manages persistent context via file system
    3. Performs recursive research rounds (up to 3)
    4. Cross-references sources and identifies contradictions
    5. Tracks cost and tokens with enhanced reporting
    """
    
    agent_name = "deep_researcher"
    agent_type = "research_deep"
    start_time = time.time()
    
    logger.info(f"[{agent_name}] Starting deep research for task {state.task_id}")
    
    # Initialize research context
    context = DeepResearchContext(UUID(state.task_id))
    await context.initialize()
    
    _local_session = session is None
    try:
        # Initialize database session if not provided
        if _local_session:
            session = AsyncSessionLocal()
        
        # Get LLM for deep research
        model = get_model_for_phase(
            research_mode=ResearchMode.DEEP,
            phase=ModelPhase.RESEARCH,
        )
        
        llm = ChatOpenAI(
            model=model,
            temperature=0.7,
            **OPENROUTER_CONFIG,
        )
        
        # Spawn multiple research sub-agents
        logger.info(f"[{agent_name}] Spawning 10 research sub-agents")
        
        # Create list of sub-agent tasks
        sub_agent_tasks = []
        num_sub_agents = 10
        
        for i in range(num_sub_agents):
            if i < len(state.research_queries):
                query = state.research_queries[i]
            else:
                # If we have more sub-agents than queries, derive new ones
                query = await _derive_sub_query(state.topic, i, llm)
            
            task = _execute_sub_agent_research(
                agent_id=i,
                query=query,
                task_id=UUID(state.task_id),
                llm=llm,
            )
            sub_agent_tasks.append(task)
        
        # Convert to explicit Tasks for partial-result collection on timeout
        sub_agent_tasks = [asyncio.ensure_future(t) for t in sub_agent_tasks]

        # Execute all sub-agents in parallel with timeout
        logger.info(f"[{agent_name}] Running {num_sub_agents} sub-agents in parallel...")
        
        try:
            async with asyncio.timeout(600):  # 10 minute timeout for all sub-agents
                sub_agent_results = await asyncio.gather(
                    *sub_agent_tasks,
                    return_exceptions=True,
                )
        except asyncio.TimeoutError:
            logger.warning(f"[{agent_name}] Sub-agent research timed out; collecting partial results")
            state.errors.append("Deep research timed out after 10 minutes; using partial results")
            # Cancel remaining tasks and collect results from completed ones
            for t in sub_agent_tasks:
                if not t.done():
                    t.cancel()
            await asyncio.gather(*sub_agent_tasks, return_exceptions=True)
            sub_agent_results = []
            for t in sub_agent_tasks:
                if t.done() and not t.cancelled():
                    try:
                        sub_agent_results.append(t.result())
                    except Exception as exc:
                        sub_agent_results.append(exc)
                else:
                    sub_agent_results.append(Exception("timed out"))
        
        # Process sub-agent results
        all_sources_found: List[Source] = []
        total_tokens = 0
        total_cost = 0.0
        
        for i, result in enumerate(sub_agent_results):
            if isinstance(result, Exception):
                logger.warning(f"[{agent_name}] Sub-agent {i} failed: {result}")
                state.errors.append(f"Sub-agent {i} error: {str(result)}")
                continue
            
            if result and isinstance(result, dict):
                sources = result.get("sources", [])
                tokens = result.get("tokens", 0)
                cost = result.get("cost", 0.0)
                
                all_sources_found.extend(sources)
                total_tokens += tokens
                total_cost += cost
        
        logger.info(f"[{agent_name}] Sub-agents found {len(all_sources_found)} total sources")
        
        # ROUND 1: Initial research
        logger.info(f"[{agent_name}] Starting Research Round 1")
        await context.save_round_results(
            sources=all_sources_found,
            analysis=f"Initial research with 10 sub-agents found {len(all_sources_found)} sources",
        )
        
        # Deduplicate and filter sources
        unique_sources = _deduplicate_sources(all_sources_found)
        state.sources.extend(unique_sources)
        
        # ROUND 2: Deep dive on contradictions and gaps
        if context.research_round < context.max_rounds:
            logger.info(f"[{agent_name}] Starting Research Round 2 (gap analysis)")
            
            gap_analysis = await context.get_research_gap_analysis()
            logger.debug(f"Gap analysis:\n{gap_analysis}")
            
            # Create follow-up research queries based on gaps
            follow_up_queries = await _generate_follow_up_queries(
                state.topic,
                state.sources,
                gap_analysis,
                llm,
            )
            
            logger.info(f"[{agent_name}] Generated {len(follow_up_queries)} follow-up queries")
            
            # Execute follow-up research with 5 sub-agents (targeted)
            follow_up_tasks = []
            for i, query in enumerate(follow_up_queries[:5]):
                task = _execute_sub_agent_research(
                    agent_id=10 + i,
                    query=query,
                    task_id=UUID(state.task_id),
                    llm=llm,
                )
                follow_up_tasks.append(task)
            
            try:
                async with asyncio.timeout(300):  # 5 minute timeout
                    follow_up_results = await asyncio.gather(
                        *follow_up_tasks,
                        return_exceptions=True,
                    )
            except asyncio.TimeoutError:
                logger.warning(f"[{agent_name}] Follow-up research timed out")
            else:
                follow_up_sources: List[Source] = []
                for result in follow_up_results:
                    if isinstance(result, dict):
                        follow_up_sources.extend(result.get("sources", []))
                        total_tokens += result.get("tokens", 0)
                        total_cost += result.get("cost", 0.0)
                
                unique_follow_up = _deduplicate_sources(follow_up_sources)
                state.sources.extend(unique_follow_up)
                
                await context.save_round_results(
                    sources=unique_follow_up,
                    analysis=f"Follow-up research found {len(unique_follow_up)} additional sources",
                )
        
        # ROUND 3: Controversy resolution (if needed)
        if context.research_round < context.max_rounds and context.contradictions_found:
            logger.info(f"[{agent_name}] Starting Research Round 3 (controversy resolution)")
            
            controversy_queries = await _generate_controversy_queries(
                context.contradictions_found,
                llm,
            )
            
            controversy_tasks = []
            for i, query in enumerate(controversy_queries[:3]):
                task = _execute_sub_agent_research(
                    agent_id=15 + i,
                    query=query,
                    task_id=UUID(state.task_id),
                    llm=llm,
                )
                controversy_tasks.append(task)
            
            try:
                async with asyncio.timeout(180):  # 3 minute timeout
                    controversy_results = await asyncio.gather(
                        *controversy_tasks,
                        return_exceptions=True,
                    )
            except asyncio.TimeoutError:
                logger.warning(f"[{agent_name}] Controversy research timed out")
            else:
                controversy_sources: List[Source] = []
                for result in controversy_results:
                    if isinstance(result, dict):
                        controversy_sources.extend(result.get("sources", []))
                        total_tokens += result.get("tokens", 0)
                        total_cost += result.get("cost", 0.0)
                
                unique_controversy = _deduplicate_sources(controversy_sources)
                state.sources.extend(unique_controversy)
                
                await context.save_round_results(
                    sources=unique_controversy,
                    analysis=f"Controversy research found {len(unique_controversy)} sources",
                )
        
        # Update state with totals
        state.tokens_used = (state.tokens_used or 0) + total_tokens
        state.cost = (state.cost or 0.0) + total_cost
        
        # Log to database
        await ResearchService.log_agent_action(
            session=session,
            task_id=UUID(state.task_id),
            agent_name=agent_name,
            agent_type=agent_type,
            action=agent_type,
            input_data={
                "topic": state.topic,
                "num_queries": len(state.research_queries),
            },
            output_data={
                "sources_found": len(state.sources),
                "research_rounds": context.research_round,
                "total_tokens": total_tokens,
            },
            tokens_used=total_tokens,
            cost_usd=total_cost,
        )
        
        elapsed = time.time() - start_time
        logger.info(
            f"[{agent_name}] Completed deep research for task {state.task_id}: "
            f"found {len(state.sources)} sources in {elapsed:.1f}s, cost ${total_cost:.2f}"
        )
        
        return state
        
    except Exception as e:
        logger.error(f"[{agent_name}] Failed: {e}", exc_info=True)
        state.errors.append(f"Deep researcher error: {str(e)}")
        state.status = TaskStatus.FAILED
        return state
    finally:
        if _local_session and session is not None:
            await session.close()


async def _execute_sub_agent_research(
    agent_id: int,
    query: str,
    task_id: UUID,
    llm: ChatOpenAI,
) -> Dict[str, Any]:
    """
    Execute a single sub-agent research task.
    
    Returns dict with sources, tokens, and cost.
    """
    try:
        prompt = f"""You are a specialized research agent. Find 5 high-quality academic sources on:

Query: {query}

Return a JSON array of sources with this structure:
[
  {{
    "id": "unique_id",
    "title": "source title",
    "authors": ["author1", "author2"],
    "publication": "journal/conference name",
    "year": 2024,
    "doi": "10.xxxx/xxxxx",
    "url": "https://...",
    "credibility": 0.9,
    "excerpt": "brief excerpt from source",
    "relevance_score": 0.85
  }}
]

Return ONLY the JSON array, no other text."""
        
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        
        # Extract token usage
        tokens = await extract_token_usage(response)
        cost_info = estimate_cost_from_response(response, model=llm.model_name)
        
        # Parse response
        try:
            content = response.content
            # Ensure content is a string (Langchain can return list)
            if isinstance(content, list):
                # Concatenate list items - each item could be TextBlock, dict, or string
                parts = []
                for item in content:
                    if hasattr(item, 'text'):
                        parts.append(getattr(item, 'text'))
                    elif isinstance(item, dict):
                        parts.append(json.dumps(item))
                    else:
                        parts.append(str(item))
                content = "".join(parts)
            json_start = content.find("[")
            json_end = content.rfind("]") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                sources_data = json.loads(json_str)
                
                sources = [
                    Source(
                        id=s.get("id", f"source_{agent_id}_{i}"),
                        title=s.get("title", ""),
                        authors=s.get("authors"),
                        publication=s.get("publication"),
                        year=s.get("year"),
                        doi=s.get("doi"),
                        url=s.get("url"),
                        credibility=float(s.get("credibility", 0.5)),
                        excerpt=s.get("excerpt"),
                        relevance_score=float(s.get("relevance_score", 0.5)),
                    )
                    for i, s in enumerate(sources_data)
                ]
                
                return {
                    "agent_id": agent_id,
                    "sources": sources,
                    "tokens": tokens.get("total_tokens", 0),
                    "cost": cost_info.get("cost", 0.0),
                }
            else:
                logger.warning(f"Sub-agent {agent_id}: Could not extract JSON from response")
                return {
                    "agent_id": agent_id,
                    "sources": [],
                    "tokens": tokens.get("total_tokens", 0),
                    "cost": cost_info.get("cost", 0.0),
                }
        except json.JSONDecodeError as e:
            logger.warning(f"Sub-agent {agent_id}: Failed to parse JSON: {e}")
            return {
                "agent_id": agent_id,
                "sources": [],
                "tokens": tokens.get("total_tokens", 0),
                "cost": cost_info.get("cost", 0.0),
            }
            
    except Exception as e:
        logger.error(f"Sub-agent {agent_id} failed: {e}")
        return {
            "agent_id": agent_id,
            "sources": [],
            "tokens": 0,
            "cost": 0.0,
            "error": str(e),
        }


def _deduplicate_sources(sources: List[Source]) -> List[Source]:
    """Remove duplicate sources based on title and DOI."""
    seen = set()
    unique = []
    
    for source in sources:
        # Use title + DOI as key (DOI takes precedence)
        key = (source.doi or source.title.lower())
        
        if key not in seen:
            seen.add(key)
            unique.append(source)
    
    return unique


async def _derive_sub_query(
    topic: str,
    index: int,
    llm: ChatOpenAI,
) -> str:
    """
    Derive a new research query for a sub-agent.
    Used when there are more sub-agents than initial queries.
    """
    aspects = [
        "historical background",
        "recent developments",
        "methodology",
        "criticism and controversies",
        "applications",
        "future directions",
        "related fields",
        "case studies",
        "statistics and data",
    ]
    
    aspect = aspects[index % len(aspects)]
    
    # Simple heuristic: append aspect to topic
    return f"{topic} - {aspect}"


async def _generate_follow_up_queries(
    topic: str,
    sources: List[Source],
    gap_analysis: str,
    llm: ChatOpenAI,
) -> List[str]:
    """
    Generate follow-up research queries based on gaps in current research.
    """
    prompt = f"""Based on this gap analysis, generate 5 specific follow-up research queries:

Topic: {topic}

Current sources: {len(sources)} sources found
Gap analysis:
{gap_analysis}

Return a JSON array of 5 specific research queries:
["query1", "query2", "query3", "query4", "query5"]

Return ONLY the JSON array."""
    
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    
    try:
        content = response.content
        # Ensure content is a string (Langchain can return list)
        if isinstance(content, list):
            # Concatenate list items - each item could be TextBlock, dict, or string
            parts = []
            for item in content:
                if hasattr(item, 'text'):
                    parts.append(getattr(item, 'text'))
                elif isinstance(item, dict):
                    parts.append(json.dumps(item))
                else:
                    parts.append(str(item))
            content = "".join(parts)
        json_start = content.find("[")
        json_end = content.rfind("]") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = content[json_start:json_end]
            queries = json.loads(json_str)
            return [q for q in queries if isinstance(q, str)]
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse follow-up queries")
    
    return []


async def _generate_controversy_queries(
    contradictions: List[Dict[str, Any]],
    llm: ChatOpenAI,
) -> List[str]:
    """
    Generate research queries to resolve controversies.
    """
    if not contradictions:
        return []
    
    # Create a summary of key disagreements
    disagreement_summary = "\n".join(
        f"- {c.get('description', 'Unknown contradiction')}"
        for c in contradictions[:5]
    )
    
    prompt = f"""Generate 3 specific research queries to resolve these research disagreements:

{disagreement_summary}

Focus on finding sources that clarify these contradictions.

Return a JSON array of 3 research queries:
["query1", "query2", "query3"]

Return ONLY the JSON array."""
    
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    
    try:
        content = response.content
        # Ensure content is a string (Langchain can return list)
        if isinstance(content, list):
            # Concatenate list items - each item could be TextBlock, dict, or string
            parts = []
            for item in content:
                if hasattr(item, 'text'):
                    parts.append(getattr(item, 'text'))
                elif isinstance(item, dict):
                    parts.append(json.dumps(item))
                else:
                    parts.append(str(item))
            content = "".join(parts)
        json_start = content.find("[")
        json_end = content.rfind("]") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = content[json_start:json_end]
            queries = json.loads(json_str)
            return [q for q in queries if isinstance(q, str)]
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse controversy queries")
    
    return []
