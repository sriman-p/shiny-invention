# Sweep `04f785b4` — Statistical Analysis Report

Project: **todo-api**  ·  Agent: **cursor/composer-2 [fast=true]**  ·  17 runs (14 produced metrics, 3 failed)
Generated from `backend/eval/metrics.py` + `backend/eval/stats.py`.

---

## 1. Quick verdict

| Aspect | Reading | Confidence |
|---|---|---|
| **Pipeline vs baseline** | The 6-stage pipeline crushes the single-pass `direct_acp_baseline` (16.7% → 95.9% quality, 0% → 100% traceability). | Very high. The lift is real and large. |
| **Strategy/context choice on the working pipeline** | Almost all working configs tie at ~95.9% quality, 100% traceability, 75% accept. Differences between `few_shot_*`, `zero_shot`, `chain_of_thought` are tiny. | Low — most apparent significance is driven by the broken baseline outlier. |
| **`chain_of_thought` reliability** | 3 of 4 CoT cells failed (`minimal`, `module`, `full`). Only `chain_of_thought · local` succeeded. | High concern. CoT looks fragile in this run. |
| **Some metrics are stubs** | `test_pass_rate` and `line_coverage` are hard-coded to 0.0 in `metrics.py` (placeholders). | Documented in code. |

**TL;DR:** the *** stars on the strategy/context ANOVA mostly mean *“the broken baseline is different from the pipelines”* — they do **not** prove that one prompt strategy beats another on this project. The within-pipeline variance is mostly zero.

---

## 2. What each value means in this codebase

These come from `backend/eval/metrics.py` and `backend/eval/stats.py`.

### Quality metrics (higher is better, all in `[0,1]`)

| Metric | Definition (this repo) |
|---|---|
| `traceability_score` | Fraction of parsed requirements with `covered` **or** `partial` coverage in the trace matrix. |
| `strict_coverage_score` | Fraction of requirements with `covered` (excludes `partial`). |
| `critique_accept_rate` | Fraction of generated tests the critique stage marked `decision == "accept"`. |
| `critique_mean_score` | Mean of `(relevance + completeness + correctness)/15` per critique. |
| `mapped_requirements_rate` | Fraction of parsed requirements linked to an implementation symbol by the map stage. |
| `mapping_confidence_avg` | Average confidence over all `mappings` from the map stage. |
| `faiss_evidence_per_mapping` | Average # of FAISS evidence snippets per mapping (raw count, not bounded to 1). |
| `generation_coverage_rate` | Fraction of parsed requirements that received ≥1 generated test. |
| `trace_matrix_completion_rate` | Fraction of requirements that have a row in the trace matrix at all. |
| `stage_success_rate` | `completed_stages / 6` (the pipeline always has 6 stages). |
| `quality_score` | Weighted composite (see below). |
| `test_pass_rate` | **Hard-coded 0.0** — placeholder, no tests are actually executed. |
| `line_coverage` | **Hard-coded 0.0** — placeholder. |

### Composite `quality_score` (from `metrics.py:240`)

```python
quality_score = (
    traceability_score        * 0.30 +
    mapped_requirements_rate  * 0.20 +
    generation_coverage_rate  * 0.15 +
    critique_accept_rate      * 0.15 +
    critique_mean_score       * 0.10 +
    trace_matrix_completion_rate * 0.05 +
    stage_success_rate        * 0.05
)
```

So **30% of `quality_score` is just trace coverage**, and 20% is whether mapping found a symbol. With the way the trace and map stages succeed on `todo-api`, this metric saturates fast.

### Significance buckets (from `stats.py`)

```text
p < .001  → ***   (very strong evidence against “no difference”)
p < .01   → **
p < .05   → *
p ≥ .05   → ns
```

```text
η² ≥ 0.14 → large       (Cohen)
η² ≥ 0.06 → medium
η² ≥ 0.01 → small
else      → negligible
```

```text
|d| ≥ 0.8 → large
|d| ≥ 0.5 → medium
|d| ≥ 0.2 → small
```

---

## 3. Sweep coverage health

- **17 cells planned** = 1 baseline + 4 strategies × 4 contexts.
- **14 succeeded**, **3 failed** (`chain_of_thought · minimal`, `chain_of_thought · module`, `chain_of_thought · full`).
- The stat module reports: *“Statistical results are partial: 14 of 17 configurations produced reliable metrics.”* That is correct and important — pairwise tests over 4 strategies × 4 contexts already have very low n, and CoT only contributes 1 sample.

**Risk:** With n = 1–4 per strategy group, ANOVA is essentially a sanity check, not a power test.

---

## 4. Reading the per-row values (your table)

Below, **“good or bad?”** is judged from the **metric’s ideal value (1.0 / 100% / etc.)** and from whether the result is **driven by real differences or by the baseline outlier**.

### Strategy axis

| Metric | p | η² | Real meaning here | Good/bad |
|---|---|---|---|---|
| `traceability_score` | 0.0000 *** | 1.000 | Pipeline is 100% covered, baseline is 0% → all variance is between “works” and “does-not-work”. | **Good for the pipeline; uninformative about strategies.** |
| `strict_coverage_score` | 0.0000 *** | 0.935 | Same story. `few_shot_dynamic · module` and `· local` dropped to 75%; everyone else 100%. | **Slight degradation in dynamic few-shot — flag, but not a blocker.** |
| `test_pass_rate` | 1.0000 ns | 0.000 negligible | **Stub metric**, always 0.0 (`metrics.py:255`). | **N/A — ignore until tests are actually executed.** |
| `critique_accept_rate` | 0.0001 *** | 0.915 | Almost all 75%; `zero_shot · full` is 50%; baseline is 0%. *** is from the baseline, not from strategy. | **Acceptable — 75% is healthy.** |
| `quality_score` | 0.0000 *** | 0.998 | Pipeline ~95.9 vs baseline 16.7. Within strategies the spread is ~0.5%. | **Excellent for pipelines.** |
| `mapped_requirements_rate` | 0.0000 *** | 1.000 | 100% across all working configs, 0% baseline. | **Saturated — good, but no discrimination signal.** |
| `mapping_confidence_avg` | 0.0000 *** | 0.999 | 94.8–98% (small but real spread). | **Good. Zero-shot is highest at 98% in several cells.** |
| `faiss_evidence_per_mapping` | 0.0806 ns | 0.569 large | Real variance (1.0–4.3) but n too small to clear α=0.05. | **Inconclusive. Re-run with replicates.** |
| `generation_coverage_rate` | 1.0000 ns | 0.000 | 100% everywhere (baseline too). No variance. | **Saturated — neutral.** |
| `trace_matrix_completion_rate` | 0.0000 *** | 1.000 | 100% pipeline, baseline incomplete. | **Good for pipeline.** |
| `stage_success_rate` | 0.0000 *** | 1.000 | 6/6 for pipelines, 2/6 for baseline. | **Good.** |

### Context axis

Same shape as strategy. Two notes worth calling out:

- `context_strict_coverage_score` is *** with η²=0.908. That comes from `few_shot_dynamic` losing strict coverage at `module` (75%) and `local` (75%) — i.e. **dynamic few-shot is more brittle on smaller/medium contexts**. Static few-shot stays at 100% across all four contexts.
- `context_critique_accept_rate` is *** with η²=0.925, but the only sub-75% cell is `zero_shot · full` at 50%. The result is mostly “baseline = 0%” pulling the variance.

### Cohen’s d highlights (the “large” pairwise list)

Almost every Bonferroni-corrected pairwise p is **1.0000 ns**. The values labeled “large” are large *effect sizes* on tiny n; they are **not** statistically significant after correction. Two are worth reading:

- `strategy_mapping_confidence_avg`: `few_shot_static vs zero_shot` → **adjusted p = 0.0341 *, d = -4.20 large.** This is the only pair that survives Bonferroni. Direction: **zero_shot beats few_shot_static on average mapping confidence** (but the absolute gap is ~98% vs ~95% — not meaningful in practice).
- `strategy_strict_coverage_score`: `few_shot_dynamic vs few_shot_static` → d = -1.41 large but adjusted p = 1.0. Real direction (dynamic worse on strict), but underpowered.

### The values that look weird and why

You will see rows like:

```text
F-statistic 0.0000   p 0.0000   η² 1.0000   ***
```

That is a **degenerate ANOVA**, not a real F-stat of zero with p≈0. It happens when within-group variance = 0 (every working pipeline has the exact same 100% score). SciPy returns `F = inf, p ≈ 0`; the helper `_finite_float` in `stats.py:33` falls back to `0.0` for non-finite floats and that is what you see in the table:

```33:39:backend/eval/stats.py
def _finite_float(value: Any, default: float = 0.0) -> float:
    """Convert numpy/scipy numeric output into JSON-safe finite floats."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default
```

**Implication:** treat any row where `F = 0.0000` and `p = 0.0000` as “the metric is constant within groups; the ‘significance’ comes from a single outlier (the baseline) being categorically different.” It is not evidence that prompt strategy or context mode matters.

---

## 5. Are the numbers “good” for `todo-api`?

Treating `todo-api` (4 requirements) as a small, well-bounded benchmark:

| Dimension | Value | Verdict |
|---|---|---|
| Best `quality_score` | 0.959 | **Excellent** — at ceiling of what this composite can give without the test-execution stub. Theoretical max with `test_pass_rate = 0` placeholder is roughly 0.965 (1.0 on every other component), so the pipeline is ≈99% of the achievable score. |
| Worst working `quality_score` | 0.920 (`zero_shot · full`) | Still strong; the gap is the 50% accept rate on that cell. |
| Traceability | 100% across all 13 working configs | **At ceiling.** |
| Strict coverage | 100% in 11/13 cells, 75% in 2 (`few_shot_dynamic · module`, `· local`) | **Mostly ceiling**, dynamic few-shot wobbles. |
| Critique accept rate | 75% (12 cells), 50% (1 cell) | **Acceptable** — the critique stage is set up to reject ~25% by default; getting 75% accept is healthy. |
| Mapping confidence | 94.8%–98.0% | **Strong.** Zero-shot tends slightly higher. |
| FAISS evidence per mapping | 1.0–4.3 | **Mixed.** `zero_shot · module` (4.3) and `few_shot_static · local` (4.0) are richest; CoT-local and few-shot-dynamic-minimal are thin (1.0). |
| Latency | 2m26s – 4m25s for pipelines vs **54s** baseline | **The pipeline is 3–5× slower** than direct generation. That is the cost of all the structure. |
| Tokens | 0 reported | The agent runner is not emitting `token_usage` for `cursor/composer-2`, so token-cost analysis is **not possible from this run**. |
| Run reliability | 14/17 succeeded | **Concern.** Three CoT failures and several earlier sweeps in the “Saved Sweeps” list also failed — see §7. |

So: **on quality, this is a strong run.** On reliability and on the value the stats module is adding **on this dataset**, there are real caveats.

---

## 6. What this sweep can and cannot tell you

### It can tell you
1. The **multi-stage pipeline is dramatically better than single-pass ACP** for this requirement set (ΔQuality +475%, ΔTraceability +100%).
2. **`few_shot_static` is the safest strategy:** it scored at the top across all four contexts and was the fastest pipeline at `· full` (2m26s).
3. **`few_shot_dynamic` loses strict coverage** at `local`/`module` contexts (drops to 75%). If you care about strict (not partial) coverage, prefer static.
4. **`chain_of_thought` is unstable** in this configuration of `cursor/composer-2[fast=true]` — 3/4 cells failed. That is a reliability problem, not a quality one.
5. **`zero_shot` is competitive.** It ties on `quality_score` at most contexts and has the highest mapping confidence (98%). The cheapest option that still passes.

### It cannot tell you (yet)
1. **Whether tests actually pass.** `test_pass_rate` and `line_coverage` are placeholders — runtime test execution is not wired in. Until those land, `quality_score` is really a *structural* score.
2. **Whether prompt strategy matters in general.** With n=1 per `(strategy, context)` cell and most metrics saturated, ANOVA cannot separate strategies. The η²=1.0 results are baseline-driven.
3. **Token cost.** `tokens_total = 0` for every row — the metric pipeline did not see token usage from the agent.
4. **Whether `todo-api` represents harder projects.** 4 requirements is small enough that 100% coverage is easy; redo on `url-shortener` or larger before publishing claims.

---

## 7. Operational red flags worth fixing

These come from looking at the broader sweep history, not just this one run.

1. **High failure rate across the sweep history**: of the 15 sweeps listed, only `04f785b4` reached 14/17 metric rows. Eight others were `failed` with 0 or low metric counts; four were `cancelled`. Worth investigating whether early failures were the agent registry warning (no ACP agents installed in the cloud VM, per `AGENTS.md`).
2. **`chain_of_thought` failures are concentrated** on `minimal`, `module`, and `full` contexts. Either the CoT prompt is too long for those context sizes, or the parser/critique stage rejects CoT outputs differently. Check `backend/pipeline/stages/*` for CoT-specific handling.
3. **`F = 0, p = 0` rendering**: not a bug in the math, but as displayed it is misleading. Consider showing `F = ∞ (degenerate)` or hiding `F` when within-group variance is zero — the current behavior makes ns metrics and degenerate metrics indistinguishable in the UI.
4. **`tokens_total = 0`** for every run with `cursor/composer-2[fast=true]`. If accurate, the lift table’s `ΔTokens = +0.0%` is meaningless. If the agent simply does not report tokens, the column should be hidden for that provider.

---

## 8. Recommended next steps

In rough order of value:

1. **Replicate** the same sweep 3× on `todo-api` (and once on `url-shortener` and `calculator`) so each `(strategy, context)` cell has n=3+. ANOVA will then be informative.
2. **Wire `test_pass_rate`** by executing the generated pytest files in a sandbox and reading the JUnit results. This is the biggest single jump the `quality_score` can take.
3. **Fix CoT reliability** before claiming any strategy ranking; right now CoT contributes only 1 sample.
4. **Either fix `tokens_total` reporting** for the `cursor` provider or remove the `ΔTokens` column for it.
5. **In the UI:** when `F = inf`/`p = 0` is degenerate, label it as “constant within groups (baseline-driven)” instead of `***` to avoid overstating findings.

---

## 9. One-line summary you can use in a deck

> On `todo-api`, the ReqLens 6-stage pipeline lifted structural quality from **16.7% to 95.9%** (+475%) and traceability from **0% to 100%**, with `few_shot_static · full` as the most reliable winner. Within working pipelines, prompt-strategy and context-mode differences are not statistically separable at this sample size; the *** badges on the ANOVA come from comparing pipelines against the deliberate single-pass baseline.
