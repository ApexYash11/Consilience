# Consilience: Project Summary

##  Core Objective
Consilience is a production-grade multi-agent research orchestration platform. It automates high-quality academic and market research through a structured pipeline of specialized AI agents (Planning, Research, Verification, Synthesis). The system prioritizes reliability, auditability, and human-in-the-loop checkpoints, using a deterministic Python orchestration layer to coordinate LLM actions.

##  System Architecture
The platform follows a modular architecture:
- **Orchestration Layer**: A deterministic state machine (LangGraph/Pure Python) controlling task flow.
- **Agent Layer**: specialized agents with specific roles, using a standard communication protocol.
- **Audit System**: An immutable log recording every intent, tool call, and result for complete traceability.
- **API Layer**: FastAPI endpoints for submitting tasks and monitoring agent state.

##  Tech Stack
- **Language**: Python 3.12+
- **API**: FastAPI, Uvicorn
- **Logic**: Pydantic v2, LangChain, LangGraph
- **Database**: SQLAlchemy 2.0 (SQLite for audit/local config)
- **AI**: Integration with OpenAI and Anthropic models

##  Core Structure
- `agents/`: Base framework and specialized agent implementations.
- `api/`: REST API surface and route definitions.
- `orchestrator/`: Workflow management and the immutable audit logger.
- `models/`: Type-safe data structures using Pydantic.
- `database/`: Persistence layer and ORM schemas.
- `services/`: Core business logic (auth, research, cost estimation).

##  Key Features
- **Deterministic Orchestration**: No rogue autonomous loops; full control over agent sequences.
- **Immutable Audit Trail**: SQLite-backed logging for every agent action.
- **Human-in-the-Loop**: Explicit checkpoints for approval on low-confidence results.
- **Scalable Agent System**: Easy integration of new specialized agents via `BaseAgent`.
