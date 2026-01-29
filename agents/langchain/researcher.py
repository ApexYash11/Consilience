"""LangChain researcher agent stub."""
from typing import Any, Dict
from agents.base_agent import BaseAgent


class ResearcherAgent(BaseAgent):
    def act(self, task: Any) -> Dict[str, Any]:
        # TODO: call LLM to gather sources and claims
        return {"sources": [], "claims": []}
