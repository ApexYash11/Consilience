"""
Cost estimation and token tracking for research tasks.
Provides pre-execution cost estimates and real-time usage tracking.
"""

from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from models_v2 import (
    ResearchConfig,
    ResearchDepth,
    TokenUsageEstimate,
    CostEstimate,
    AgentType,
)


# Token pricing per million tokens (as of Jan 2026)
# Update these based on current Anthropic pricing
LLM_PRICING = {
    "claude-3-5-sonnet-20241022": {
        "input": Decimal("3.00") / 1_000_000,   # $3 per million input tokens
        "output": Decimal("15.00") / 1_000_000,  # $15 per million output tokens
    },
    "claude-3-opus-20240229": {
        "input": Decimal("15.00") / 1_000_000,
        "output": Decimal("75.00") / 1_000_000,
    },
    "claude-3-haiku-20240307": {
        "input": Decimal("0.25") / 1_000_000,
        "output": Decimal("1.25") / 1_000_000,
    },
}


# Historical average token usage per agent type per action
# These would be learned from actual usage data
AGENT_TOKEN_AVERAGES = {
    AgentType.PLANNER: {
        "input": 2000,
        "output": 1500,
    },
    AgentType.RESEARCHER: {
        "input": 5000,
        "output": 3000,
    },
    AgentType.VERIFIER: {
        "input": 3000,
        "output": 1000,
    },
    AgentType.FACT_CHECKER: {
        "input": 4000,
        "output": 2000,
    },
    AgentType.CITATION_CHAINER: {
        "input": 3500,
        "output": 1500,
    },
    AgentType.METHODOLOGY_CRITIC: {
        "input": 4500,
        "output": 3000,
    },
    AgentType.EXPERT_REVIEWER: {
        "input": 6000,
        "output": 4000,
    },
    AgentType.CONTRADICTION_ANALYZER: {
        "input": 5000,
        "output": 2500,
    },
    AgentType.SOURCE_QUALITY_RANKER: {
        "input": 3000,
        "output": 1000,
    },
    AgentType.RECURSIVE_RESEARCHER: {
        "input": 5000,
        "output": 3000,
    },
    AgentType.SYNTHESIZER: {
        "input": 8000,
        "output": 5000,
    },
    AgentType.REVIEWER: {
        "input": 6000,
        "output": 3000,
    },
    AgentType.FORMATTER: {
        "input": 4000,
        "output": 2000,
    },
}


class CostEstimator:
    """Estimates costs for research tasks before execution."""
    
    def __init__(self, historical_data: Optional[Dict] = None):
        """
        Initialize cost estimator.
        
        Args:
            historical_data: Optional historical usage data for better estimates
        """
        self.historical_data = historical_data or {}
        self.pricing = LLM_PRICING
        self.averages = AGENT_TOKEN_AVERAGES
    
    def estimate_task_cost(
        self,
        task_id: UUID,
        config: ResearchConfig,
    ) -> CostEstimate:
        """
        Estimate total cost for a research task.
        
        Args:
            task_id: Task identifier
            config: Research configuration
        
        Returns:
            Detailed cost estimate with phase breakdowns
        """
        phase_estimates = []
        
        if config.depth == ResearchDepth.STANDARD:
            phase_estimates = self._estimate_standard_research(config)
        else:
            phase_estimates = self._estimate_deep_research(config)
        
        # Calculate totals
        total_tokens = sum(
            est.estimated_input_tokens + est.estimated_output_tokens
            for est in phase_estimates
        )
        total_cost = sum(est.estimated_cost_usd for est in phase_estimates)
        
        # Estimate duration
        estimated_duration = self._estimate_duration(config)
        
        # Confidence based on historical data availability
        confidence = self._calculate_confidence(config)
        
        return CostEstimate(
            task_id=task_id,
            config=config,
            phase_estimates=phase_estimates,
            total_estimated_tokens=total_tokens,
            total_estimated_cost_usd=total_cost,
            estimated_duration_minutes=estimated_duration,
            confidence_level=confidence,
        )
    
    def _estimate_standard_research(
        self,
        config: ResearchConfig,
    ) -> List[TokenUsageEstimate]:
        """Estimate costs for standard research workflow."""
        estimates = []
        model = config.llm_model
        pricing = self.pricing.get(model, self.pricing["claude-3-5-sonnet-20241022"])
        
        # Phase 1: Planning
        estimates.append(self._estimate_agent_cost(
            phase="planning",
            agent_type=AgentType.PLANNER,
            count=1,
            pricing=pricing,
        ))
        
        # Phase 2: Research (5 parallel researchers)
        estimates.append(self._estimate_agent_cost(
            phase="research",
            agent_type=AgentType.RESEARCHER,
            count=min(config.max_agents, 5),
            pricing=pricing,
        ))
        
        # Phase 3: Verification
        estimates.append(self._estimate_agent_cost(
            phase="verification",
            agent_type=AgentType.VERIFIER,
            count=1,
            pricing=pricing,
        ))
        
        # Phase 4: Synthesis
        estimates.append(self._estimate_agent_cost(
            phase="synthesis",
            agent_type=AgentType.SYNTHESIZER,
            count=1,
            pricing=pricing,
        ))
        
        # Phase 5: Review (multiple cycles)
        for cycle in range(config.max_revision_cycles):
            estimates.append(self._estimate_agent_cost(
                phase=f"review_cycle_{cycle+1}",
                agent_type=AgentType.REVIEWER,
                count=1,
                pricing=pricing,
            ))
        
        # Phase 6: Formatting
        estimates.append(self._estimate_agent_cost(
            phase="formatting",
            agent_type=AgentType.FORMATTER,
            count=1,
            pricing=pricing,
        ))
        
        return estimates
    
    def _estimate_deep_research(
        self,
        config: ResearchConfig,
    ) -> List[TokenUsageEstimate]:
        """Estimate costs for deep research workflow."""
        estimates = []
        model = config.llm_model
        pricing = self.pricing.get(model, self.pricing["claude-3-5-sonnet-20241022"])
        
        # All standard phases
        estimates.extend(self._estimate_standard_research(config))
        
        # Additional deep research phases
        
        # Source Quality Ranking
        estimates.append(self._estimate_agent_cost(
            phase="source_quality_ranking",
            agent_type=AgentType.SOURCE_QUALITY_RANKER,
            count=1,
            pricing=pricing,
        ))
        
        # Citation Chain Verification
        if config.enable_citation_chain:
            estimates.append(self._estimate_agent_cost(
                phase="citation_chain",
                agent_type=AgentType.CITATION_CHAINER,
                count=2,
                pricing=pricing,
            ))
        
        # Fact Checking (multiple fact checkers)
        if config.enable_fact_checking:
            estimates.append(self._estimate_agent_cost(
                phase="fact_checking",
                agent_type=AgentType.FACT_CHECKER,
                count=3,
                pricing=pricing,
            ))
        
        # Contradiction Analysis
        estimates.append(self._estimate_agent_cost(
            phase="contradiction_analysis",
            agent_type=AgentType.CONTRADICTION_ANALYZER,
            count=1,
            pricing=pricing,
        ))
        
        # Methodology Critique
        estimates.append(self._estimate_agent_cost(
            phase="methodology_critique",
            agent_type=AgentType.METHODOLOGY_CRITIC,
            count=1,
            pricing=pricing,
        ))
        
        # Expert Review
        estimates.append(self._estimate_agent_cost(
            phase="expert_review",
            agent_type=AgentType.EXPERT_REVIEWER,
            count=2,
            pricing=pricing,
        ))
        
        # Recursive Research (estimate 2 rounds on average)
        if config.enable_recursive_research:
            estimates.append(self._estimate_agent_cost(
                phase="recursive_research",
                agent_type=AgentType.RECURSIVE_RESEARCHER,
                count=4,  # 2 rounds x 2 agents
                pricing=pricing,
            ))
        
        return estimates
    
    def _estimate_agent_cost(
        self,
        phase: str,
        agent_type: AgentType,
        count: int,
        pricing: Dict[str, Decimal],
    ) -> TokenUsageEstimate:
        """Estimate cost for specific agent type."""
        avg_tokens = self.averages.get(agent_type, {"input": 3000, "output": 2000})
        
        input_tokens = avg_tokens["input"] * count
        output_tokens = avg_tokens["output"] * count
        
        cost = (
            (input_tokens * pricing["input"]) +
            (output_tokens * pricing["output"])
        )
        
        return TokenUsageEstimate(
            phase=phase,
            agent_type=agent_type,
            estimated_input_tokens=input_tokens,
            estimated_output_tokens=output_tokens,
            estimated_cost_usd=cost,
        )
    
    def _estimate_duration(self, config: ResearchConfig) -> int:
        """Estimate task duration in minutes."""
        if config.depth == ResearchDepth.STANDARD:
            # Base: 30 minutes + 5 min per revision cycle
            return 30 + (config.max_revision_cycles * 5)
        else:
            # Deep research: 90 minutes base + 10 min per revision cycle
            # + extra for deep features
            base = 90
            revisions = config.max_revision_cycles * 10
            
            extras = 0
            if config.enable_fact_checking:
                extras += 15
            if config.enable_citation_chain:
                extras += 10
            if config.enable_recursive_research:
                extras += 20
            
            return base + revisions + extras
    
    def _calculate_confidence(self, config: ResearchConfig) -> float:
        """
        Calculate confidence level in estimate.
        
        Returns:
            Confidence score 0.0-1.0
        """
        # Base confidence
        confidence = 0.7
        
        # Higher confidence if we have historical data
        if self.historical_data:
            confidence += 0.2
        
        # Lower confidence for deep research (more variables)
        if config.depth == ResearchDepth.DEEP:
            confidence -= 0.1
        
        return min(1.0, max(0.0, confidence))


class CostTracker:
    """Real-time cost tracking during task execution."""
    
    def __init__(self):
        self.task_costs: Dict[UUID, Dict] = {}
    
    def start_task(self, task_id: UUID):
        """Initialize cost tracking for a task."""
        self.task_costs[task_id] = {
            "total_cost": Decimal("0.00"),
            "total_tokens": 0,
            "phases": {},
        }
    
    def record_agent_action(
        self,
        task_id: UUID,
        phase: str,
        agent_type: AgentType,
        input_tokens: int,
        output_tokens: int,
        model: str,
    ):
        """Record costs for a single agent action."""
        if task_id not in self.task_costs:
            self.start_task(task_id)
        
        pricing = LLM_PRICING.get(model, LLM_PRICING["claude-3-5-sonnet-20241022"])
        
        cost = (
            (input_tokens * pricing["input"]) +
            (output_tokens * pricing["output"])
        )
        
        # Update totals
        self.task_costs[task_id]["total_cost"] += cost
        self.task_costs[task_id]["total_tokens"] += (input_tokens + output_tokens)
        
        # Update phase costs
        if phase not in self.task_costs[task_id]["phases"]:
            self.task_costs[task_id]["phases"][phase] = {
                "cost": Decimal("0.00"),
                "tokens": 0,
            }
        
        self.task_costs[task_id]["phases"][phase]["cost"] += cost
        self.task_costs[task_id]["phases"][phase]["tokens"] += (
            input_tokens + output_tokens
        )
    
    def get_task_cost(self, task_id: UUID) -> Dict:
        """Get current cost for a task."""
        return self.task_costs.get(task_id, {
            "total_cost": Decimal("0.00"),
            "total_tokens": 0,
            "phases": {},
        })
    
    def check_budget(
        self,
        task_id: UUID,
        max_budget: Optional[Decimal] = None,
    ) -> bool:
        """
        Check if task is within budget.
        
        Returns:
            True if within budget, False if exceeded
        """
        if max_budget is None:
            return True
        
        current_cost = self.task_costs.get(task_id, {}).get(
            "total_cost", Decimal("0.00")
        )
        
        return current_cost <= max_budget
