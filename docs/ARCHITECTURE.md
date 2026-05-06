# Architecture

## System Overview

```
┌─────────────┐     ┌─────────────┐
│  Next.js 15 │────▶│  Django 5.x │
│  (port 3000)│◀────│  (port 8000)│
└─────────────┘     └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
         ┌────┴────┐ ┌────┴────┐ ┌────┴────┐
         │Pipeline │ │  Core   │ │  Eval   │
         │ Stages  │ │ Models  │ │ Engine  │
         └────┬────┘ └─────────┘ └─────────┘
              │
         ┌────┴────┐
         │   ACP   │──▶ External Agents
         │  Client │    (Claude Code, Codex, etc.)
         └─────────┘
```

## Pipeline Stages

1. **Parse** — Extract requirements from document
2. **Analyze** — Walk codebase, build symbol inventory
3. **Map** — Map requirements to code symbols
4. **Generate** — Generate pytest tests for each mapping
5. **Critique** — Score tests on relevance/completeness/correctness
6. **Trace** — Build traceability matrix + gap report

## Data Flow

Each stage's output is the next stage's input. All stage I/O is typed with Pydantic v2 models in `pipeline/contracts.py`.

## Evaluation

The 16-config sweep tests 4 prompt strategies × 4 context modes:
- Strategies: zero_shot, chain_of_thought, few_shot_static, few_shot_dynamic
- Context: minimal, local, module, full

Statistical analysis: one-way ANOVA + Bonferroni-corrected pairwise t-tests.
