"""Small demo that runs the research orchestrator with a planning agent."""
from models import ResearchTask, AgentSpec
from orchestrator.research_orchestrator import ResearchOrchestrator
from agents.research_planning_agent import ResearchPlanningAgent


def main():
    task = ResearchTask(id="task-001", title="Survey topic X", description="Produce an initial research plan")

    planner_spec = AgentSpec(name="planner-1", role="research_planner", capabilities=["summarize","plan"]) 
    planner = ResearchPlanningAgent(spec=planner_spec)

    orchestrator = ResearchOrchestrator(audit_log_path="./audit.log")
    result = orchestrator.run(task, agents=[planner])

    print("Demo result:")
    print(result)


if __name__ == "__main__":
    main()
