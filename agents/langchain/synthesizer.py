"""LangChain synthesizer agent stub."""
from typing import Any, Dict
from agents.base_agent import BaseAgent


class SynthesizerAgent(BaseAgent):
    def act(self, task: Any) -> Dict[str, Any]:
        # TODO: combine research outputs into coherent draft
        return {"draft": ""}
