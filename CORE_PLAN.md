# Core Development Plan & Clean Architecture

## 1. Project Intent
To provide an enterprise-grade research pipeline that uses specialized agents to overcome the limitations of single-prompt AI generation. Focus: **Trust through Traceability**.

## 2. Refined Architecture
```text
[Request] --> [API: main.py] 
                   |
           [Orchestrator: workflow.py] <---> [Audit: audit_logger.py]
                   |
           ┌───────┴───────┐
           │   Agent Pool  │
           │ - Planner     │ --> [Tools: Search, WebFetch]
           │ - Researcher  │
           │ - Reviewer    │
           └───────┬───────┘
                   |
           [Synthesis] --> [Final Paper]
```

## 3. Scaffolding Progress
- [x] Standardized `BaseAgent` abstract class.
- [x] Streamlined `api/main.py` entry point.
- [x] Implemented `orchestrator/audit_logger.py` with SQLite integration.
- [x] Modernized `PROJECT_SUMMARY.md` and `README.md`.

## 4. Next Steps (Priority)
1. **Agent Implementation**: Implement `Planner` and `Researcher` agents based on the new `BaseAgent`.
2. **Workflow Engine**: Develop `orchestrator/workflow.py` using LangGraph or a simple Python state machine to manage agent sequencing.
3. **Tool Registry**: Create a standardized interface for agents to access web search and document extraction tools.
4. **Human-in-the-Loop Gateway**: Implement an endpoint in `api/routes/research.py` to handle pending human approvals for risky agent actions.

## 5. Development Principles
- **Minimalism**: Favor clear, direct Python code over complex abstractions.
- **Audit First**: No agent action shall occur without an accompanying audit entry.
- **Fail Fast**: The orchestrator should halt and escalate on low-confidence outputs or tool failures.
