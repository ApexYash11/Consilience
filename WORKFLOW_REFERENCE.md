# Consilience Research Workflows Reference

## Overview

Two research modes optimized for different scale and complexity requirements:
- **Standard Mode**: Fast, cost-effective, 5 parallel researchers
- **Deep Mode**: Comprehensive, thorough, 10-15 recursive researchers with multi-round analysis

---

# ⚙️ STANDARD RESEARCH WORKFLOW

## Flow Diagram

```
START
  ↓
[1] PLANNER (Analyze topic → Generate 5-10 queries)
  ↓ (deterministic)
[2-6] RESEARCHERS × 5 in PARALLEL (Queries assigned round-robin)
  Distribution: N queries ∈ [5,10] assigned to 5 researchers
  Each researcher gets floor(N/5) queries, first (N mod 5) get +1 extra
  Examples: 5 queries → [1,1,1,1,1] | 7 queries → [2,1,1,2,1] | 10 queries → [2,2,2,2,2]
  ├─ Researcher 1: Queries [assigned round-robin]
  ├─ Researcher 2: Queries [assigned round-robin]
  ├─ Researcher 3: Queries [assigned round-robin]
  ├─ Researcher 4: Queries [assigned round-robin]
  └─ Researcher 5: Queries [assigned round-robin]
  ↓ (synchronization point)
[7] MERGE_RESEARCHERS (Deduplicate sources, sum tokens/costs)
  ↓ (deterministic)
[8] VERIFIER (Assess source credibility)
  ├─ Quality Score < 0.3 & !fallback_triggered → [9] RESEARCHER-RETRY
  └─ Quality Score ≥ 0.3 OR fallback_triggered → [10] DETECTOR
  ↓
[9] RESEARCHER-RETRY (Generate fallback queries, re-search)
  └─ Routes back to [8] VERIFIER
  ↓
[10] DETECTOR (Find contradictions between verified sources)
  ↓ (deterministic)
[11] SYNTHESIZER (Draft paper from sources)
  ├─ Confidence < 0.5 → [11B] SYNTHESIZER-REDO
  └─ Confidence ≥ 0.5 → [12] REVIEWER
  ↓
[11B] SYNTHESIZER-REDO (Re-draft with different approach)
  └─ Routes to [12] REVIEWER
  ↓
[12] REVIEWER (Fact-check draft, find issues)
  ├─ Issues found & attempt < 2 → [12B] PREPARE-REVISION
  └─ No issues OR attempt ≥ 2 → [13] FORMATTER
  ↓
[12B] PREPARE-REVISION (Increment attempt counter, reset flags)
  └─ Routes back to [11] SYNTHESIZER
  ↓
[13] FORMATTER (Final polish, format output)
  ↓
END
```

## Stage-by-Stage Breakdown

### [1] PLANNER
**Model**: DeepSeek R1-0528 (Free)  
**Speed**: ~5-10 seconds  
**Cost**: $0  
**Purpose**: Break topic into 5-10 specific, searchable queries  
**Input**: `topic`, `requirements`  
**Output**: `research_queries` (list of 5-10 strings)  
**Scale Notes**:
- Analysis is lightweight and free
- Scales well; no token overhead
- Use for topic understanding at any scale

### [2-6] RESEARCHERS × 5 (Parallel)
**Model**: Claude 3.5 Sonnet or GPT-4o  
**Speed**: ~20-40 seconds each (parallel)  
**Cost**: ~$0.10-0.30 per researcher × 5  
**Purpose**: Search web/database for relevant sources  
**Parallelization**: 5 agents run simultaneously
- Researcher 1: Queries 1-2 (finds sources A, B, C)
- Researcher 2: Queries 3-4 (finds sources D, E, F)
- ... and so on
**Output per researcher**: `sources` (list of Source objects)  
**Scale Notes**:
- Parallel execution reduces wall-clock time
- Each researcher is independent; no coordination overhead
- High throughput for broad research
- Sources may have duplicates (deduplicated later)

### [7] MERGE_RESEARCHERS
**Purpose**: Combine 5 researcher outputs into single deduplicated state  
**Logic**:
```
For each source across all researchers:
  - Deduplicate by URL (primary) → title (secondary) → id (fallback)
  - If no identifier: use anon-{memory_address} fallback
  - If duplicate found: log and skip
  
Sum costs: ∑ researcher.cost
Sum tokens: ∑ researcher.tokens_used
Combine errors: [error_list_1 + error_list_2 + ...]
```
**Output**: Single `ResearchState` with merged sources, aggregated metrics  
**Scale Notes**:
- Deduplication prevents source explosion
- Memory-address fallback uniqueness NOT stable across runs
- Scalability: O(n) where n = total sources; typically 50-200 sources

### [8] VERIFIER
**Model**: DeepSeek R1 Distill Qwen 7B (Free)  
**Speed**: ~10-20 seconds  
**Cost**: $0  
**Purpose**: Filter sources by credibility score (0-1)  
**Quality Score Thresholds**:
- < 0.3: Poor quality → triggers retry
- 0.3-0.7: Acceptable → proceed
- 0.7+: High quality
**Output**: 
- `verified_sources` (sources passing threshold)
- `verification_notes` (rejected source reasons)
- `source_quality_score` (0-1)
**Scale Notes**:
- Linear in source count
- Fast free model suitable for bulk filtering
- Typically rejects 20-40% of sources

### [9] RESEARCHER-RETRY (Conditional)
**Triggered when**: `source_quality_score < 0.3 && !fallback_triggered`  
**Model**: Same as original researchers (Claude/GPT-4o)  
**Purpose**: Generate fallback queries emphasizing underrepresented perspectives  
**Fallback Query Strategy**:
- Original: "climate change effects"
- Fallback: "climate change skeptic perspectives", "climate models accuracy criticism"
**Output**: New `research_queries` + re-run through researchers  
**Routes to**: VERIFIER (for re-validation)  
**Scale Notes**:
- Extra loop adds 30-60 seconds
- Only triggered ~20% of workflows
- Retry limit = 1 (prevents infinite loops)

### [10] DETECTOR
**Model**: Grok-2 or equivalent (fast, cheap)  
**Speed**: ~15-30 seconds  
**Cost**: ~$0.05-0.10  
**Purpose**: Find contradictions between verified sources  
**Algorithm**: Pairwise comparison
```
For each pair of sources (i, j) where i < j:
  Compare for contradictions
  Store contradiction object if found
  
Time complexity: O(n²) where n = verified sources
```
**Contradiction Object**:
```json
{
  "source_a_id": "...",
  "source_b_id": "...",
  "contradiction_summary": "Source A claims X, Source B claims ¬X",
  "severity": 0.0-1.0
}
```
**Scale Notes**:
- O(n²) complexity: 20 sources = 190 comparisons; 50 sources = 1,225 comparisons
- For large datasets (100+ sources): Consider clustering/sampling
- **WARNING**: Quadratic scaling = bottleneck at scale

### [11] SYNTHESIZER
**Model**: Claude 3.5 Sonnet (for reasoning + writing)  
**Speed**: ~30-60 seconds  
**Cost**: ~$0.20-0.40  
**Purpose**: Draft coherent paper combining verified sources  
**Algorithm**:
```
1. Create outline from sources (3-7 sections)
2. For each section:
   - Write 400-600 word section
   - Cite relevant sources
   - Track citations for final bibliography
3. Assemble into final draft
```
**Output**:
- `draft_paper` (Markdown formatted)
- `draft_outline` (section titles)
- `synthesis_confidence` (0-1, how coherent/supported is draft)
**Scale Notes**:
- Higher synthesis_confidence when sources align
- Contradictions reduce confidence
- Large source count (100+) may reduce coherence

### [11B] SYNTHESIZER-REDO (Conditional)
**Triggered when**: `synthesis_confidence < 0.5`  
**Approach**: Same synthesizer with different prompt emphasis  
- Original: "Create coherent narrative"
- Redo: "Address contradictions explicitly, flag uncertainties"
**Routes to**: REVIEWER  
**Scale Notes**:
- Triggered ~30-40% of workflows
- Additional 30-60 seconds cost

### [12] REVIEWER
**Model**: Claude 3.5 Sonnet  
**Speed**: ~20-40 seconds  
**Cost**: ~$0.15-0.25  
**Purpose**: Fact-check draft, find logical issues  
**Review Checklist**:
- Citations present for major claims?
- Contradictions acknowledged?
- Logical flow coherent?
- Factual accuracy against sources?
- Missing sections?
**Output**:
- `review_feedback` (list of issues)
- `revision_needed` (boolean)
- `issues_found` (list of issues)
**Scale Notes**:
- Single pass regardless of source count
- Processing time stable O(draft_length)

### [12B] PREPARE-REVISION (Conditional)
**Triggered when**: `revision_needed && current_attempt < 2`  
**Purpose**: Increment revision counter, reset flags for next cycle  
**Routes to**: SYNTHESIZER (loops back)  
**Max Revisions**: 2 (synthesis → review → synthesis → review → formatter)  
**Scale Notes**:
- Revision limit prevents infinite loops
- ~60-90 seconds per revision cycle

### [13] FORMATTER
**Model**: N/A (post-processing)  
**Speed**: ~2-5 seconds  
**Cost**: $0  
**Purpose**: Polish output, add metadata, finalize format  
**Output**:
- `final_paper` (publication-ready Markdown)
- `execution_metrics` (timing, token usage)
**Scale Notes**:
- Fast, deterministic post-processing

---

## Standard Workflow Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| **Total Time** | 2-4 minutes | Parallel researchers dominate |
| **Total Cost** | $0.30-0.80 | Mostly Claude/GPT calls |
| **Sources Found** | 50-200 | Depends on topic specificity |
| **Sources Verified** | 30-120 | ~50-60% pass credibility |
| **Final Tokens** | 200K-500K | Depends on draft size |
| **Max Revision Loops** | 2 | Prevents runaway synthesis |
| **Single Point of Failure** | DETECTOR (O(n²)) | Slow on 100+ sources |
| **Typical Use** | General research, fast turnaround | Good for blog posts, quick summaries |

---

# 🔬 DEEP RESEARCH WORKFLOW

## Flow Diagram

```
START
  ↓
[1] PLANNER (Analyze → Generate 5+ queries)
  ↓ (deterministic)
[2] DEEP-RESEARCHER (10-15 parallel sub-agents, 3 recursive rounds)
  │
  ├─ Round 1: 10 sub-agents (initial broad search)
  │  └─ Each searches 1-2 specific queries
  │
  ├─ Round 2: 5 sub-agents (gap analysis)
  │  └─ Follow-up on contradictions/missing angles
  │
  └─ Round 3: 3 specialized sub-agents (controversy resolution)
     └─ Deep dive on unresolved contradictions
  ↓ (synchronization)
[3] VERIFIER (Stricter but allows failures)
  ├─ Quality Score < 0.2 & rejection_count < 1 → [4] RESEARCHER-RETRY
  └─ Else → [5] DETECTOR
  ↓
[4] RESEARCHER-RETRY (Specialized follow-up search)
  └─ Routes back to [3] VERIFIER
  ↓
[5] DETECTOR (Deep contradiction analysis)
  ├─ Find contradictions
  ├─ Categorize severity
  └─ Flag for synthesis attention
  ↓ (deterministic)
[6] SYNTHESIZER (Comprehensive paper with cross-refs)
  ├─ Confidence < 0.4 → [6B] SYNTHESIZER-REDO
  └─ Confidence ≥ 0.4 → [7] REVIEWER
  ↓
[6B] SYNTHESIZER-REDO
  └─ Routes to [7] REVIEWER
  ↓
[7] REVIEWER (Multi-round fact-checking)
  ├─ Issues found & attempt < 3 → [7B] PREPARE-REVISION
  └─ No issues OR attempt ≥ 3 → [8] FORMATTER
  ↓
[7B] PREPARE-REVISION (Increment attempt up to 3)
  └─ Routes back to [6] SYNTHESIZER
  ↓
[8] FORMATTER (Final publication-quality output)
  ↓
END
```

## Stage-by-Stage Breakdown

### [1] PLANNER
**Same as Standard** (same model, cost, speed)

### [2] DEEP-RESEARCHER (Advanced Multi-Round)
**Model**: Claude 3.5 Sonnet (premium reasoning)  
**Speed**: ~60-120 seconds total (3 rounds of async agents)  
**Cost**: ~$0.50-1.50  
**Purpose**: Comprehensive research with recursive refinement  

**Round 1: Broad Search** (~30-40 sec)
- 10 parallel sub-agents
- Each searches 1-2 queries
- Captures diverse perspectives
- Output: 100-300 sources

**Round 2: Gap Analysis** (~20-30 sec)
- 5 parallel sub-agents
- Analyze contradictions from Round 1
- Search for missing viewpoints
- Queries like: "counterargument to X", "alternative explanation for Y"
- Output: +100-150 additional sources

**Round 3: Controversy Resolution** (~10-20 sec)
- 3 specialized sub-agents
- Deep-dive into unresolved contradictions
- Seek expert/academic sources
- Queries like: "academic consensus on X", "peer review of Y study"
- Output: +50-100 high-credibility sources

**Total Output**: 250-550 sources (vs. 50-200 in Standard)

**Scale Notes**:
- Multi-round approach compounding: each round builds on previous
- Persistent file-system context allows agents to understand workflow history
- Much higher throughput; scales to complex topics
- Cost-effective for comprehensive research (batch processing)

### [3] VERIFIER (Less Strict for Deep Research)
**Model**: Same as Standard (DeepSeek R1 Distill 7B)  
**Speed**: ~20-40 seconds (larger source pool)  
**Cost**: $0  
**Quality Threshold**: < 0.2 (vs. 0.3 in Standard)  
**Purpose**: Filter sources while allowing some failures  
**Output**: 
- `verified_sources`: 150-300 sources
- `source_quality_score`: typically 0.3-0.6
**Scale Notes**:
- Lower threshold designed to keep more sources
- Allows contradictory sources (useful for comprehensive analysis)
- Less strict because Deep research handles complexity

### [4] RESEARCHER-RETRY (Conditional)
**Triggered when**: `source_quality_score < 0.2 && rejection_count < 1`  
**Approach**: Same as Standard, but with emphasis on:
- Academic sources
- Peer-reviewed literature
- Expert commentary
**Routes to**: VERIFIER  
**Scale Notes**:
- Triggered <15% of workflows (higher initial quality)
- Specialization emphasis on academic/credible sources

### [5] DETECTOR (Deep Contradiction Analysis)
**Model**: Grok-2 or Claude  
**Speed**: ~40-60 seconds (larger dataset)  
**Cost**: ~$0.15-0.25  
**Purpose**: Comprehensive contradiction mapping  
**Algorithm**:
```
1. Compare all verified sources (pairwise)
2. For each contradiction, categorize:
   - Methodology disagreement
   - Data interpretation difference
   - Empirical contradiction
   - Framing/perspective difference
3. Severity score: 0.0 (minor framing) to 1.0 (direct factual conflict)
4. Track contradiction chains (A contradicts B, B contradicts C...)
```
**Output**: 
- `contradictions`: 20-100 contradiction objects
- `contradiction_analysis`: Categorized map
**Scale Notes**:
- **WARNING**: O(n²) complexity problematic on 300+ sources
- May take 2-3 minutes with deep dataset
- Consider sampling/clustering if performance critical

### [6] SYNTHESIZER (Comprehensive Synthesis)
**Model**: Claude 3.5 Sonnet  
**Speed**: ~60-90 seconds  
**Cost**: ~$0.30-0.50  
**Purpose**: Author comprehensive paper incorporating multiple perspectives  
**Algorithm**:
```
1. Create detailed outline (8-12 sections)
2. For each section:
   - Identify multiple viewpoints
   - Present evidence from different sources
   - Explicitly acknowledge contradictions
   - Draw nuanced conclusions
3. Add meta-sections:
   - "Open Questions" (unresolved contradictions)
   - "Research Gaps" (areas needing more sources)
   - "Confidence Assessment" (by claim)
4. Generate complete outline and full text
```
**Output**:
- `draft_paper`: 2,000-5,000 word comprehensive paper
- `draft_outline`: 8-12 sections
- `synthesis_confidence`: typically 0.4-0.8 (nuanced)
**Scale Notes**:
- Larger source pool → higher detail and nuance
- More contradictions handled explicitly
- Longer generation time due to complexity
- Confidence lower than Standard (expects contradiction)

### [6B] SYNTHESIZER-REDO
**Triggered when**: `synthesis_confidence < 0.4`  
**Approach**:
- Emphasize contrasting viewpoints
- Structure paper as "debate" rather than narrative
- Let contradictions guide section organization
**Routes to**: REVIEWER  
**Scale Notes**:
- Triggered ~25% of workflows (acceptable in deep research)

### [7] REVIEWER (Multi-Round Deep Fact-Check)
**Model**: Claude 3.5 Sonnet  
**Speed**: ~40-60 seconds per round  
**Cost**: ~$0.20-0.30 per round  
**Purpose**: Rigorous fact-checking across depth, accuracy, and structure  
**Review Depth**:
- All claims vs. sources (not sampling)
- Cross-source verification (does A contradict B?)
- Citation accuracy
- Logical coherence despite contradictions
- Missing perspectives
**Output**:
- `review_feedback`: detailed issue list
- `revision_needed`: boolean
- `issues_found`: 5-20 issues per round
**Scale Notes**:
- Fact-checking 3,000+ word paper takes time
- Comprehensive review often finds issues
- Triggers revisions ~60% of workflows

### [7B] PREPARE-REVISION
**Purpose**: Increment revision counter (max 3)  
**Routes to**: SYNTHESIZER  
**Max Revision Cycles**: 3
- Cycle 1: Synthesizer → Reviewer
- Cycle 2: Synthesizer → Reviewer (attempt 2)
- Cycle 3: Synthesizer → Reviewer (attempt 3)
- Then → Formatter regardless
**Scale Notes**:
- Each cycle +60-90 seconds
- 3 cycles = +3-4.5 minutes additional time
- Ensures quality but has hard limit

### [8] FORMATTER
**Same as Standard** (fast finalization)

---

## Deep Workflow Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| **Total Time** | 8-15 minutes | Multiple rounds + deeper review |
| **Total Cost** | $1.50-3.50 | More researchers + multi-round |
| **Sources Found (Round 1)** | 100-300 | Broad initial search |
| **Sources Found (Round 2)** | +100-150 | Gap analysis |
| **Sources Found (Round 3)** | +50-100 | Specialized search |
| **Total Sources** | 250-550 | 4-5× Standard |
| **Sources Verified** | 150-300 | ~55-60% pass credibility |
| **Contradictions Identified** | 20-100 | Deep contradiction mapping |
| **Final Tokens** | 800K-2M | Comprehensive coverage |
| **Max Revision Loops** | 3 | Thorough fact-checking |
| **Typical Use** | Academic research, policy papers, complex topics | Worth time/cost investment |

---

# 🎯 DECISION MATRIX: When to Use Each Mode

| Factor | Standard | Deep |
|--------|----------|------|
| **Time Budget** | <5 min | >8 min available |
| **Cost Budget** | <$1 | >$1.50 |
| **Source Variety Needed** | 50-150 | 250-550 |
| **Contradiction Tolerance** | Low | High (expected) |
| **Topic Complexity** | Simple/straightforward | Complex/controversial |
| **Use Cases** | Blog post, quick summary, FAQ | Academic paper, policy brief, whitepaper |
| **Contradiction Handling** | Avoid/minimize | Embrace/analyze |
| **Deadline** | Today | Next few days |

---

# ⚠️ KNOWN BOTTLENECKS & SCALING ISSUES

## Standard Workflow

### Issue 1: DETECTOR's O(n²) Complexity
**Problem**: Contradiction detection scales quadratically
- 50 sources = 1,225 comparisons
- 100 sources = 4,950 comparisons  
- 150 sources = 11,175 comparisons
```
Time = 20-30 seconds for 50 sources
Time = 2-3 minutes for 100 sources  ⚠️
```
**Fix Options**:
1. Parallel batching: Compare sources in parallel chunks
2. Clustering: Group similar sources, compare cluster reps
3. Sampling: Random sample of sources for contradiction detection
4. Threshold: Skip contradictory analysis if >100 sources

### Issue 2: Concurrent State Updates
**Problem**: LangGraph's `LastValue` channel can't merge multiple concurrent writes
**Current Status**: Using `Annotated[List[str], reducer_func]` for `errors` field
**Symptoms**: `InvalidUpdateError: Can receive only one value per step`
**Fix**: Ensure fields that receive concurrent updates have Annotated reducers

### Issue 3: Arbitrary Fallback Identifiers
**Problem**: `anon-{id(source)}` uses memory address (not stable)
**Impact**: Same source appears different across workflow runs
**Fix**: Hash source content instead: `hashlib.md5(source_content).hexdigest()`

---

## Deep Workflow

### Issue 1: Exponential Time Growth
**Problem**: 3 rounds × detection = very slow
```
Round 1: 30-40 sec
Round 2: 20-30 sec
Round 3: 10-20 sec
DETECTOR: 1-2 minutes (on 300+ sources)
Total detection time can exceed synthesis time
```
**Fix**: Parallel detection via source clustering

### Issue 2: Token Budget Explosion
**Problem**: Multi-round deep research consumes 800K-2M tokens
**Cost Impact**: 4-6× Standard mode
**Symptoms**: Budget-heavy for continuous research
**Fix**: Memoization of round results, cache contradictions

### Issue 3: Metadata Persistence Overhead
**Problem**: File system writes after each round
**Impact**: I/O bottleneck on slow storage
**Fix**: Batch metadata writes; async I/O

---

# 📊 EXPECTED COSTS & TIMES (Approximate)

## Standard Research (~$0.50-0.80, ~2-3 min)
```
Planner:             $0.00  0-5 sec     ✓ Free
Researchers (5x):    $0.35  20-30 sec   ✓ Parallel
Merge:               $0.00  1 sec       ✓ Instant
Verifier:            $0.00  10 sec      ✓ Free
Detector:            $0.05  20 sec      ⚠ O(n²)
Synthesizer:         $0.25  40 sec      ✓ Standard
Reviewer:            $0.15  30 sec      ✓ Single pass
Formatter:           $0.00  2 sec       ✓ Instant
────────────────────────────────────────
TOTAL:               $0.80  125-180 sec (2-3 min)
```

## Deep Research (~$1.50-3.50, ~8-15 min)
```
Planner:              $0.00    0-5 sec      ✓ Free
Deep-Researcher:      $1.00    60-120 sec   ✓ 3 rounds × 10-15 agents
Verifier:             $0.00    20-40 sec    ✓ Free
Detector:             $0.20    60-120 sec   ⚠⚠ O(n²) on 300+ sources
Synthesizer (all):    $0.50    120-150 sec  ✓ Comprehensive
Reviewer x3:          $0.80    180-240 sec  ✓ Multi-round
Formatter:            $0.00    2 sec        ✓ Instant
────────────────────────────────────────
TOTAL:                $2.50    500-700 sec (8-12 min)
```

---

# 🔧 ARCHITECTURE RECOMMENDATIONS FOR SCALE

## Recommendation 1: Decouple Detector from Research Loop
**Issue**: DETECTOR's O(n²) blocks synthesis
**Solution**:
```
Current: VERIFIER → DETECTOR → SYNTHESIZER (blocked)
Proposed: VERIFIER → SYNTHESIZER (async)
          DETECTOR runs in background, results used in next revision
```

## Recommendation 2: Parallel Contradiction Detection
**Implementation**:
```python
# Instead of pairwise comparison (n²)
# Batch compare: Group sources by topic cluster
# Compare inter-cluster pairs only (O(n log n))

clusters = cluster_sources_by_topic(sources)  # K clusters
for i, cluster_a in enumerate(clusters):
    for cluster_b in clusters[i+1:]:
        compare_clusters(cluster_a, cluster_b)  # Much fewer comparisons
```

## Recommendation 3: Source Deduplication Strategy
**Current**: URL-based dedup (vulnerable to redirects, archives)
**Better**:
```python
# Multi-factor dedup check:
# 1. Exact URL match
# 2. Title similarity (>0.9)
# 3. Author + Year + Title (for academic papers)
# 4. Content hash (first 1K chars MD5)
```

## Recommendation 4: Caching & Memoization
**For Repeated Topics**:
```
Cache keys:
- Topic hash
- Query set hash
- Model version

Cache contents:
- Verified sources (by topic)
- Contradictions (by source pair)
- Draft outline (by topic + sources)

TTL: 1-7 days
```

## Recommendation 5: Circuit Breaker for Detector
**Problem**: DETECTOR hangs on very large datasets (300+ sources)
**Solution**:
```python
if len(verified_sources) > 250:
    # Use sampling instead of exhaustive comparison
    sample = random.sample(verified_sources, 250)
    contradictions = detect_contradictions(sample)
    state.contradictions = contradictions
    state.notes += f"(Based on {len(sample)} sampled sources)"
else:
    contradictions = detect_contradictions(verified_sources)
```

---

# 📝 SUMMARY TABLE

```
┌──────────────────┬─────────────────┬──────────────────┐
│ Characteristic   │ Standard        │ Deep             │
├──────────────────┼─────────────────┼──────────────────┤
│ Researchers      │ 5 parallel      │ 10-15 recursive  │
│ Rounds           │ 1               │ 3                │
│ Total Sources    │ 50-200          │ 250-550          │
│ Time             │ 2-3 min         │ 8-15 min         │
│ Cost             │ $0.50-0.80      │ $1.50-3.50       │
│ Contradictions   │ ~5-10 found     │ ~20-100 found    │
│ Final Paper      │ 800-1500 words  │ 2000-5000 words  │
│ Use Case         │ Quick research  │ Comprehensive    │
│ Quality Focus    │ Speed+Cost      │ Depth+Accuracy   │
│ Main Bottleneck  │ DETECTOR O(n²)  │ DETECTOR O(n²)   │
│ Revision Loops   │ Max 2           │ Max 3            │
└──────────────────┴─────────────────┴──────────────────┘
```

---

# 🚀 READY FOR LARGE-SCALE FIXES

Now specify which workflow areas need fixing:
1. **Performance Bottlenecks** - DETECTOR O(n²), parallel processing
2. **Concurrency Issues** - LangGraph state merge, Annotated reducers
3. **Scalability Limits** - Source pooling, batch processing, caching
4. **Cost Optimization** - Model selection, sampling strategies
5. **Error Handling** - Retry logic, circuit breakers, fallbacks
6. **Monitoring** - Observability, metrics tracking, logging

Ask for fixes in specific areas! 🎯
