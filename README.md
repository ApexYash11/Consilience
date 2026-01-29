# Consilience: Multi-Agent Research Orchestration

A production-style system for generating research papers through coordinated multi-agent collaboration, verification, and quality control.

##  Overview
Consilience is designed to solve the reliability gap in AI agents. Instead of autonomous "black boxes," it uses a deterministic orchestration layer to guide specialized agents through a rigorous research process.

##  Key Components
- **Deterministic Orchestrator**: Manages workflow states and agent transitions.
- **Specialized Agents**: 
  - `Planner`: Breaks down topics into verifiable claims.
  - `Researcher`: Executes deep-web searches and evidence extraction.
  - `Reviewer`: Critiques methodology and verifies citations.
- **Audit System**: Immutable logging of every agent action to SQLite.
- **FastAPI Interface**: standard REST API for task submission and status monitoring.

##  Getting Started
1. **Clone the repository**
2. **Install dependencies**: `pip install -r requirements.txt`
3. **Configure Environment**: Add `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` to `.env`.
4. **Run the API**: `python api/main.py`

##  Architecture
For details on system flow, see [ARCHITECTURE_DIAGRAM.txt](ARCHITECTURE_DIAGRAM.txt).
For project roadmap and setup, see [SETUP.md](SETUP.md).

---
*Built for reliability, auditability, and trust.*
