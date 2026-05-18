# ReqLens Presenter Notes

These notes are for `FINAL UPDATING sriman.pdf`.

Important rule for presentation: **trust the code and `output.md` over the PDF when numbers differ.**

## Corrections To Remember


| Topic                | PDF / old wording                              | Correct presenter wording                                                                                                |
| -------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Best config          | Few-shot dynamic + full = 87%                  | Current `output.md` winner is `few_shot_static / full`: `95.9%` quality, `100.0%` traceability, `75.0%` critique accept. |
| Traceability ANOVA   | Strategy effect on traceability is significant | Current `output.md`: strategy traceability `p = 1.0000`, not significant.                                                |
| Significant results  | General `p < .05` strategy claim               | Safe claims: strict coverage `p = 0.0014`; mapping confidence `p = 0.0001`; FAISS evidence `p = 0.0372`.                 |
| Single-pass baseline | 80% vs ~45%                                    | Treat as fixture/demo evidence unless a direct baseline row is rerun and appears in `output.md`.                         |
| Test count           | 85 tests                                       | Current source has about 135 app test functions, but pytest could not be rerun in this environment.                      |


## Core Explanation

ReqLens is not just an AI test generator. It is a **requirement-traced test generation pipeline**.

The key idea:

```text
requirements + code -> six-stage pipeline -> tests + traceability matrix + metrics
```

The six stages:

```text
Parse -> Analyze -> Map -> Generate -> Critique -> Trace
```

What happens after a test is generated:

```text
GeneratedTest -> CritiqueScore -> TraceabilityRow -> compute_metrics() -> rank + ANOVA
```

Use this 5-line test example:

```python
def test_create_todo_adds_item():
    store = TodoStore()
    todo = store.create("Buy milk")
    assert todo.title == "Buy milk"
    assert todo in store.list_all()
```

How it is evaluated:

1. `GenerateOutput` stores the test with requirement id, file path, code, target symbol, and rationale.
2. `CritiqueOutput` scores relevance, completeness, and correctness from 1 to 5.
3. `TraceOutput` links the test file back to the requirement in a traceability matrix.
4. `compute_metrics()` converts the trace matrix and critique scores into percentages.
5. Sweep ranking and ANOVA compare configurations.

## Slide 01 — Title

### What To Say

Good morning. Our project is ReqLens, a requirement-traced test generation system.

The main problem is not only generating tests with AI. The harder problem is proving which requirement each test verifies.

ReqLens solves this with a six-stage multi-agent pipeline and hybrid retrieval.

### Technical Meaning

ReqLens means “requirements lens.” It views generated tests through requirement coverage.

The system has:

- Django backend
- Next.js frontend
- Agent Client Protocol layer
- Pydantic stage contracts
- Sweep evaluation

### Professor Questions

**Q: What is your main contribution?**  
A: A structured, typed, evaluable AI pipeline that produces tests and a traceability matrix.

**Q: Why not just use Copilot or ChatGPT?**  
A: Single-pass tools may generate tests, but they usually do not preserve requirement-to-test evidence.

## Slide 02 — Abstract

### What To Say

ReqLens parses requirements, analyzes code, maps requirements to implementation, generates tests, critiques those tests, and builds a final traceability matrix.

Each stage has a strict Pydantic contract, so invalid agent output is caught before it affects later stages.

Correction: if using current `output.md`, say the latest completed sweep rows reached `100%` traceability, and the rank-one configuration was `few_shot_static / full`.

### Technical Meaning

Hybrid retrieval means FAISS semantic retrieval plus BM25 keyword retrieval.

ACP means Agent Client Protocol, which lets the backend call different agents through a common interface.

The PDF’s old `87%` best-config claim is stale compared with current `output.md`.

### Professor Questions

**Q: What does traceability mean?**  
A: For each requirement, the system can identify which test file verifies it.

**Q: What is the source of truth?**  
A: The code and `output.md`. The PDF is a presentation artifact and needs a few numeric corrections.

## Slide 03 — Motivation

### What To Say

In real projects, teams may have hundreds of requirements and thousands of tests.

When someone asks “which tests verify this requirement?”, manual traceability is slow and often stale.

ReqLens makes traceability a first-class deliverable.

### Technical Meaning

Existing AI tools can generate tests, but often do not create a durable traceability matrix.

Manual matrices become outdated as code and tests change.

ReqLens stores structured requirements, code symbols, mappings, generated tests, critique scores, and final matrix rows.

### Professor Questions

**Q: Who would use this?**  
A: QA teams, regulated software teams, and developers who need evidence that requirements are tested.

**Q: Is this only for compliance?**  
A: No. It also helps engineering teams find coverage gaps.

## Slide 04 — Background

### What To Say

Each technology has a specific role.

ACP gives an agent-agnostic execution layer. Pydantic gives strict contracts. FAISS and BM25 support retrieval. SciPy supports statistical evaluation.

### Technical Meaning

FAISS finds semantically similar code.

BM25 finds exact keyword and identifier matches.

Pydantic strict mode prevents wrong shapes, wrong types, and extra fields from silently flowing downstream.

SciPy runs ANOVA and pairwise comparisons.

### Professor Questions

**Q: Why use both FAISS and BM25?**  
A: FAISS catches meaning; BM25 catches exact terms. Together they are more robust.

**Q: What happens if an agent returns bad JSON?**  
A: The stage extraction and Pydantic validation catch it. The orchestrator can retry or fail the stage.

## Slide 05 — System Architecture

### What To Say

The architecture has three layers:

```text
Frontend -> Backend -> AI agent layer
```

The frontend manages projects, runs, sweeps, and live status.

The backend stores data and orchestrates the pipeline.

The AI layer performs stage-specific work through ACP.

### Technical Meaning

Frontend: Next.js and React.

Backend: Django 5, REST API, SQLite.

Live run status uses Server-Sent Events.

Pipeline execution happens in background tasks.

### Professor Questions

**Q: Why use SSE?**  
A: Runs can take time, so SSE streams progress, stage completion, reasoning, and permission events live to the UI.

**Q: Why not Celery?**  
A: For project scope, background threads were enough. The code also has stale-task reaping for recovery.

## Slide 06 — Six-Stage Pipeline

### What To Say

This is the core of ReqLens.

Each stage has one responsibility:

```text
Parse: requirements -> structured Requirement[]
Analyze: code -> CodeSymbol[]
Map: requirements -> code symbols
Generate: mappings -> tests
Critique: tests -> quality decisions
Trace: all outputs -> final matrix
```

The advantage is decomposition. Smaller stages are easier to validate, retry, and evaluate.

### Technical Meaning

Each later output nests earlier outputs:

```text
TraceOutput contains CritiqueOutput
CritiqueOutput contains GenerateOutput
GenerateOutput contains MapOutput
MapOutput contains AnalyzeOutput
AnalyzeOutput contains ParseOutput
```

This preserves provenance.

### Professor Questions

**Q: Why is critique separate from generation?**  
A: Generation creates candidate tests. Critique acts as a quality gate: accept, revise, or reject.

**Q: What if map misses a requirement?**  
A: The orchestrator validates that map includes one mapping per parsed requirement.

## Slide 07 — Hybrid Retrieval

### What To Say

Mapping requirements to code is hard because the implementation may be buried in the codebase.

ReqLens builds a retrieval index over Python files.

It combines:

```text
FAISS: 60%
BM25: 40%
alpha = 0.6
```

The map stage uses retrieval hints in local, module, and full context modes.

### Technical Meaning

FAISS handles semantic similarity.

BM25 handles exact terms.

The map stage uses `DEFAULT_TOP_K = 5` retrieval hits.

Minimal mode skips retrieval to be a cheaper baseline.

### Professor Questions

**Q: Is Precision@3 formally computed?**  
A: The retrieval tests assert that correct benchmark files appear within top-k results. The PDF’s Precision@3 claim should be phrased as retrieval-test evidence unless expanded.

**Q: Why alpha 0.6?**  
A: It slightly favors semantic retrieval while keeping keyword matching important.

## Slide 08 — Prompt Strategies And Context Modes

### What To Say

We compare four prompt strategies and four context modes.

Prompt strategies:

```text
zero_shot
chain_of_thought
few_shot_static
few_shot_dynamic
```

Context modes:

```text
minimal
local
module
full
```

### Technical Meaning

Prompt strategy changes how the agent is asked.

Context mode changes how much code context is included.

Current `output.md` does not show significant traceability differences by context because completed rows all reached `100%` traceability.

### Professor Questions

**Q: What is few-shot static?**  
A: Hardcoded examples for stages/projects.

**Q: What is few-shot dynamic?**  
A: Project-specific examples retrieved dynamically. Current static example code only applies examples for `few_shot_static`.

## Slide 09 — Evaluation Setup

### What To Say

Evaluation has two parts:

```text
Tests validate the system machinery.
Sweeps compare configurations.
```

The tests cover contracts, retrieval, metrics, statistics, prompts, runtime behavior, APIs, and agent registry behavior.

The current `output.md` sweep is for `todo-api`.

### Technical Meaning

Important correction: the PDF says `85` tests, but current source has about `135` app test functions.

Generated test execution is not yet integrated into `test_pass_rate`; in `metrics.py`, `test_pass_rate` and `line_coverage` are placeholders.

### Professor Questions

**Q: What exactly is evaluated?**  
A: Deterministic system correctness plus agent-output quality metrics from completed runs.

**Q: Are generated tests executed?**  
A: Not in the current metrics. The system scores generated artifacts through traceability, mapping, critique, and stage success.

## Slide 10 — Research Questions

### What To Say

The research questions separate four concerns:

```text
RQ1: Does staging help?
RQ2: Which prompt strategy works best?
RQ3: Does more context improve quality?
RQ4: Does retrieval surface correct code?
```

When answering, distinguish fixture evidence, source tests, and current `output.md` evidence.

### Professor Questions

**Q: Which result is strongest?**  
A: The architecture, contracts, retrieval tests, and deterministic metrics validation are strongest. Sweep conclusions need current-output wording.

**Q: Which result should we trust?**  
A: Trust code and `output.md` first.

## Slide 11 — RQ1 Pipeline Vs Single-Pass

### What To Say

The concept is correct: staged generation gives more structure than single-pass generation.

However, present the exact numbers carefully.

The `80%` traceability comes from a realistic unit-test fixture:

```text
5 requirements
3 covered
1 partial
1 uncovered
traceability = (3 + 1) / 5 = 80%
strict coverage = 3 / 5 = 60%
```

Current `output.md` for `todo-api` shows `4` requirements and `4` generated tests, with `100%` traceability for completed rows.

### Professor Questions

**Q: How is 80% calculated?**  
A: Covered or partial rows divided by total requirements: `4/5`.

**Q: Why does partial count?**  
A: `traceability_score` counts covered + partial; `strict_coverage_score` only counts fully covered.

## Slide 12 — Strategy And Context Comparison

### What To Say

This slide compares prompt strategies and context modes, but current output differs from the older PDF narrative.

Current winner:

```text
few_shot_static / full
quality = 95.9%
traceability = 100.0%
strict coverage = 100.0%
critique accept = 75.0%
```

### Technical Meaning

All completed configurations in `output.md` have `100%` traceability.

Differences come from quality score, strict coverage, mapping confidence, FAISS evidence, and latency.

Do not claim token-cost comparisons from current `output.md` because tokens are `0`.

### Professor Questions

**Q: Why did static beat dynamic?**  
A: In this saved sweep, static/full had slightly higher quality and strong strict coverage/evidence metrics.

**Q: Does full context always win?**  
A: Not from current `output.md`. Context-level traceability was not significant.

## Slide 13 — Retrieval Precision

### On-The-Fly Card

**One idea:** Retrieval helps the Map stage find the right code before the agent generates tests.

**Say this in 20 seconds:**

```text
This slide shows why retrieval matters. Requirements are written in human language, but code uses functions, classes, and identifiers. ReqLens uses hybrid retrieval to bridge that gap. FAISS finds semantic matches, BM25 finds exact keyword matches, and the Map stage uses those snippets as evidence before linking requirements to code.
```

**Numbers to remember:**

```text
FAISS weight = 60%
BM25 weight = 40%
alpha = 0.6
Map stage top-k hints = 5
```

**Simple flow:**

```text
Requirement text
  -> FAISS semantic search
  -> BM25 keyword search
  -> fused score
  -> top code snippets
  -> Map stage chooses code symbol
```

**Safe wording for PDF result:**

```text
For the tested benchmark queries, retrieval surfaced the correct implementation files in the top results.
```

Do **not** say it proves industrial-scale retrieval. Say it is benchmark evidence.

### If Professor Asks

**Q: What is Precision@3?**  
A: It checks whether the correct file appears in the top 3 retrieved results.

**Q: Why use both FAISS and BM25?**  
A: FAISS catches meaning. BM25 catches exact code words. They cover each other’s weaknesses.

**Q: Where does retrieval happen?**  
A: In the Map stage, before test generation.

**Q: Does retrieval evaluate tests?**  
A: No. Retrieval supports mapping. Evaluation happens later through critique, trace, metrics, ranking, and ANOVA.

**One-sentence answer:**  
Retrieval narrows the search space so the agent maps requirements to the right implementation code instead of guessing.

## Slide 14 — Statistical Analysis

### On-The-Fly Card

**One idea:** ANOVA tells us whether different strategies really performed differently, or whether differences are just noise.

**Say this in 20 seconds:**

```text
ANOVA compares the average scores of different prompt strategies and context modes. If p is below 0.05, we treat the difference as statistically meaningful. In the current output, traceability was not significant because every completed configuration reached 100% traceability. The real differences show up in stricter metrics like strict coverage and mapping confidence.
```

**Must-say correction:**

```text
Traceability was NOT significantly different in output.md.
strategy traceability p = 1.0000
context traceability p = 1.0000
```

**Safe significant results:**

```text
strict coverage: p = 0.0014, eta2 = 0.744
mapping confidence: p = 0.0001, eta2 = 0.837
FAISS evidence per mapping: p = 0.0372, eta2 = 0.523
```

**Simple meaning:**

```text
p-value = is the difference likely real?
eta2 = how big is the effect?
```

**What to avoid:**

```text
Do not say: strategy significantly improved traceability.
Say: traceability saturated, so strict coverage and mapping quality separate configurations better.
```

### If Professor Asks

**Q: What is ANOVA?**  
A: It tests whether multiple groups have meaningfully different average results.

**Q: Why is p = 1.0000 for traceability?**  
A: Because all completed configurations had the same traceability: 100%.

**Q: Why is strict coverage significant but traceability is not?**  
A: Traceability counts covered plus partial. Strict coverage only counts fully covered requirements, so it is harder and more discriminating.

**Q: What does eta2 mean?**  
A: It tells how much of the variation is explained by the factor, like strategy.

**One-sentence answer:**  
ANOVA shows traceability did not separate strategies, but strict coverage and mapping quality did.

## Slide 15 — Test Suite Summary

### On-The-Fly Card

**One idea:** Tests validate the system machinery; sweeps evaluate generated outputs.

**Say this in 20 seconds:**

```text
This slide is about engineering validation. The test suite checks that contracts, retrieval, metrics, statistics, prompts, APIs, runtime behavior, and agent registry logic work correctly. That is different from sweep evaluation, which compares generated outputs across prompt and context configurations.
```

**Quick distinction:**

```text
Testing asks: does the system compute correctly?
Evaluation asks: which configuration performs better?
```

**Test areas to name:**

```text
contracts
retrieval
metrics
statistics
prompts/context modes
ACP registry
API endpoints
runtime hardening
```

**Important caveat:**

```text
test_pass_rate = placeholder
line_coverage = placeholder
Generated tests are not yet executed inside compute_metrics().
```

**Correct test count wording:**

```text
The PDF's 85-test count is stale. Current source has about 135 app test functions, but I would rerun in a clean environment before claiming an exact pass count.
```

### If Professor Asks

**Q: Do tests prove generated tests pass?**  
A: Not yet. They validate the pipeline and metric logic. Generated test execution is future work.

**Q: Why are deterministic tests important in an AI project?**  
A: AI output varies, so deterministic tests protect the infrastructure around it: schemas, scoring, retrieval, retries, and statistics.

**Q: What do contract tests prevent?**  
A: Bad agent JSON or incomplete outputs from silently entering later stages.

**Q: What does runtime hardening test?**  
A: Retries, cancellation, permission flow, sweep concurrency, and stale-task recovery.

**One-sentence answer:**  
The tests prove ReqLens handles AI outputs safely and computes evaluation metrics correctly.

## Slide 16 — Related Work

### On-The-Fly Card

**One idea:** ReqLens combines ideas that prior work usually handles separately.

**Say this in 20 seconds:**

```text
Related work falls into three groups: traditional automated test generation, LLM-based test generation, and requirements traceability. ReqLens sits between them. It uses AI to generate tests, but also keeps requirement links and evaluates configurations through a structured pipeline.
```

**Three buckets:**

```text
Search-based generation: EvoSuite, Randoop, Pynguin
LLM test generation: ChatUniTest, TestPilot, Codex-style tools
Traceability: ReqTracer-style systems
```

**Your difference:**

```text
They often generate tests OR trace artifacts.
ReqLens generates tests AND traces them back to requirements.
```

**Strong sentence:**

```text
ReqLens is not replacing test generators; it adds traceability and evaluation structure around AI-generated tests.
```

### If Professor Asks

**Q: Is ReqLens better than these tools?**  
A: We have not proven that broadly. The contribution is a different architecture: requirement-traced, multi-stage generation.

**Q: How is it different from ChatUniTest?**  
A: ChatUniTest focuses on LLM unit test generation. ReqLens adds parse, map, critique, trace, and a final traceability matrix.

**Q: How is it different from ReqTracer?**  
A: ReqTracer-style tools trace artifacts. ReqLens traces and generates tests in one pipeline.

**Q: Could ReqLens use Pynguin?**  
A: Yes. Pynguin could become a future baseline or backend for generation.

**One-sentence answer:**  
ReqLens combines requirement tracing, AI test generation, critique, and statistical evaluation in one workflow.

## Slide 17 — Limitations

### On-The-Fly Card

**One idea:** Be honest: this is a strong prototype, not a final industrial benchmark.

**Say this in 20 seconds:**

```text
The main limitations are benchmark size, partial sweep evidence, and artifact-based evaluation. Current benchmarks are small, one sweep has 15 reliable rows out of 16, and generated tests are not yet executed for pass rate or coverage. So the architecture is strong, but the next step is larger execution-backed evaluation.
```

**Limitations to list:**

```text
Small benchmark projects
Mostly Python examples
15/16 reliable sweep rows, not 16/16
Some PDF numbers are fixture/older evidence
Generated tests not yet executed in metrics
Coverage not yet integrated
Live agents can be nondeterministic
```

**Say this confidently:**

```text
These limitations define future work; they do not invalidate the architecture.
```

**Best future work:**

```text
1. Rerun clean full sweep with direct baseline.
2. Execute generated tests.
3. Add pass rate and line coverage.
4. Scale to larger projects.
5. Add more languages.
6. Compare multiple agents.
```

### If Professor Asks

**Q: Does 100% traceability mean tests are perfect?**  
A: No. It means every requirement has a linked test row. Passing tests and coverage are separate future metrics.

**Q: Why only 15/16 reliable rows?**  
A: One run failed, so the app stored partial metrics from successful runs.

**Q: Biggest threat to validity?**  
A: Small benchmarks and artifact-based evaluation instead of executed-test evaluation.

**Q: Is it production-ready?**  
A: It is a research prototype with validated architecture, but it needs larger benchmarks and execution-backed metrics.

**One-sentence answer:**  
The biggest limitation is that current evaluation proves traceability, not yet real executed test pass rate or coverage.

## Slide 18 — Conclusion

### On-The-Fly Card

**One idea:** ReqLens generates tests plus evidence.

**Say this in 20 seconds:**

```text
The main takeaway is that ReqLens turns AI test generation into an auditable process. Instead of stopping at a generated test file, it records the requirement, code symbol, generated test, critique decision, trace matrix row, and final evaluation metrics.
```

**Correct current result:**

```text
15/16 reliable metric rows
winner = few_shot_static / full
quality = 95.9%
traceability = 100.0%
critique accept = 75.0%
```

**Five findings to say safely:**

```text
1. Decomposition makes the process auditable.
2. Pydantic contracts make outputs checkable.
3. Hybrid retrieval supports mapping.
4. Critique + trace turn tests into evidence.
5. Sweeps make configurations measurable.
```

**Avoid old claims:**

```text
Do not say: dynamic/full was best at 87%.
Do not say: strategy significantly improved traceability.
Do not say: 85 tests passed from the current source.
```

### If Professor Asks

**Q: Final takeaway?**  
A: ReqLens generates tests and evidence, not just tests.

**Q: What result are you most confident in?**  
A: The architecture and deterministic validation, plus the corrected current output.md summary.

**Q: What is the biggest engineering lesson?**  
A: Break AI workflows into typed, validated stages instead of trusting one huge prompt.

**Q: What would make it publishable?**  
A: Larger benchmarks, generated test execution, coverage, direct baseline, and multi-agent replication.

**Final sentence:**  
ReqLens is valuable because every generated test can be connected back to the requirement it is supposed to prove.

## Slide 19 — References

### On-The-Fly Card

**One idea:** References show ReqLens combines three research areas.

**Say this in 20 seconds:**

```text
The references show the background for this work: search-based test generation, LLM-based test generation, and requirements traceability. ReqLens combines these directions by generating tests and preserving requirement links in the same pipeline.
```

**Use references like this:**

```text
EvoSuite/Randoop/Pynguin -> automated test generation
ChatUniTest/TestPilot -> LLM test generation
ReqTracer -> requirements traceability
```

**Safe claim:**

```text
The references position the project. We did not run a full head-to-head benchmark against every tool.
```

### If Professor Asks

**Q: Which reference is closest?**  
A: ChatUniTest/TestPilot are close for LLM test generation; ReqTracer is close for traceability. ReqLens combines both.

**Q: Why cite older tools?**  
A: They are the historical baseline for automated test generation.

**Q: Where does this fit academically?**  
A: At the intersection of requirements traceability, automated testing, and agentic software engineering.

**Q: Most important future baseline?**  
A: A direct single-pass LLM baseline and a conventional Python generator like Pynguin.

**One-sentence answer:**  
Prior work gives the pieces; ReqLens combines them into one requirement-traced generation pipeline.

## Slide 20 — Thank You

### On-The-Fly Card

**One idea:** End simple and be ready for corrected-number questions.

**Say this in 15 seconds:**

```text
Thank you. I’m happy to answer questions about the six-stage pipeline, retrieval, evaluation metrics, statistical results, or the corrected output.md numbers.
```

**If asked what you built:**

```text
We built a full-stack prototype that takes requirements and code, runs a six-stage agent pipeline, generates tests, critiques them, traces them back to requirements, and evaluates configurations using stored metrics and ANOVA.
```

**If asked for corrected numbers:**

```text
15/16 reliable rows
winner = few_shot_static / full
quality = 95.9%
traceability = 100.0%
critique accept = 75.0%
```

**If asked what was wrong in the PDF:**

```text
The PDF has a few stale result claims. Code and output.md are the source of truth, so I would update the result slide to say traceability saturated and strict coverage/mapping quality were the significant differentiators.
```

**If asked the biggest limitation:**

```text
Current evaluation proves traceability and artifact quality, but generated test execution and coverage should be added next.
```

**Last sentence to end with:**

```text
ReqLens matters because it makes AI-generated tests auditable: each test is connected back to the requirement it is supposed to prove.
```

