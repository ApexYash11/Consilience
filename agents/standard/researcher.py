"""
Researcher Agent: Executes search queries and collects sources.

Uses Qwen 2.5 7B (free) for research phase.
- Fast parallel execution (5 researchers run simultaneously)
- Strong multilingual support
- Lightweight for quick turnaround
- $0.00 cost per researcher

Execution: 5 researchers run in parallel, each gets 1 query from the plan.
"""

from langchain_openai import ChatOpenAI
from models.research import ResearchState, Source, TaskStatus
from config.models import (
    get_model_for_phase,
    ModelPhase,
    ResearchMode,
    OPENROUTER_CONFIG,
)
from utils.cost_estimator import estimate_cost_from_response
from typing import Dict, List, Tuple
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


async def researcher_node(state: ResearchState, researcher_id: int) -> ResearchState:
    """
    RESEARCHER NODE - Source Collection

    **Input**: ResearchState with:
        - research_queries: List of 5 specific search queries
        - sources: Initial empty list

    **Output**: ResearchState with:
        - sources: Extended list with new sources from this query

    **Execution**: Runs 5 times in parallel (one per query)
        - Researcher 0: Searches query[0]
        - Researcher 1: Searches query[1]
        - ...
        - Researcher 4: Searches query[4]
        
        Total time: Same as searching 1 query (parallel execution)

    **Process**:
        1. Get assigned query
        2. Search web + academic databases
        3. Evaluate source credibility
        4. Add sources to state
        5. Track cost and tokens

    **Output**: 3 sources per researcher (15 total sources)

    **Model**: Qwen 2.5 7B (free)
        - Fast inference for parallel execution
        - 131K context window
        - Strong general task performance
        - $0.00 cost
    """
    query = ""
    try:
        # Get the query for this researcher
        if researcher_id >= len(state.research_queries):
            logger.warning(
                f"Researcher {researcher_id} has no query (only {len(state.research_queries)} queries)"
            )
            return state

        query = state.research_queries[researcher_id]
        logger.info(f"Researcher {researcher_id} searching for: {query}")

        # Search for sources
        sources, cost_info = await search_sources(query, researcher_id)

        # Add to state
        if sources:
            state.sources.extend(sources)
            logger.info(
                f"Researcher {researcher_id} found {len(sources)} sources | Cost: ${cost_info.get('cost', 0):.4f}"
            )

            # Track tokens and cost
            state.tokens_used = (state.tokens_used or 0) + cost_info.get("total_tokens", 0)
            state.cost = (state.cost or 0.0) + cost_info.get("cost", 0.0)

        return state

    except Exception as e:
        logger.error(
            f"Researcher {researcher_id} failed on query '{query}': {str(e)}",
            exc_info=True,
        )
        state.status = TaskStatus.FAILED
        raise ValueError(f"Researcher {researcher_id} failed: {str(e)}") from e


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