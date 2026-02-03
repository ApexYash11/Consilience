Summary — what's done vs what's left (payment skipped)

Phase 1 — Foundation

Done: FastAPI scaffold and routes present (main.py, research.py, dependencies.py); DB layer and migrations exist (connection.py, models.py, migrations/); config and security stubs (config.py, security.py); basic tests present (tests).
Remaining: Run/configure Neon DB (connection strings, migrate), finalize Neon-managed auth middleware (validate assertions/session tokens), end-to-end auth tests, CI for migrations and basic health checks.
Phase 3 — Standard Research (LangGraph)

Done: Agent modules and tools scaffolding present (standard: planner.py, researcher.py, verifier.py, detector.py, synthesizer.py, reviewer.py, formatter.py); orchestrator file exists (standard_orchestrator.py); tools implemented (web_search.py, academic_search.py, source_verification.py, pdf_extraction.py); OpenRouter wrapper in openrouter_client.py.
Remaining: Implement concrete LangGraph StateGraph definitions and conditional routing, wire agents for parallel execution & orchestration, ensure agent outputs persist to DB (research_tasks, agent_actions), integrate real cost tracking per run, end-to-end tests for /api/research/standard.
Phase 4 — Deep Research (LangChain Deep Agents)

Done: Deep agent scaffold and orchestrator files present (deep_researcher.py, deep_orchestrator.py); tooling for sub-tasks exists in tools.
Remaining: Integrate and test deepagents runtime (file read/write tooling), implement sub-agent spawning and recursive rounds, implement file-system-backed context management, gate deep flows by user tier, add cost-estimate-before-run endpoint, robust testing of recursive verification and reviewer cycles.
Phase 5 — Quota & Rate Limiting

Done: Architecture and schema include usage_logs and quota concepts; sample middleware idea in doc.
Remaining: Implement usage logging (persist LLM calls to usage_logs), quota checks (check_quota) and middleware, add slowapi rate limiting, add /api/users/usage dashboard endpoints, tests for quota enforcement.
Phase 6 — Testing & Polish

Done: Unit/integration test stubs exist (tests); Alembic present.
Remaining: Full E2E tests for standard + deep flows, webhook/webhook-handler tests (payment skipped), retry/error handling for LLM calls, performance tuning (DB indices, pooling), API docs (OpenAPI) and user docs.
Immediate next actions (recommended)

Run DB migrations and verify Neon connection; seed test data.
Finish Neon auth middleware and verify protected endpoints.
Wire LangGraph StateGraph in standard_orchestrator.py to call agents/standard/* in parallel and persist outputs.
Implement LLM usage logging in openrouter_client.py → write to usage_logs.
Start integration tests for standard research flow.