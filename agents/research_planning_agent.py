from typing import Any, Dict
from agents.base_agent import BaseAgent
from models import AgentSpec

class ResearchPlanningAgent(BaseAgent):
    """Example agent that produces a naive research plan."""

    def __init__(self, spec: AgentSpec):
        super().__init__(spec)

    def act(self, task: Any) -> Dict[str, Any]:
        # Minimal deterministic planning logic for demo purposes
        plan = {
            "task_id": getattr(task, "id", "unknown"),
            "steps": [
                {"step": 1, "action": "define_scope", "notes": "Clarify scope and key questions."},
                {"step": 2, "action": "literature_review", "notes": "Collect top 10 sources."},
                {"step": 3, "action": "synthesis", "notes": "Summarize findings."},
            ],
            "created_by": self.spec.name,
        }
        return {"plan": plan}
