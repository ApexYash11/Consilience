"""DeepAgents Methodology Critic stub."""
from typing import Any, Dict
from agents.base_agent import BaseAgent


class MethodologyCritic(BaseAgent):
    def act(self, task: Any) -> Dict[str, Any]:
        # TODO: critique methodology and suggest improvements
        return {"weaknesses": [], "recommendations": []}
