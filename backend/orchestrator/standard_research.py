"""Standard research orchestrator - high-level skeleton."""
from typing import List, Any, Dict


class StandardResearchOrchestrator:
    def __init__(self, agents: List[Any]):
        self.agents = agents

    def run(self, task) -> Dict[str, Any]:
        # TODO: orchestrate LangChain agents according to workflow
        results = {}
        for agent in self.agents:
            results[agent.spec.name] = agent.act(task)
        return {"task": task, "results": results}
