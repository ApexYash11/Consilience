"""LangChain planner agent stub."""
from typing import Any, Dict
from agents.base_agent import BaseAgent


class PlannerAgent(BaseAgent):
    def act(self, task: Any) -> Dict[str, Any]:
        # TODO: integrate LangChain prompt and model call
        return {"plan": [{"step": 1, "action": "define_scope"}]}
