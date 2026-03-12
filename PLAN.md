# Consilience — Project Plan & Roadmap

**Platform:** Production-grade multi-agent research orchestration  
**Date:** March 12, 2026  
**Overall Completion:** ~85% (Phases 1, 3, 4 Code-Complete; Phases 2, 5, 6 In Progress)

---

## What It Does

Takes a research topic → runs coordinated AI agents → produces a cited research paper.

Two tiers:
- **Standard (FREE)** — 7 agents, LangGraph state machine, ~3 min, ~$1–2/paper
- **Deep (PAID, $29/mo)** — 18 sub-agents, 3 recursive rounds, ~10 min, ~$10/paper

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI 0.104+ |
| Standard Orchestration | LangGraph (StateGraph) |
| Deep Orchestration | LangGraph + custom sub-agent spawning |
| LLM Provider | OpenRouter (unified API) |
| Database | Neon Serverless PostgreSQL |
| Auth | Neon JWT |
| Payments | **Dodo Payments** |
| Python | 3.12+ |

---

## Phase Status
## Phase Status
| Phase | Status | Notes |
|---|---|---|
| 1 — Foundation | ✅ 100% | FastAPI, auth, DB, CI/CD — 39/41 tests pass |
| 3 — Standard Research | ✅ 100% code | 7 agents, 11-node LangGraph, 17/17 unit tests |
| 4 — Deep Research | ✅ 100% code | 18 sub-agents, 3 rounds, file-system context, 35+ tests |
| 2 — Payments | 🔄 In Progress | Dodo Payments integration replacing Stripe scaffold |
| 5 — Quota / Rate Limiting | 🔄 In Progress | DB schema ready; service implementation underway |
| 6 — Testing & Polish | ⚠️ 30% | E2E tests need DB mocking; no API docs |

---

## What's Left — Ordered by Priority

### Phase A — E2E Test Fixes + Staging (2–3 days)

1. Add `override_get_db` mock fixture to `tests/conftest.py` — unblocks 5 E2E tests for research endpoints
2. Fix `mocker` fixture import for `test_research_result_retrieval`
3. Run full test suite — target 100% pass
4. Configure staging `.env` (OPENROUTER_API_KEY, Neon DB URL)
5. Run 1 standard + 1 deep research task with real API; validate cost and agent logs

**Files:** `tests/conftest.py`, `tests/test_standard_research.py`

---

### Phase B — Dodo Payments Integration (3–5 days)

Payment provider: **Dodo Payments** (`dodopayments` Python SDK)

**Flow:**
1. User clicks upgrade → `POST /api/payments/checkout` → returns Dodo checkout URL
2. User pays → Dodo calls `POST /api/webhooks/dodo` with event payload
3. Webhook handler verifies HMAC signature → updates user tier in DB
4. User now has PAID tier → can access `/api/research/deep`

**Steps:**
1. ✅ Replace `stripe` with `dodopayments` in `pyproject.toml`
2. ✅ Rewrite `models/payment.py` — Dodo models
3. ✅ Rename schema columns — `dodo_customer_id`, `dodo_subscription_id`
4. ✅ Implement `services/payment_service.py` — Dodo checkout, subscriptions
5. ✅ Implement `api/routes/webhooks.py` — handle Dodo events with HMAC verification
6. ✅ Wire `api/routes/payments.py` — GET /plans, POST /checkout, POST /cancel
7. ✅ Implement `services/user_service.py` — sync tier after webhook
8. ✅ Register routes in `api/main.py`

**Security:** Webhook HMAC verification is mandatory. `DODO_API_KEY` and `DODO_WEBHOOK_SECRET` in env vars only.

---

### Phase C — Quota & Rate Limiting (3–5 days)

1. ✅ Implement `services/cost_service.py`
2. ✅ Add quota check dep in `api/dependencies.py` — HTTP 429 on over-limit
3. ✅ Hook usage logging into orchestrator callbacks
4. ✅ Add `GET /api/users/usage` endpoint
5. Rate limiting via Slowapi on `/api/research/*`
6. Quota enforcement tests

---

### Phase D — Polish & Docs (2–3 days)

1. Add `response_model`, `summary`, `description` to all route decorators → Swagger at `/docs`
2. Update `README.md` with API quickstart and example curl commands
3. Implement TTL cleanup for `research_context/` directories
4. Load test (5 concurrent users) — validate DB pool and agent timeouts

---

## Verification Checklist

- [ ] `pytest tests/ -v` → 100% pass
- [ ] `GET /health` → `{"status": "healthy", "database": "connected"}`
- [ ] `POST /api/research/standard` → completes in <5 min with real OpenRouter key
- [ ] `POST /api/research/deep` (PAID tier) → completes in <12 min
- [ ] `POST /api/payments/checkout` → returns Dodo checkout URL
- [ ] Dodo test webhook → DB tier updates to PAID
- [ ] Exceed monthly quota → HTTP 429
- [ ] `GET /api/users/usage` → correct token/cost breakdown

---

## Architecture Overview

```
User Request
      ↓
FastAPI (Auth · Payments · Research endpoints)
      ↓
┌─────────────────────────────────────────┐
│ Standard Orchestrator (LangGraph)        │  FREE tier
│ Planner → 5× Researchers → Verifier     │
│ → Detector → Synthesizer → Reviewer     │
│ → Formatter                             │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│ Deep Orchestrator (LangGraph)            │  PAID tier
│ 18 sub-agents · 3 rounds                │
│ Round 1: 10 broad researchers            │
│ Round 2: 5 gap-filling researchers       │
│ Round 3: 3 contradiction resolvers       │
└─────────────────────────────────────────┘
      ↓
OpenRouter (LLM: GPT-4 · Claude · Gemini)
      ↓
Neon PostgreSQL
```

---

## Project Structure

```
api/                     FastAPI app, routes, dependencies
agents/standard/         7 standard research agents ✅
agents/deep/             Deep researcher agent ✅
orchestrator/            LangGraph state machines ✅
services/                payment_service ✅  user_service ✅  cost_service ✅
tools/                   Web search, academic search, file system, PDF
database/                Schema (Dodo columns) ✅, connection, models
models/                  research ✅  payment (Dodo) ✅
tests/                   Phase 1+3+4 unit tests ✅  E2E needs fix ⚠️
config/                  Settings, model config, logging
core/                    Security (JWT), config, exceptions
```

---

## Environment Variables Required

```bash
# Database
DATABASE_URL=postgresql+asyncpg://...neon.tech/consilience

# Auth
AUTH_URL=https://...neon.tech
JWKS_URL=https://...neon.tech/.well-known/jwks.json

# LLM
OPENROUTER_API_KEY=sk-or-...

# Payments (Dodo Payments)
DODO_API_KEY=...
DODO_WEBHOOK_SECRET=...

# App
ENVIRONMENT=production
DEBUG=false
```
