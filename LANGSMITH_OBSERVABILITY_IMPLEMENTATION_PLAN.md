# LangSmith Observability Implementation Plan

**Project:** Consilience (FastAPI + LangGraph multi-agent research platform)
**Date:** March 19, 2026 (Revised)
**Scope:** Planning only (no code changes in this step)
**Strategy:** Dual-mode observability—local debugging (rich context) + production monitoring (cost/quality alerts)

---

## Objective

Implement production-safe LangSmith observability with two distinct modes:

**Local Development:** Catch & debug issues early by seeing full context
- Full tracing with state snapshots at each agent transition
- Exception capture with traceback + last known state
- Export capability: save production traces + state for local replay

**Production Monitoring:** Alert on anomalies and enable quick diagnosis  
- Sampled tracing (cost-effective)
- Cost anomaly alerts (>2σ above baseline)
- Quality alerts (synthesis confidence, source quality drops)
- Failure alerts with LangSmith trace links
- DB correlation for cross-reference

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

## Phase 7: Agent Metrics + State Snapshots (LOCAL-FOCUSED)

### Files
- `agents/base_agent.py`
- `agents/standard/planner.py`
- `agents/standard/researcher.py`
- `agents/standard/verifier.py`
- `agents/standard/detector.py`
- `agents/standard/synthesizer.py`
- `agents/standard/reviewer.py`
- `agents/standard/formatter.py`
- `agents/deep/deep_researcher.py`
- NEW: `utils/state_serializer.py` (serialize ResearchState for tracing)

### Changes
Attach per-agent metadata/events:
- `agent_name`, `execution_time_ms`, `tokens_used`, `cost_usd`
- `retry_count`, `circuit_breaker_failures`
- **NEW—State snapshots:** ResearchState before & after agent execution
  - `state_before`: Full Research state (sources collected, quality scores, contradictions, synthesis confidence)
  - `state_after`: Updated Research state
  - Enables locals to debug why agent made its decision
- **NEW—Decision metadata:** Agent reasoning/path chosen (e.g., "planner chose narrow search after broad failed")
- Quality signals: `source_quality_score`, `synthesis_confidence`, revisions

### Acceptance
- Agent logic/output unchanged.
- Metrics + state snapshots visible per node in traces.
- Developers can inspect state transitions to understand agent behavior.

---

## Phase 8: Error & Exception Capture (LOCAL + PRODUCTION)

### Files
- `services/observability.py`
- `api/routes/research.py`
- `orchestrator/standard_orchestrator.py`
- `orchestrator/deep_orchestrator.py`

### Changes
1. Wrap graph invocations in try/except to capture task failures
2. When exception occurs:
   - Log exception + full traceback
   - Capture last known ResearchState before failure
   - Create LangSmith event with exception + context
   - Store `error_info` in `research_tasks.metadata_json`
3. Capture fallback logic triggers (e.g., "switched to narrow search after broad search failed")
4. Log circuit-breaker activations with last known state

### Acceptance
- Task failures appear in LangSmith traces with full exception context
- DB `metadata_json` includes `error_info` for traceability
- Locals can inspect last state when task fails
- Production alerts include error summary in notification

---

## Phase 9: Production-Only—Alerting Setup

### Files
- NEW: `services/alerting.py`
- `config/settings.py` (add alert thresholds and configurations)
- `database/models.py` (add alert tracking table if needed)

### Changes
1. Define alert thresholds:
   - **Cost anomaly:** Task cost exceeds mean + 2σ for same depth/topic
   - **Quality drop:** `source_quality_score` or `synthesis_confidence` below threshold (e.g., <0.6)
   - **Failure rate spike:** >5% of tasks in last \`X\` minutes failed
   - **Rate limiting:** Unusual API rejection spike
2. Implement alert dispatcher:
   - Write to structured logs (JSON format for Splunk/CloudWatch/etc.)
   - Optional webhook integration (Slack, PagerDuty, etc.)
   - Include LangSmith trace link + error summary + last ResearchState snippet
3. Implement metrics aggregator for baseline (mean, stddev) calculation

### Acceptance
- Alerts fire to logs without breaking task execution
- Each alert includes: task_id, LangSmith run URL, error/context snippet
- Thresholds are configurable via env/settings
- Sampled production traces (not 100%—configurable sampling rate)

---

## Phase 10: Debugging Export & Local Replay (PRODUCTION ENDPOINT)

### Files
- NEW: `api/routes/debug.py` (protected endpoint)
- NEW: `utils/trace_exporter.py`
- `services/observability.py` (add export helpers)

### Changes
1. New endpoint: `GET /debug/trace/{task_id}` (auth required)
   - Returns full LangSmith trace + ResearchState snapshots + error info
   - Format: JSON bundle including:
     - Task metadata (topic, depth, user_id, timestamps)
     - All state snapshots from each agent transition
     - Exception info if failed
     - Token usage + cost breakdown
2. Export function:
   - Fetch trace from LangSmith API
   - Combine with state snapshots from DB
   - Create reproducible payload that can be used locally with inputs
3. Security:
   - Require auth (API key, user token)
   - Log all exports for audit

### Acceptance
- Ops can export a production task that failed/had anomaly
- Dev can run locally with same state/context for debugging
- No sensitive data exposed without auth

---

## Phase 11: DB Correlation (LangSmith Run ID) + Alerts

### Files
- `services/research_service.py`
- `api/routes/research.py` and/or orchestrator completion hooks

### Changes
1. Capture current run ID from LangSmith context (via safe helper)
2. Persist into `research_tasks.metadata_json` under keys:
   - `langsmith_run_id`
   - `langsmith_project`
   - `langsmith_trace_url` (clickable link)
3. When persisting, preserve existing metadata (merge, don't replace)
4. On task failure, also persist `error_info` with exception + traceback

### Acceptance
- Each completed/failed task has LangSmith linkage in DB
- Tasks are cross-referenceable: task → trace and trace → task
- No schema migration required (uses existing `metadata_json`)

---

## Phase 12: Dashboard Metrics + Feedback (TOP-LEVEL RUN)

### Source of metrics
- `models/research.py` (`ResearchState`)

### Changes
1. Attach metrics to top-level LangSmith run **after task completion**
2. Metrics to capture:
   - `topic`, `research_depth`, `total_cost_usd`, `tokens_used`, `execution_time_seconds`
   - `num_sources_collected`, `num_verified_sources`
   - `source_quality_score`, `synthesis_confidence`, `revision_cycles`
   - `fallback_triggered`, `contradictions_detected`, `paper_length_chars`
3. Use LangSmith feedback API to attach quality metrics
4. Tag run by outcomes (success, failed_early, quality_low, etc.)

### Acceptance
- Metrics visible in LangSmith run metadata/feedback
- Values match existing state/cost outputs
- Dashboard can filter runs by quality/cost/outcomes

---

## Phase 13: Tools (Active Instrumentation Only)

### Decision
**Remove tool stubs from earlier consideration.** Instrument tools ONLY when they are integrated and actively used, not speculatively.

### Files to instrument when integrated
- `tools/web_search.py` (when integrated)
- `tools/academic_search.py` (when integrated)
- `tools/source_verification.py` (when integrated)
- `tools/file_system.py` (active today—instrument immediately)

### Changes for active tools only
1. Add traceable decorators/wrappers for tool runs (`run_type="tool"`)
2. Capture tool name, input + output, execution time
3. Attach to LangSmith traces as child spans of calling agent

### Acceptance
- No dead code (no tool instrumentation for unused tools)
- Active tools (especially file_system.py in deep research) have visibility
- When new tool integrates, add instrumentation at that time

---

## Testing and Validation Plan

### Regression Tests (Must Pass)
1. Run rate-limit and quota tests:
   - `tests/test_rate_limiter.py`
   - `tests/test_quota_enforcement.py`
2. Run workflow tests:
   - `tests/test_standard_research.py`
   - Deep workflow tests if present
3. Verify tracing doesn't block:
   - LangSmith import failure doesn't break tasks
   - LangSmith API exception doesn't fail task lifecycle
   - Background tasks complete normally with/without tracing

### New Tests (Local Debugging)
1. State snapshot serialization:
   - ResearchState serializes without errors
   - State before/after captures are meaningful
2. Exception handling:
   - Task failure is captured with full traceback
   - Last state is persisted in `error_info`

### New Tests (Production Monitoring)
1. Alerting logic:
   - Cost anomaly detected when >2σ above baseline
   - Quality alert fires when confidence drops
   - Failure alert fires with correct metadata
   - Alerts don't block task execution
2. Trace export:
   - `/debug/trace/{task_id}` returns full payload
   - Auth is enforced
   - Exported state matches DB metadata
3. DB correlation:
   - `research_tasks.metadata_json` includes `langsmith_run_id`
   - `langsmith_trace_url` is clickable and valid

### Validation
1. Cost parity: Task totals align with `token_usage_logs` aggregates
2. State correctness: Exported state matches final DB state
3. Production deployment: Alerting fires without impacting API latency

---

## Rollout Order (Recommended)

### Foundation (Shared, both local & production)
1. Phase 1 + 2 (wiring + startup)
2. Phase 3 (safe helper layer)
3. Phase 4 + 5 (root tracing + graph metadata)
4. Phase 6 (LLM call tracing)

### Local Development First
5. Phase 7 (agent metrics + **state snapshots**)
   - Run locally to verify state capture works
6. Phase 8 (error & exception capture)
   - Test by running failures locally
7. Phase 11 (DB correlation)
   - Verify LangSmith run IDs persist

### Production Rollout
8. Phase 9 (alerting setup)
   - Test alerts in staging
   - Configure thresholds based on baseline metrics
9. Phase 10 (export/replay endpoint)
   - Enable ops to export production traces
   - Test in staging with sample data
10. Phase 12 (dashboard metrics)
    - Deploy to production with minimal sampling initially
11. Phase 13 (tools)
    - Only when tools are actively integrated

### Final Validation
- Run all regression tests
- Verify alerts fire correctly in production
- Confirm export/replay works end-to-end
- Validate cost parity across all pipelines

---

## Notes & Strategy

### Design Principles
1. **Local-first observability:** Developers need to see state transitions + decisions locally
2. **Production cost-effective:** Use sampled tracing, not 100% traces
3. **Never break tasks:** LangSmith failures are swallowed and logged, never break execution
4. **Single source of truth for cost:** Existing `cost_estimator.py` + `log_token_usage()` remain authoritative
5. **Dual metadata strategy:**
   - LangSmith: Structure (execution flow, timing, spans)
   - DB `metadata_json`: Final outcomes + cost + state snapshots + errors

### Implementation Constraints
1. Keep `api/dependencies.py` and rate limiter path untouched for performance
2. Keep existing cost math as the single source of truth
3. Prefer metadata/events over excessive nested spans to avoid duplicate noise
4. Wrap all LangSmith calls in safe helpers with `try/except`
5. Don't instrument tools until they're actively integrated (no dead code)
6. State snapshots should be compact JSON, not full object serialization

### Local vs. Production Differences

| Aspect | Local | Production |
|---|---|---|
| Tracing | 100% (all tasks) | Sampled (configurable %) |
| State snapshots | Full capture | Sampled or summary only |
| Exceptions | Full traceback + state | Summary + last state |
| Alerts | Manual inspection | Automated + webhooks |
| Export | Manual via dashboard | `/debug/trace` endpoint (auth) |
| Latency impact | Acceptable | Minimal (async, sampled) |

### Future Enhancements
- Machine learning on traces for anomaly detection (beyond threshold-based alerts)
- Custom agent reasoning metrics (reasoning chains, token efficiency per agent)
- Replay/mutation testing framework for debugging (e.g., "what if this agent chose differently?")
- Multi-modal tracing (combine with metrics from cost_estimator, rate limiter, etc.)
