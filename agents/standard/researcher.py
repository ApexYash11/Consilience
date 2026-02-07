"""
Researcher Agent: Executes search queries and collects sources.

Uses Qwen 2.5 7B (free) for research phase.
- Fast parallel execution (5 researchers run simultaneously)
- Strong multilingual support
- Lightweight for quick turnaround
- $0.00 cost per researcher

Execution: 5 researchers run in parallel, each gets 1 query from the plan.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from uuid import UUID

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

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
from database.connection import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def researcher_node(state: ResearchState, researcher_index: int = 0) -> ResearchState:
    """
    Research agent node with timeout & retry logic.
    
    Called 5 times in parallel from graph (via multiple edges).
    Each researcher gets 180 seconds (3 minutes) to find sources.
    """
    
    researcher_id = f"researcher_{researcher_index + 1}"
    start_time_dt = datetime.utcnow()
    start_time = time.time()
    
    try:
        # Wrap with timeout to prevent hanging
        async with asyncio.timeout(180):  # 3 minutes per researcher
            
            # Get the query for this researcher
            if researcher_index >= len(state.research_queries):
                logger.warning(f"{researcher_id}: No query assigned")
                return state
            
            query = state.research_queries[researcher_index]
            
            # Get LLM model
            model = get_model_for_phase(
                research_mode=ResearchMode.STANDARD,
                phase=ModelPhase.RESEARCH,
            )
            
            llm = ChatOpenAI(
                model=model,
                temperature=0.7,
                **OPENROUTER_CONFIG,
            )
            
            # Call LLM to find sources
            prompt_text = f"Find 3 credible academic sources on: {query}"
            response = await llm.ainvoke([HumanMessage(content=prompt_text)])
            
            # Extract tokens and costs
            tokens = await extract_token_usage(response)
            cost_info = estimate_cost_from_response(response, model=model)
            
            # Parse sources from response
            found_sources = parse_sources_from_response(response, researcher_index)
            if found_sources:
                if not hasattr(state, 'sources') or state.sources is None:
                    state.sources = []
                state.sources.extend(found_sources)
            
            # Track execution
            state.tokens_used = (state.tokens_used or 0) + tokens["total_tokens"]
            state.cost = (state.cost or 0.0) + cost_info["cost"]
            
            # Log to DB
            async with AsyncSessionLocal() as session:
                await ResearchService.log_token_usage(
                    session=session,
                    task_id=UUID(state.task_id),
                    agent_name=researcher_id,
                    model=model,
                    prompt_tokens=tokens["prompt_tokens"],
                    completion_tokens=tokens["completion_tokens"],
                    cost_usd=cost_info["cost"],
                    input_preview=query[:100],
            output_preview=str(response.content)[:100] if hasattr(response, 'content') else "",
                    duration_seconds=time.time() - start_time,
                )
            
            return state
            
    except asyncio.TimeoutError:
        logger.warning(f"{researcher_id} timed out after 180 seconds")
        if not hasattr(state, 'errors') or state.errors is None:
            state.errors = []
        state.errors.append(f"{researcher_id}: Timeout")
        return state
    except Exception as e:
        logger.error(f"{researcher_id} failed: {str(e)}")
        if not hasattr(state, 'errors') or state.errors is None:
            state.errors = []
        state.errors.append(f"{researcher_id}: {str(e)}")
        return state


async def search_sources(query: str, researcher_id: int) -> Tuple[List[Source], Dict]:
    """
    Generate candidate sources for a query using an LLM (SIMULATED SOURCES).

    NOTE: This implementation does NOT perform real network searches against
    DuckDuckGo, arXiv, Semantic Scholar, or other APIs. Instead it prompts an
    LLM to synthesize a JSON array of suggested sources and then parses that
    output into `Source` objects. The generated sources may hallucinate and
    can contain invalid or non-existent DOIs, URLs, years, or author lists.

    Current process:
        1. Build an LLM prompt requesting a JSON array of 3 candidate sources.
        2. Call the LLM and parse the JSON response (with a relaxed fallback
             that extracts a JSON array from surrounding text if necessary).
        3. Convert each JSON item into a `Source` Pydantic object and return
             (sources, cost_info).

    Limitations:
        - No real network/API calls are made; results are synthetic examples.
        - DOIs/URLs returned by the LLM must be verified before use.
        - Credibility scores are LLM-estimated and should be confirmed.

    Recommended next steps for production:
        - Replace the LLM-based generator with real integrations (DuckDuckGo,
            arXiv API, Semantic Scholar API) to retrieve authoritative metadata.
        - Add DOI/URL verification (HTTP HEAD, DOI resolution) and publisher
            metadata normalization.
        - Rate-limit and cache external searches to control costs.

    Args:
        query: Search query string
        researcher_id: ID of this researcher (for logging)

    Returns:
        Tuple of (List[Source], cost_info dict). `cost_info` contains
        `total_tokens` and `cost` estimated from the LLM response.
    """
    sources: List[Source] = []

    try:
        # Initialize LLM for source evaluation
        model = get_model_for_phase(
            research_mode=ResearchMode.STANDARD,
            phase=ModelPhase.RESEARCH,
        )

        llm = ChatOpenAI(
            model=model,
            temperature=0.3,
            max_completion_tokens=1500,
            **OPENROUTER_CONFIG,
        )

        # Step 1: Web search (simulated - real implementation would use DuckDuckGo API)
        web_search_prompt = f"""You are a research source evaluator.

Your task: Suggest 3 high-quality sources for this search query.

SEARCH QUERY: {query}

Think about:
1. What academic papers or reputable sources would answer this query?
2. What institutions or experts are known for this topic?
3. What recent publications are relevant?

Return a JSON array with 3 sources:
[
  {{
    "title": "Source Title",
    "authors": "Author1, Author2",
    "publication": "Journal/Website Name",
    "year": 2024,
    "doi": "10.xxxx/xxxxx",
    "url": "https://example.com",
    "type": "academic_paper|news|website",
    "credibility_score": 0.85
  }},
  ...
]

CRITICAL: Return ONLY the JSON array, no other text."""

        response = await llm.ainvoke(web_search_prompt)

        # Parse response
        payload = response.content
        if not isinstance(payload, str):
            payload = str(payload)

        try:
            sources_data = json.loads(payload)
        except json.JSONDecodeError:
            import re

            json_match = re.search(r"\[.*\]", payload, re.DOTALL)
            if json_match:
                sources_data = json.loads(json_match.group())
            else:
                logger.error(f"Failed to parse researcher response: {payload}")
                return sources, {"total_tokens": 0, "cost": 0.0}

        # Convert to Source objects
        for source_data in sources_data:
            source = Source(
                id=f"{researcher_id}_{len(sources)}",
                title=source_data.get("title", "Unknown"),
                authors=source_data.get("authors", "Unknown"),
                publication=source_data.get("publication", "Unknown"),
                year=source_data.get("year", 0),
                doi=source_data.get("doi", ""),
                url=source_data.get("url", ""),
                credibility=source_data.get("credibility_score", 0.5),
                verified=False,
                excerpt=f"Query: {query}",
                relevance_score=0.8,
            )
            sources.append(source)

        # Track cost
        cost_info = estimate_cost_from_response(response, model)

        logger.info(
            f"Researcher {researcher_id} evaluated sources | Cost: ${cost_info.get('cost', 0):.4f}"
        )

        return sources, cost_info

    except Exception as e:
        logger.error(f"search_sources failed for query '{query}': {str(e)}", exc_info=True)
        # On failure, do not return partially-built sources — return empty results
        return [], {"total_tokens": 0, "cost": 0.0}


def parse_sources_from_response(response, researcher_index: int) -> List[Source]:
    """
    Parse source references from LLM response.
    
    Expects response to contain URLs, paper citations, or structured source data.
    Returns up to 3 Source objects extracted from the response.
    """
    try:
        import json
        import re
        
        content = response.content if hasattr(response, 'content') else str(response)
        sources = []
        
        # Try to parse as JSON first
        try:
            data = json.loads(content)
            if isinstance(data, list):
                for item in data[:3]:
                    if isinstance(item, dict):
                        source = Source(
                            id=f"source_{researcher_index}_{len(sources)}",
                            url=item.get('url', f"https://source-{researcher_index}-{len(sources)}.example.com"),
                            title=item.get('title', f"Source {len(sources) + 1}"),
                            authors=[item.get('author', 'Unknown')]  if item.get('author') else None,
                            year=item.get('year', 2024),
                            credibility=float(item.get('credibility_score', 0.7)),
                            relevance_score=float(item.get('relevance_score', 0.8)),
                        )
                        sources.append(source)
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Fallback: extract URLs from text
        if not sources:
            url_pattern = r'https?://[^\s\)>]+'
            urls = re.findall(url_pattern, content)
            
            for i, url in enumerate(urls[:3]):
                source = Source(
                    id=f"source_{researcher_index}_{i}",
                    url=url,
                    title=f"Source {i + 1}",
                    authors=["Unknown"] if url else None,
                    year=2024,
                    credibility=0.7,
                    relevance_score=0.8,
                )
                sources.append(source)
        
        return sources[:3]  # Max 3 sources per researcher
        
    except Exception as e:
        logger.warning(f"Failed to parse sources from response: {str(e)}")
        return []