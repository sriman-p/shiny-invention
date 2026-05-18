
Thumbnails

Page
20
20 / 20





Fit Page






R e q L e n s

S L I D E 1 5 · V A L I D A T I O N 

ReqLens · IS 698 · May 2026 

15 / 19

Test Suite Summary

85

T E S T S

100%

P A S S R A T E

23.8s

E X E C U T I O N

7

M O D U L E S

M O D U L E 

T E S T S 

W H A T I T V A L I D A T E S

Contracts (Pydantic) 

17 

Schema enforcement, nesting, serialization, rejection of bad data.

Retrieval (real benchmarks) 

17 

BM25 precision on 3 codebases, filtering, edge cases.

Evaluation (metrics & stats) 

14 

Traceability scoring, accept rate, ANOVA, t-tests.

Context & Prompts 

15 

4-mode hierarchy, 24 template completeness, fallback behaviour.

ACP Registry 

10 

7 agents registered, specs correct, error handling.

API Integration 

4 

REST endpoints, project CRUD, filesystem validation.

Django Models 

8 

Model creation, relationships, ordering.

All 85 tests pass without external API access; ACP-dependent stages are mocked using deterministic fixtures.

R e q L e n s

S L I D E 1 6 · R E L A T E D W O R K 

ReqLens · IS 698 · May 2026 

16 / 19

Positioning Against Prior Art

# 

W O R K 

A P P R O A C H 

D I F F E R E N C E F R O M R E Q L E N S

1 

EvoSuite (Fraser & Arcuri, 2011) 

Search-based test gen 

No requirement awareness, no traceability.

2 

Randoop (Pacheco & Ernst, 2007) 

Random testing for Java 

No requirement mapping.

3 

Pynguin (Lukasczyk et al., 2022) 

Coverage-driven Python gen 

Coverage-driven, not requirement-driven.

4 

ChatUniTest (Chen et al., 2023) 

LLM unit-test gen 

Single-pass; no multi-stage pipeline.

5 

CodaMosa (Lemieux et al., 2023) 

LLM + search-based hybrid 

Augments search-based with LLM; no reqs.

6 

TestPilot (Schaefer et al., 2023) 

LLM JS test gen 

Single prompt; no traceability matrix.

7 

Codex (Chen et al., 2021) 

Code generation 

General-purpose; not test-focused.

8 

TOGA (Dinella et al., 2022) 

Test-oracle generation 

Oracles only; not full test suites.

9 

A3Test (Alagarsamy et al., 2023) 

Assertion generation 

Assertion-level only; no req tracing.

10 

ReqTracer (Guo et al., 2017) 

Requirements traceability 

Traces existing code; no test gen.

11 

TCGM (Li et al., 2023) 

Model-based test gen 

Requires formal specifications.

12 

AgentCoder (Huang et al., 2024) 

Multi-agent code gen 

Code gen, not test gen with traceability.

K E Y D I F F E R E N T I A T O R ReqLens uniquely combines requirement-driven generation, multi-stage pipeline with critique, traceability matrix as primary deliverable, and systematic 
strategy evaluation.

R e q L e n s

S L I D E 1 7 · D I S C U S S I O N 

ReqLens · IS 698 · May 2026 

17 / 19

Limitations & Threats to Validity

I N T E R N A L V A L I D I T Y

Benchmark projects are small (5, 3, 4 requirements) — results may not 
generalise to large codebases.

Sweep data partially simulated; full ACP runs require live API keys and 
reproducibility-controlled environments.

E X T E R N A L V A L I D I T Y

Only Python projects tested — pipeline architecture is language-agnostic, 
prompts are not.

Three benchmark projects; broader, domain-diverse benchmarks are needed 
for generalisation.

P A T H F O R W A R D

→ 

Scale benchmarks to 10+ projects with 50+ requirements each. 

→ 

Add Java / JavaScript / Go benchmark projects.

→ 

Conduct user studies with real development teams. 

→ 

Run full sweeps with multiple ACP agents using live API keys.

R e q L e n s

S L I D E 1 8 · C O N C L U S I O N 

ReqLens · IS 698 · May 2026 

18 / 19

Five Findings

01 

Decomposition works.

The 6-stage pipeline with Pydantic-typed contracts produces structured, traceable 
outputs single-pass cannot match — 80% vs ~45%.

02 

Prompt strategy matters.

ANOVA confirms statistically significant differences (p < .05). Few-shot dynamic 
outperforms zero-shot by 35 percentage points.

03 

Context has diminishing returns.

Full context improves traceability by 15–19 pp over minimal — at 2–3× token cost. 
Module mode offers the best cost/quality trade-off.

04 

Hybrid retrieval is precise.

FAISS + BM25 reaches 100% precision@3 across all benchmark requirement queries, 
validating the retrieval-augmented mapping approach.

05 

Critique is a quality multiplier.

40% of initially generated tests are revised or rejected — preventing low-quality tests from reaching the traceability matrix.

85 / 85 tests pass. Contracts, retrieval, metrics, statistics, prompts, context modes, API, agent registry — all validated.

R e q L e n s

S L I D E 1 9 · R E F E R E N C E S 

ReqLens · IS 698 · May 2026 

19 / 19

References

01 Fraser, G., & Arcuri, A. (2011). EvoSuite: Automatic test suite generation for object-oriented 
software. ESEC/FSE.

02 Pacheco, C., & Ernst, M. D. (2007). Randoop: Feedback-directed random testing for Java. 
OOPSLA Companion.

03 Lukasczyk, S., Kroiss, F., & Fraser, G. (2022). An empirical study of automated unit test 
generation for Python. EMSE.

04 Chen, Y., et al. (2023). ChatUniTest: A ChatGPT-based automated unit test generation tool. 
arXiv:2305.04764.

05 Lemieux, C., et al. (2023). CodaMosa: Escaping coverage plateaus in test generation with pre-
trained large language models. ICSE.

06 Schaefer, M., et al. (2023). An empirical evaluation of using large language models for 
automated unit test generation. TSE.

07 Chen, M., et al. (2021). Evaluating large language models trained on code. arXiv:2107.03374.

08 Dinella, E., et al. (2022). TOGA: A neural method for test oracle generation. ICSE.

09 Alagarsamy, S., et al. (2023). A3Test: Assertion-augmented automated test case generation. 
arXiv:2302.10352.

10 Guo, J., et al. (2017). Semantically enhanced software traceability using deep learning 
techniques. ICSE.

11 Li, B., et al. (2023). Automated test case generation from requirements: A systematic literature 
review. IST.

12 Huang, D., et al. (2024). AgentCoder: Multi-agent-based code generation with iterative testing 
and optimisation. arXiv:2312.13010.

R e q L e n s

S L I D E 2 0 · T h a n k Y o u 

ReqLens · IS 698 · May 2026 

19 / 19

THANK YOU 

