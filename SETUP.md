# Consilience: Project Setup & Planning Guide

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture Summary](#architecture-summary)
3. [Setup Instructions](#setup-instructions)
4. [Development Roadmap](#development-roadmap)
5. [Component Implementation Order](#component-implementation-order)
6. [Testing Strategy](#testing-strategy)
7. [Deployment Considerations](#deployment-considerations)

---

## 1. Project Overview

### What is Consilience?

Consilience is a **production-grade multi-agent orchestration system** designed to generate college-quality research papers through:

- **Independent investigation** by multiple AI agents
- **Adversarial verification** where agents challenge each other's findings
- **Human oversight** at critical decision points
- **Complete auditability** of every action and decision

### What Makes It Different?

| Feature | Single-Agent Systems | Consilience |
|---------|---------------------|-------------|
| Source verification | Optional, if prompted | Mandatory, automated |
| Contradiction handling | Smooths over conflicts | Explicitly surfaces disagreements |
| Confidence assessment | Self-reported (unreliable) | Cross-agent comparison |
| Auditability | Chat history only | Full action log with reasoning |
| Human involvement | All or nothing | Strategic checkpoints only |
| Failure detection | Reactive (user notices) | Proactive (system detects) |

### Core Value Propositions

1. **For Students/Researchers:** College-quality papers with verified sources
2. **For Educators:** Transparent research process, not black-box AI
3. **For Institutions:** Auditable, quality-controlled research assistance
4. **For Developers:** Reference implementation for multi-agent coordination

---

## 2. Architecture Summary

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                     │
│  /tasks, /checkpoints, /audit, /papers                      │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              Research Orchestrator (Pure Python)            │
│  • Task lifecycle management                                │
│  • Phase sequencing (planning → research → synthesis)       │
│  • Failure handling & retry logic                           │
│  • Human checkpoint enforcement                             │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Agent Coordinator                         │
│  • Agent registration & tool injection                      │
│  • Parallel execution management                            │
│  • Inter-agent communication                                │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
┌────────▼─────────┐          ┌─────────▼────────┐
│     Agents       │          │      Tools       │
│  • Planner       │◄────────►│  • Search        │
│  • Researchers   │          │  • Verification  │
│  • Verifier      │          │  • PDF Extract   │
│  • Detector      │          │  • Web Fetch     │
│  • Synthesizer   │          └──────────────────┘
│  • Reviewer      │
│  • Formatter     │
└────────┬─────────┘
         │
┌────────▼─────────────────────────────────────────────────────┐
│                   Audit Logger (SQLite)                      │
│  • agent_actions table                                       │
│  • sources, verifications, contradictions tables             │
│  • human_checkpoints table                                   │
│  • task_state_changes table                                  │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User Request
    ↓
Task Created (Audit Log Entry #1)
    ↓
Phase 1: Planning Agent
    ├─ Generate research plan (Audit Log Entry #2)
    └─ Human Checkpoint: Approve plan? (Audit Log Entry #3)
    ↓
Phase 2: 5x Researcher Agents (Parallel)
    ├─ Agent A searches academic DB (Audit Log Entry #4)
    ├─ Agent B searches meta-analyses (Audit Log Entry #5)
    ├─ Agent C searches contradictory evidence (Audit Log Entry #6)
    ├─ Agent D searches original studies (Audit Log Entry #7)
    └─ Agent E searches longitudinal studies (Audit Log Entry #8)
    ↓
Phase 3: Verification Agent
    ├─ Verify Source 1 (Audit Log Entry #9)
    ├─ Verify Source 2 (Audit Log Entry #10)
    ├─ ... (50-80 verifications)
    └─ Human Checkpoint: High rejection rate? (Audit Log Entry #N)
    ↓
Phase 4: Contradiction Detector
    ├─ Extract claims from sources
    ├─ Compare claims cross-source
    └─ Human Checkpoint: Critical contradictions? (Audit Log Entry #M)
    ↓
Phase 5: Synthesis Agent
    └─ Write draft paper (Audit Log Entry #P)
    ↓
Phase 6-7: Review & Revision (Loop)
    ├─ Peer Review Agent reviews draft
    ├─ Revision Coordinator addresses issues
    └─ Repeat until "ready_for_publication" = True
    ↓
Phase 8: Citation Formatter
    └─ Format citations & generate references
    ↓
Final Paper Ready
```

---

## 3. Setup Instructions

### Step 1: Environment Setup

```bash
# Create project directory
mkdir consilience
cd consilience

# Create Python virtual environment (recommended)
python3.10 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Directory Structure

```bash
# Create directories
mkdir -p agents orchestrator tools storage api logs tests docs

# Verify structure
ls -la
# Should show: agents/ orchestrator/ tools/ storage/ api/ logs/ tests/ docs/
```

### Step 3: Initialize Database

```bash
# Create logs directory
mkdir -p logs

# Database will auto-initialize on first run
# Location: logs/consilience_audit.db
```

### Step 4: Configuration

Create `.env` file:

```bash
# .env
ANTHROPIC_API_KEY=your_key_here
# OR
OPENAI_API_KEY=your_key_here

# Optional: Academic API keys
GOOGLE_SCHOLAR_API_KEY=your_key
PUBMED_API_KEY=your_key
```

### Step 5: Verify Setup

```bash
# Run demo (currently shows Phase 1 only)
python demo_scenario.py

# Expected output:
# ✓ Agents registered
# ✓ Task created
# ✓ Planning phase completed
# ✓ Audit trail created
```

---

## 4. Development Roadmap

### Phase 1: Foundation ✅ (COMPLETED)
- [x] Data models (Pydantic)
- [x] Audit logging system (SQLite)
- [x] Base agent framework
- [x] Agent coordinator
- [x] Research orchestrator skeleton
- [x] Documentation

**Deliverables:**
- `models.py` - Complete data models
- `storage/audit_logger.py` - Audit logging
- `agents/base_agent.py` - Agent framework
- `orchestrator/research_orchestrator.py` - Workflow engine
- `README.md` - Architecture docs

### Phase 2: Agent Implementation 🔄 (IN PROGRESS)
- [x] Research Planning Agent
- [ ] Researcher Agent (x5 instances)
- [ ] Source Verification Agent
- [ ] Contradiction Detection Agent
- [ ] Synthesis Agent
- [ ] Peer Review Agent
- [ ] Revision Coordinator Agent
- [ ] Citation Formatting Agent

**Implementation Priority:**
1. **Researcher Agent** (critical path - blocks phases 3-8)
2. **Source Verification Agent** (quality gate)
3. **Contradiction Detection Agent** (unique value prop)
4. **Synthesis Agent** (actual output generation)
5. **Peer Review Agent** (quality assurance)
6. **Revision Coordinator** (iteration logic)
7. **Citation Formatter** (final polish)

### Phase 3: Tool Integration
- [ ] Academic Search Tool (Google Scholar, PubMed)
- [ ] Source Verification Tool (DOI lookup, CrossRef)
- [ ] Web Search Tool (general fact-checking)
- [ ] PDF Extraction Tool (read paper contents)
- [ ] Citation Formatter Tool (APA/MLA/Chicago)

**Tool Dependencies:**
- `academic_search.py` → Researcher Agent
- `source_verification.py` → Verification Agent
- `web_search.py` → All research agents
- `pdf_extraction.py` → Verification Agent, Synthesis Agent
- `citation_formatter.py` → Citation Formatting Agent

### Phase 4: API & Interface
- [ ] FastAPI server with REST endpoints
- [ ] Task submission endpoint
- [ ] Progress monitoring endpoint
- [ ] Human checkpoint resolution endpoint
- [ ] Audit trail query endpoint
- [ ] Paper download endpoint

### Phase 5: Testing & Quality
- [ ] Unit tests for all agents
- [ ] Integration tests for workflows
- [ ] End-to-end test with real research topic
- [ ] Performance testing (time, token usage)
- [ ] Failure scenario testing

### Phase 6: Production Readiness
- [ ] Error handling & recovery
- [ ] Rate limiting & cost controls
- [ ] Logging & monitoring
- [ ] Deployment configuration
- [ ] User documentation

---

## 5. Component Implementation Order

### Critical Path (Must Complete First)

```
1. Researcher Agent
   └─ Depends on: academic_search tool, web_search tool
   └─ Blocks: Phases 3-8

2. Source Verification Agent
   └─ Depends on: source_verification tool, pdf_extraction tool
   └─ Blocks: Synthesis quality

3. Contradiction Detection Agent
   └─ Depends on: Verified sources from Phase 3
   └─ Blocks: Synthesis quality

4. Synthesis Agent
   └─ Depends on: Verified sources + contradiction analysis
   └─ Blocks: Paper generation

5. Peer Review Agent
   └─ Depends on: Synthesis output
   └─ Blocks: Quality assurance

6. Revision Coordinator
   └─ Depends on: Peer Review feedback
   └─ Blocks: Iterative improvement

7. Citation Formatting Agent
   └─ Depends on: Final draft
   └─ Blocks: Publication-ready output
```

### Parallel Development Opportunities

**Can develop simultaneously:**
- Researcher Agent + Academic Search Tool
- Verification Agent + Source Verification Tool
- API endpoints + Orchestrator refinement
- Test suite + Documentation

**Dependencies to watch:**
- All agents depend on base_agent.py
- All tools depend on tool interface definition
- Orchestrator depends on agent implementations
- API depends on orchestrator

---

## 6. Testing Strategy

### Unit Tests

**Test each agent independently:**

```python
# Example: test_research_planning_agent.py

async def test_planning_agent_generates_sub_questions():
    """Planning agent should generate 3+ sub-questions."""
    agent = create_research_planning_agent(mock_audit_logger)
    
    context = {
        "topic": "Test topic",
        "requirements": {...}
    }
    
    result = await agent.execute(task_id, context)
    
    assert len(result["output"]["sub_questions"]) >= 3
    assert result["confidence"] in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM]
```

**Test audit logging:**

```python
def test_audit_logger_records_actions():
    """All agent actions should be logged."""
    logger = AuditLogger(":memory:")  # In-memory DB for testing
    
    action = AgentAction(...)
    logger.log_agent_action(action)
    
    actions = logger.get_task_actions(task_id)
    assert len(actions) == 1
    assert actions[0]["action_id"] == str(action.action_id)
```

### Integration Tests

**Test agent coordination:**

```python
async def test_parallel_research_execution():
    """Multiple researcher agents should execute in parallel."""
    coordinator = AgentCoordinator(audit_logger)
    
    # Register 5 researcher agents
    for i in range(5):
        agent = create_researcher_agent(f"researcher_{i}", audit_logger)
        coordinator.register_agent(agent)
    
    # Execute in parallel
    results = await coordinator.execute_parallel(
        [f"researcher_{i}" for i in range(5)],
        task_id,
        context
    )
    
    assert len(results) == 5
    # Each should have found sources
    for result in results:
        assert len(result["sources"]) > 0
```

### End-to-End Tests

**Test complete workflow:**

```python
async def test_full_research_workflow():
    """Complete workflow from submission to paper."""
    orchestrator = ResearchOrchestrator(audit_logger, coordinator)
    
    task = create_test_task("Sample research topic")
    task_id = orchestrator.create_task(task)
    
    # Execute full workflow
    completed_task = await orchestrator.execute_task(task_id)
    
    assert completed_task.status == TaskStatus.COMPLETED
    assert completed_task.final_paper is not None
    assert len(completed_task.verified_sources) >= task.requirements.minimum_sources
```

### Performance Tests

**Measure execution time:**

```python
async def test_performance_under_load():
    """System should handle multiple concurrent tasks."""
    tasks = [create_test_task(f"Topic {i}") for i in range(10)]
    
    start_time = time.time()
    results = await asyncio.gather(*[
        orchestrator.execute_task(task.task_id)
        for task in tasks
    ])
    duration = time.time() - start_time
    
    assert all(r.status == TaskStatus.COMPLETED for r in results)
    assert duration < 600  # Should complete in <10 minutes
```

---

## 7. Deployment Considerations

### Local Development

```bash
# Run FastAPI server locally
uvicorn api.fastapi_server:app --reload --port 8000

# Access API docs
open http://localhost:8000/docs
```

### Production Deployment

**Option 1: Docker Container**

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "api.fastapi_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Option 2: Cloud Platform (AWS/GCP/Azure)**

- Deploy FastAPI as containerized service
- Use managed PostgreSQL for audit log (replace SQLite)
- Set up object storage for generated papers
- Configure API gateway for rate limiting

### Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-...
# or
OPENAI_API_KEY=sk-...

# Optional
DATABASE_URL=postgresql://user:pass@host:5432/consilience
STORAGE_BUCKET=consilience-papers
LOG_LEVEL=INFO
MAX_CONCURRENT_TASKS=10
ENABLE_HUMAN_CHECKPOINTS=true
```

### Monitoring & Observability

**Key Metrics to Track:**
- Task completion rate
- Average task duration
- Source verification rejection rate
- Contradiction detection rate
- Review cycle count
- Human checkpoint frequency
- LLM token usage
- Error rate by agent type

**Logging:**
- All agent actions → Audit DB
- System errors → Application logs
- API requests → Access logs
- Performance metrics → Metrics service

### Cost Management

**LLM API Costs:**
- Planning: ~1K tokens
- Research (5 agents): ~10K tokens total
- Verification: ~5K tokens
- Contradiction Detection: ~3K tokens
- Synthesis: ~15K tokens
- Review: ~5K tokens
- Revision: ~10K tokens
- **Total per paper: ~50K tokens (~$1-2 per paper)**

**Optimization Strategies:**
- Cache source verifications (avoid re-checking same source)
- Batch LLM requests where possible
- Use cheaper models for low-risk tasks
- Implement token budgets per agent

---

## 8. Next Steps

### Immediate Priorities

1. **Implement Researcher Agent** (blocks all downstream work)
2. **Build Academic Search Tool** (required by researcher)
3. **Test end-to-end with mock LLMs** (validate workflow logic)
4. **Integrate real LLM API** (Anthropic Claude or OpenAI)

### Week 1 Goals

- [ ] Complete Researcher Agent implementation
- [ ] Integrate Google Scholar/PubMed search
- [ ] Test parallel research execution
- [ ] Document agent behavior

### Week 2 Goals

- [ ] Implement Source Verification Agent
- [ ] Build DOI lookup tool
- [ ] Test verification logic
- [ ] Measure rejection rates

### Week 3 Goals

- [ ] Implement Contradiction Detection Agent
- [ ] Test with known contradictory sources
- [ ] Refine contradiction categorization
- [ ] Build contradiction report format

### Week 4 Goals

- [ ] Implement Synthesis Agent
- [ ] Test paper generation quality
- [ ] Implement Peer Review Agent
- [ ] Test review-revision loop

### Month 2 Goals

- [ ] Complete all agents
- [ ] Build FastAPI server
- [ ] End-to-end testing
- [ ] Production deployment

---

## 9. Success Criteria

### System Quality Metrics

**Technical:**
- [ ] All agents log actions to audit trail
- [ ] Parallel execution works without race conditions
- [ ] Human checkpoints pause/resume correctly
- [ ] Failures are detected and logged
- [ ] Retry logic handles transient errors

**Research Quality:**
- [ ] Sources are verified (DOI checked)
- [ ] Contradictions are detected and acknowledged
- [ ] Papers cite sources accurately
- [ ] Citation formatting is correct
- [ ] Papers pass plagiarism detection

**User Experience:**
- [ ] Clear progress indicators
- [ ] Human checkpoints provide context
- [ ] Audit trail is queryable
- [ ] Papers are downloadable
- [ ] Errors are explained clearly

---

## 10. Resources & References

### Documentation
- `/docs` - Additional technical docs
- `README.md` - Architecture overview
- `SETUP.md` - This file

### Code Examples
- `demo_scenario.py` - Working demo
- `agents/research_planning_agent.py` - Example agent implementation
- `tests/` - Test examples

### External Resources
- [Anthropic Claude API Docs](https://docs.anthropic.com)
- [OpenAI API Docs](https://platform.openai.com/docs)
- [Google Scholar API](https://serpapi.com/google-scholar-api)
- [PubMed E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/)
- [CrossRef API](https://www.crossref.org/documentation/retrieve-metadata/)

---

**Next Action:** Run `python demo_scenario.py` to verify setup and see Phase 1 execution.