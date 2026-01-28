from typing import Any, Dict
from models import AgentSpec

class BaseAgent:
    """Simple agent framework. Subclass and implement `act` or `plan`."""

    def __init__(self, spec: AgentSpec):
        self.spec = spec

    def act(self, task: Any) -> Dict[str, Any]:
        raise NotImplementedError("Agents must implement `act` or `plan`.")

    def info(self) -> Dict[str, Any]:
        return {"name": self.spec.name, "role": self.spec.role, "capabilities": self.spec.capabilities}
