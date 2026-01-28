from typing import Any, Dict, List
from storage.audit_logger import AuditLogger
from models import ResearchTask

class ResearchOrchestrator:
    """Orchestrates agents to complete research tasks and logs audit entries."""

    def __init__(self, audit_log_path: str = "./audit.log"):
        self.audit = AuditLogger(audit_log_path)

    def run(self, task: ResearchTask, agents: List[Any]) -> Dict[str, Any]:
        self.audit.log(actor="orchestrator", action="start_task", details={"task": task.to_dict()})
        results = {}
        for agent in agents:
            self.audit.log(actor=agent.info().get("name", "agent"), action="start_action", details={"task_id": task.id})
            try:
                output = agent.act(task)
                results[agent.info().get("name", "agent")] = output
                self.audit.log(actor=agent.info().get("name", "agent"), action="complete_action", details={"output": output})
            except Exception as e:
                self.audit.log(actor=agent.info().get("name", "agent"), action="error", details={"error": str(e)})
                results[agent.info().get("name", "agent")] = {"error": str(e)}
        self.audit.log(actor="orchestrator", action="finish_task", details={"task_id": task.id})
        return {"task": task.to_dict(), "results": results}
