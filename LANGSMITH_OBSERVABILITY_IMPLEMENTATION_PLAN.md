# LangSmith Observability Implementation Plan

**Project:** Consilience (FastAPI + LangGraph multi-agent research platform)
**Date:** March 13, 2026
**Scope:** Planning only (no code changes in this step)

---

## Objective

Implement production-safe LangSmith observability across the platform, including:

1. LangSmith tracing
2. Agent-level performance monitoring
3. Research pipeline metrics
4. Observability dashboard metrics
5. Token usage tracking
6. Cost tracking integration
7. Background task tracing
8. Database correlation between LangSmith runs and `research_tasks`

---

## Key Constraints (Must Not Break)

1. Do not interfere with rate limiting in `api/dependencies.py` and `services/rate_limiter.py`.
2. Do not add blocking network calls in request dependency path.
3. Do not replace existing cost/token logic in `utils/cost_estimator.py` and `ResearchService.log_token_usage()`.
4. LangSmith failures must never break task execution or API responses.
5. Preserve async background execution behavior (`asyncio.create_task(...)`).
6. Avoid duplicate tracing where LangGraph already emits spans.

---

## Current Architecture Findings (Summary)

1. Background research execution runs in:
- `api/routes/research.py`:
- `_execute_research_background(...)`
- `_execute_deep_research_background(...)`

2. Standard graph invocation exists in:
- `orchestrator/standard_orchestrator.py` (`graph.ainvoke(..., config={"run_name": ...})`)

3. Deep graph invocation exists in:
- `orchestrator/deep_orchestrator.py` (`graph.ainvoke(initial_state)` currently minimal config)

4. Authoritative token/cost flow:
- `services/openrouter_client.py::extract_token_usage(...)`
- `utils/cost_estimator.py::estimate_cost_from_response(...)`
- `services/research_service.py::log_token_usage(...)`

5. DB correlation target already available:
- `database/schema.py` includes `research_tasks.metadata_json`
- `ResearchService.update_research_task(...)` can persist metadata

---

## Phased Implementation Plan

## Phase 1: Baseline Wiring

### Files
- `requirements.txt`
- `.env.example`
- `config/settings.py`
- `core/config.py`

### Changes
1. Add `langsmith>=0.1.0` to dependencies.
2. Add env variables:
- `LANGCHAIN_TRACING_V2`
- `LANGCHAIN_API_KEY`
- `LANGCHAIN_PROJECT`
- `LANGCHAIN_ENDPOINT`
3. Add settings fields in both settings modules so startup and runtime can read tracing config consistently.

### Acceptance
- App boots with tracing disabled by default.
- No behavior changes when env vars are absent.

---

## Phase 2: Startup Bootstrap

### File
- `api/main.py`

### Changes
1. In startup event, if tracing enabled, set:
- `os.environ["LANGCHAIN_TRACING_V2"]`
- `os.environ["LANGCHAIN_API_KEY"]`
- `os.environ["LANGCHAIN_PROJECT"]`
- `os.environ["LANGCHAIN_ENDPOINT"]`
2. Keep existing startup order and DB init behavior unchanged.

### Acceptance
- Startup remains stable.
- Misconfigured LangSmith logs warning/error without crashing non-tracing mode.

---

## Phase 3: Safe LangSmith Helper Layer

### New file
- `services/observability.py` (or `utils/observability.py`)

### Responsibilities
1. Safe import/wrapper for LangSmith APIs.
2. `safe_trace(...)` context manager with fallback no-op.
3. `safe_get_current_run_id()` helper.
4. `safe_create_feedback(...)` helper.
5. Structured metadata merge helper for task-level metrics.

### Acceptance
- Any LangSmith exception is swallowed and logged.
- Callers never fail due to observability issues.

---

## Phase 4: Background Root Trace Contexts

### File
- `api/routes/research.py`

### Changes
1. Wrap `_execute_research_background(...)` in explicit top-level trace context.
2. Wrap `_execute_deep_research_background(...)` in explicit top-level trace context.
3. Attach metadata:
- `task_id`
- `topic`
- `research_depth`
- `user_id` (if available)

### Acceptance
- Request handlers return immediately as before.
- Only background execution path performs tracing network activity.

---

## Phase 5: LangGraph Invocation Metadata

### Files
- `orchestrator/standard_orchestrator.py`
- `orchestrator/deep_orchestrator.py`

### Changes
1. Standard graph: enrich existing `config` with tags + metadata.
2. Deep graph: add missing `config` with run name, tags, metadata.
3. Metadata examples:
- `task_id`
- `topic`
- `research_mode` (`standard`/`deep`)
- `num_sources_target`
- deep research expectations (`rounds`, `sub_agents`)

### Acceptance
- Graph runs unchanged functionally.
- LangSmith trace hierarchy is discoverable by task/topic/mode.

---

## Phase 6: LLM Trace Boundary + Token/Cost Attachment

### File
- `agents/base_agent.py`

### Changes
1. Add traceable boundary around `call_llm_with_retry(...)` with `run_type="llm"`.
2. Capture timing + retry/circuit-breaker counters where available.
3. Attach token/cost metadata from existing OpenRouter/cost extraction call-sites.

### Acceptance
- Existing retry, timeout, circuit-breaker behavior unchanged.
- No separate cost system introduced.

---

## Phase 7: Agent-Level Metrics

### Files
- `agents/standard/planner.py`
- `agents/standard/researcher.py`
- `agents/standard/verifier.py`
- `agents/standard/detector.py`
- `agents/standard/synthesizer.py`
- `agents/standard/reviewer.py`
- `agents/standard/formatter.py`
- `agents/deep/deep_researcher.py`

### Changes
Attach per-agent metadata/events:
- `agent_name`
- `execution_time_ms`
- `tokens_used`
- `cost_usd`
- `retry_count`
- `circuit_breaker_failures`
- quality signals when applicable (`source_quality_score`, `synthesis_confidence`, revisions)

### Acceptance
- Agent logic/output unchanged.
- Metrics are visible per node/agent in traces.

---

## Phase 8: Tool Tracing

### Files
- `tools/web_search.py`
- `tools/academic_search.py`
- `tools/source_verification.py`
- `tools/file_system.py` (active tooling path today)

### Changes
1. Add traceable decorators/wrappers for tool runs (`run_type="tool"`).
2. Since three requested tool modules are currently empty, add minimal instrumentable function stubs/placeholders for future use.
3. Instrument currently active file-system tool calls used by deep research for immediate visibility.

### Acceptance
- No runtime regressions if optional tools are not used.
- Tool-level traces appear for active deep-research tool operations.

---

## Phase 9: DB Correlation (LangSmith Run ID)

### Files
- `services/research_service.py`
- `api/routes/research.py` and/or orchestrator completion hooks

### Changes
1. Capture current run ID (`get_current_run_tree()` equivalent via safe helper).
2. Persist into `research_tasks.metadata_json` under keys like:
- `langsmith_run_id`
- `langsmith_project`
- `langsmith_trace_url` (optional)
3. Use merge semantics to preserve existing metadata.

### Acceptance
- Each completed task has run ID correlation in DB metadata.
- No schema migration required.

---

## Phase 10: Dashboard Metrics + Feedback

### Source of metrics
- `models/research.py` (`ResearchState`)

### Attach to top-level run
- `topic`
- `research_depth`
- `total_cost_usd`
- `tokens_used`
- `execution_time_seconds`
- `num_sources_collected`
- `num_verified_sources`
- `source_quality_score`
- `synthesis_confidence`
- `revision_cycles`
- `fallback_triggered`
- `contradictions_detected`
- `paper_length_chars`

### Feedback keys
- `source_quality_score`
- `synthesis_confidence`
- `revision_cycles`
- `paper_length_chars`

### Acceptance
- Metrics visible in LangSmith run metadata/feedback.
- Values match existing state/cost outputs.

---

## Testing and Validation Plan

1. Run rate-limit and quota tests to ensure no regressions:
- `tests/test_rate_limiter.py`
- `tests/test_quota_enforcement.py`

2. Run workflow tests:
- `tests/test_standard_research.py`
- deep workflow tests if present

3. Add tests for observability safety:
- LangSmith import failure does not break tasks
- LangSmith API exception does not fail task lifecycle
- Background task still runs to completion/failure normally

4. Validate DB correlation:
- `research_tasks.metadata_json` includes `langsmith_run_id`

5. Validate cost parity:
- Task totals align with `token_usage_logs` aggregates

---

## Rollout Order (Recommended)

1. Phase 1 + 2 (wiring + startup)
2. Phase 3 (safe helper)
3. Phase 4 + 5 (root tracing + graph metadata)
4. Phase 6 + 7 (LLM + agent metrics)
5. Phase 8 (tools)
6. Phase 9 + 10 (DB correlation + dashboard feedback)
7. Validation tests and staging verification

---

## Notes

1. Keep `api/dependencies.py` and rate limiter path untouched for performance.
2. Keep existing cost math as the single source of truth.
3. Prefer metadata/events over excessive nested spans to avoid duplicate noise.
4. Wrap all LangSmith calls in safe helpers and `try/except`.
