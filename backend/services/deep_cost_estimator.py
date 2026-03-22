"""
Deep Research Cost Estimation.

Estimates cost for deep research workflows:
- 10-15 parallel sub-agents (3 research rounds)
- Enhanced verification with semantic cross-checking
- 3-5 revision cycles
- Uses premium LLM models (Claude 3.5 Sonnet or GPT-4)
"""

from typing import Dict, Any
from ..models.research import ResearchDepth


def estimate_deep_research_cost(
    topic_length: int = 50,
    num_sources_target: int = 20,
    enable_revision: bool = True,
) -> Dict[str, Any]:
    """
    Estimate cost for a deep research task.

    Deep research uses:
    - Claude 3.5 Sonnet ($3/$15 per 1M tokens) for complex reasoning
    - 10-15 sub-agents in parallel (3 rounds)
    - 3-5 revision cycles
    - Enhanced verification

    Args:
        topic_length: Length of research topic (avg 50 chars)
        num_sources_target: Target number of sources (default 20)
        enable_revision: Whether revision cycles are enabled (default True)

    Returns:
        Dict with:
        - estimated_tokens: Total estimated tokens
        - estimated_cost_usd: Estimated cost in USD
        - cost_breakdown: Breakdown by component
        - estimated_duration_minutes: Duration estimate
        - confidence: Confidence level in estimate (0.0-1.0)
    """

    # Token estimates per component
    # (based on GPT-4 / Claude 3.5 Sonnet token counts)

    # 1. PLANNER: 5 complex queries
    planner_prompt_tokens = 100 + (topic_length // 10)  # ~100-150 tokens
    planner_completion_tokens = 150  # JSON array of queries
    planner_tokens = planner_prompt_tokens + planner_completion_tokens

    # 2. DEEP RESEARCHER: 3 rounds of research
    #    Round 1: 10 sub-agents, 5 sources each
    #    Round 2: 5 sub-agents (follow-up), 5 sources each
    #    Round 3: 3 sub-agents (controversy), 5 sources each

    # Each sub-agent call:
    # - Prompt: ~300-400 tokens (instruction + context)
    # - Completion: ~500 tokens (5 sources in JSON)
    sub_agent_prompt_tokens = 350
    sub_agent_completion_tokens = 500
    sub_agent_tokens = sub_agent_prompt_tokens + sub_agent_completion_tokens

    round1_sub_agents = 10
    round2_sub_agents = 5
    round3_sub_agents = 3
    total_sub_agents = round1_sub_agents + round2_sub_agents + round3_sub_agents

    researcher_tokens = total_sub_agents * sub_agent_tokens

    # 3. VERIFIER: Enhanced semantic verification
    # Prompt: ~400 tokens (all sources + verification instructions)
    # Completion: ~500 tokens (verification results + scoring)
    verifier_tokens = 400 + 500

    # 4. DETECTOR: Find contradictions
    # Prompt: ~400 tokens (sources + contradiction detection instructions)
    # Completion: ~400 tokens (contradiction analysis)
    detector_tokens = 400 + 400

    # 5. SYNTHESIZER: Draft paper with cross-references
    # Initial draft:
    # Prompt: ~500 tokens (sources + outline + synthesis instructions)
    # Completion: ~2000 tokens (paper draft)
    synthesizer_initial_tokens = 500 + 2000

    # Redo cycles (if confidence < 0.4)
    synthesizer_redo_tokens = 0
    if enable_revision:
        synthesizer_redo_tokens = (400 + 1500) * 1  # 1 redo cycle expected

    synthesizer_tokens = synthesizer_initial_tokens + synthesizer_redo_tokens

    # 6. REVIEWER: Fact-check and feedback
    # Prompt: ~600 tokens (draft paper + verification instructions)
    # Completion: ~600 tokens (feedback + issues)
    reviewer_tokens_per_cycle = 600 + 600

    # Deep research targets 3 revision cycles (consistent with compare_research_depths)
    revision_cycles = 3 if enable_revision else 0
    reviewer_tokens = reviewer_tokens_per_cycle * (1 + revision_cycles)

    # 7. FORMATTER: Final formatting
    # Prompt: ~200 tokens (instructions)
    # Completion: ~1000 tokens (formatted output)
    formatter_tokens = 200 + 1000

    # Total tokens
    total_tokens = (
        planner_tokens
        + researcher_tokens
        + verifier_tokens
        + detector_tokens
        + synthesizer_tokens
        + reviewer_tokens
        + formatter_tokens
    )

    # Cost calculation (Claude 3.5 Sonnet pricing)
    # Input: $3 per 1M tokens
    # Output: $15 per 1M tokens
    # Average input/output ratio: ~1:1 for research (slightly more output)

    # Simplified: ~$10 per 1M tokens for mixed input/output
    cost_per_million_tokens = 10.0
    estimated_cost = (total_tokens / 1_000_000) * cost_per_million_tokens

    # Add overhead for potential retries and error handling
    overhead_factor = 1.15  # 15% overhead
    estimated_cost_with_overhead = estimated_cost * overhead_factor

    # Estimate duration
    # Sub-agent parallelization:
    # - Round 1: 10 agents in parallel = ~1 call duration (~20s)
    # - Round 2: 5 agents in parallel = ~1 call duration (~20s)
    # - Round 3: 3 agents in parallel = ~1 call duration (~20s)
    # Other components: ~15s each

    duration_estimate_seconds = (
        15  # planner
        + 60  # researcher (3 rounds in parallel)
        + 15  # verifier
        + 15  # detector
        + 30  # synthesizer initial
        + 20 * revision_cycles  # synthesizer redos
        + 30 * (1 + revision_cycles)  # reviewer
        + 10  # formatter
    )

    duration_estimate_minutes = duration_estimate_seconds / 60

    return {
        "estimated_tokens": int(total_tokens),
        "estimated_cost_usd": round(estimated_cost_with_overhead, 2),
        "cost_breakdown": {
            "planner_tokens": planner_tokens,
            "researcher_tokens": researcher_tokens,
            "verifier_tokens": verifier_tokens,
            "detector_tokens": detector_tokens,
            "synthesizer_tokens": synthesizer_tokens,
            "reviewer_tokens": reviewer_tokens,
            "formatter_tokens": formatter_tokens,
        },
        "estimated_duration_minutes": round(duration_estimate_minutes, 1),
        "confidence": 0.75,  # 75% confidence in estimate
        "model": "Claude 3.5 Sonnet (Premium)",
        "included_features": [
            "10-15 parallel sub-agents",
            "3 research rounds",
            "Gap analysis & controversy resolution",
            "Enhanced verification",
            "Semantic cross-referencing",
            "2-3 revision cycles",
        ],
    }


def compare_research_depths() -> Dict[str, Dict[str, Any]]:
    """
    Compare costs and features between Standard and Deep research.

    Returns:
        Dict comparing both research types
    """
    standard_estimate = {
        "estimated_tokens": 8000,
        "estimated_cost_usd": 1.50,
        "estimated_duration_minutes": 3.5,
        "num_agents": 7,
        "sub_agents_per_round": 5,
        "research_rounds": 1,
        "revision_cycles": 1,
        "model": "Qwen 2.5 7B (Free)",
        "target_sources": 15,
    }

    deep_estimate = estimate_deep_research_cost()
    deep_estimate.update(
        {
            "num_agents": 7,
            "sub_agents_per_round": 18,  # 10 + 5 + 3
            "research_rounds": 3,
            "revision_cycles": 3,
            "target_sources": 20,
        }
    )

    return {
        "standard": standard_estimate,
        "deep": deep_estimate,
        "comparison": {
            "cost_multiplier": round(
                deep_estimate["estimated_cost_usd"]
                / standard_estimate["estimated_cost_usd"],
                1,
            ),
            "time_multiplier": round(
                deep_estimate["estimated_duration_minutes"]
                / standard_estimate["estimated_duration_minutes"],
                1,
            ),
            "agent_multiplier": 2.6,  # 18 vs 5 per round
            "quality_improvement": "3-5x better: recursive research, contradiction resolution, semantic verification",
        },
    }


def estimate_monthly_cost(
    free_tier_tasks: int = 10,
    paid_tier_tasks: int = 5,
) -> Dict[str, Any]:
    """
    Estimate monthly costs for the platform.

    Args:
        free_tier_tasks: Monthly standard research tasks (free tier)
        paid_tier_tasks: Monthly deep research tasks (paid tier)

    Returns:
        Dict with monthly cost estimates
    """
    standard_cost_per_task = 1.50
    # Derive deep cost dynamically to stay consistent with estimate_deep_research_cost()
    try:
        deep_cost_per_task = estimate_deep_research_cost()["estimated_cost_usd"]
    except Exception:
        deep_cost_per_task = 10.00  # Fallback if estimation fails

    total_free_cost = free_tier_tasks * standard_cost_per_task
    total_paid_cost = paid_tier_tasks * deep_cost_per_task

    total_monthly_llm_cost = total_free_cost + total_paid_cost

    # Platform overhead (database, API, infra)
    platform_overhead = 200  # $200/month base

    total_platform_cost = total_monthly_llm_cost + platform_overhead

    # Pricing strategy
    free_tier_revenue = 0  # Free tier
    paid_tier_revenue = (
        paid_tier_tasks * 30
    )  # $30/month per user (assume 1 task per month)

    if paid_tier_revenue > 0:
        profit_margin = paid_tier_revenue - total_platform_cost
        profit_margin_pct = profit_margin / paid_tier_revenue * 100
    else:
        profit_margin = 0
        profit_margin_pct = 0

    return {
        "free_tier": {
            "monthly_tasks": free_tier_tasks,
            "cost_per_task": standard_cost_per_task,
            "total_cost": round(total_free_cost, 2),
        },
        "paid_tier": {
            "monthly_tasks": paid_tier_tasks,
            "cost_per_task": deep_cost_per_task,
            "total_cost": round(total_paid_cost, 2),
        },
        "platform": {
            "llm_cost": round(total_monthly_llm_cost, 2),
            "overhead": platform_overhead,
            "total_cost": round(total_platform_cost, 2),
        },
        "revenue": {
            "free_tier": free_tier_revenue,
            "paid_tier": int(paid_tier_revenue),
            "total": int(paid_tier_revenue),
        },
        "profitability": {
            "profit_margin": round(profit_margin, 2),
            "profit_margin_pct": round(profit_margin_pct, 1),
            "breakeven_paid_tasks": round(total_platform_cost / 30, 1),
        },
    }
