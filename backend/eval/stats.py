"""
Statistical analysis for comparing pipeline configurations across sweep runs.

When a sweep finishes, this module analyzes the collected metrics to determine
whether different pipeline configurations (prompt strategies, context modes)
produce statistically significant differences in quality metrics.

The analysis uses standard statistical methods:
  1. One-way ANOVA: tests whether at least one group mean differs significantly.
     If p < 0.05, there is a statistically significant difference between groups.
  2. Effect size (eta-squared): measures how much of the total variance is explained
     by the grouping factor. Higher values mean the configuration choice matters more.
  3. Pairwise t-tests with Bonferroni correction: when ANOVA is significant,
     identifies which specific pairs of configurations differ. Bonferroni correction
     adjusts p-values to account for multiple comparisons (reduces false positives).
  4. Cohen's d: effect size for pairwise comparisons. Values of 0.2/0.5/0.8 are
     conventionally considered small/medium/large effects.

This module also generates a Markdown-formatted report that can be stored in
the sweep's stats_report field and displayed in the frontend.
"""

import logging
import math
from typing import Any

import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


def _finite_float(value: Any, default: float = 0.0) -> float:
    """Convert numpy/scipy numeric output into JSON-safe finite floats."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _json_safe(value: Any) -> Any:
    """Recursively coerce numpy/scipy values into JSON-safe Python primitives."""
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, bool | str) or value is None:
        return value
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, np.floating | float):
        return _finite_float(value)
    return str(value)


def _p_significance(p_value: float) -> str:
    """Human-friendly significance bucket for UI badges and reports."""
    if p_value < 0.001:
        return "***"
    if p_value < 0.01:
        return "**"
    if p_value < 0.05:
        return "*"
    return "ns"


def _eta_squared_magnitude(value: float) -> str:
    """Interpret eta-squared using conventional ANOVA thresholds."""
    value = abs(value)
    if value >= 0.14:
        return "large"
    if value >= 0.06:
        return "medium"
    if value >= 0.01:
        return "small"
    return "negligible"


def _cohens_d_magnitude(value: float) -> str:
    """Interpret Cohen's d using conventional pairwise effect thresholds."""
    value = abs(value)
    if value >= 0.8:
        return "large"
    if value >= 0.5:
        return "medium"
    if value >= 0.2:
        return "small"
    return "negligible"


def _format_label(entry: dict[str, Any], dimension: str) -> str:
    """Stable display label for an ANOVA group, used in the report tables."""
    if dimension == "agent":
        agent = entry.get("agent_id") or "agent"
        model = entry.get("model_id") or "default"
        return f"{agent}/{model}"
    return str(entry.get(f"{dimension}_mode" if dimension == "context" else f"{dimension}_strategy", "unknown"))


def _run_anova_group(
    report: dict[str, Any],
    metric_keys: list[str],
    grouped: dict[str, list[dict[str, Any]]],
    dimension: str,
) -> None:
    """Run ANOVA + pairwise t-tests for a single grouping dimension."""
    for metric_key in metric_keys:
        groups: list[list[float]] = []
        labels: list[str] = []
        for label, entries in sorted(grouped.items()):
            vals = [float(e.get(metric_key, 0.0) or 0.0) for e in entries]
            if vals:
                groups.append(vals)
                labels.append(label)

        if len(groups) < 2:
            continue
        if all(len(group) < 2 for group in groups):
            # One sample per group cannot support a meaningful one-way ANOVA.
            continue

        try:
            f_stat, p_value = scipy_stats.f_oneway(*groups)

            all_values = [v for grp in groups for v in grp]
            grand_mean = float(np.mean(all_values))
            ss_between = sum(len(g) * (np.mean(g) - grand_mean) ** 2 for g in groups)
            ss_total = sum((v - grand_mean) ** 2 for grp in groups for v in grp)
            eta_sq = float(ss_between / ss_total) if ss_total > 0 else 0.0

            f_stat_safe = _finite_float(f_stat)
            p_value_safe = _finite_float(p_value, default=1.0)
            eta_sq_safe = _finite_float(eta_sq)

            report["anova"][f"{dimension}_{metric_key}"] = {
                "f_statistic": f_stat_safe,
                "p_value": p_value_safe,
                "eta_squared": eta_sq_safe,
                "significant": p_value_safe < 0.05,
                "significance": _p_significance(p_value_safe),
                "effect_magnitude": _eta_squared_magnitude(eta_sq_safe),
                "groups": labels,
            }
            report["effect_sizes"][f"{dimension}_{metric_key}"] = {
                "eta_squared": eta_sq_safe,
                "eta_squared_magnitude": _eta_squared_magnitude(eta_sq_safe),
            }

            if p_value_safe < 0.05:
                n_comparisons = len(groups) * (len(groups) - 1) // 2 or 1
                pairwise = []
                max_abs_cohens_d = 0.0
                for i in range(len(groups)):
                    for j in range(i + 1, len(groups)):
                        t_stat, t_p = scipy_stats.ttest_ind(groups[i], groups[j], equal_var=False)
                        t_stat_safe = _finite_float(t_stat)
                        t_p_safe = _finite_float(t_p, default=1.0)
                        adjusted_p = min(t_p_safe * n_comparisons, 1.0)
                        pooled_std = np.sqrt((np.var(groups[i]) + np.var(groups[j])) / 2)
                        cohens_d = (
                            float((np.mean(groups[i]) - np.mean(groups[j])) / pooled_std) if pooled_std > 0 else 0.0
                        )
                        cohens_d_safe = _finite_float(cohens_d)
                        max_abs_cohens_d = max(max_abs_cohens_d, abs(cohens_d_safe))
                        pairwise.append(
                            {
                                "pair": [labels[i], labels[j]],
                                "t_statistic": t_stat_safe,
                                "p_value_bonferroni": adjusted_p,
                                "cohens_d": cohens_d_safe,
                                "significant": adjusted_p < 0.05,
                                "significance": _p_significance(adjusted_p),
                                "cohens_d_magnitude": _cohens_d_magnitude(cohens_d_safe),
                            }
                        )
                report["pairwise"][f"{dimension}_{metric_key}"] = pairwise
                report["effect_sizes"][f"{dimension}_{metric_key}"]["max_abs_cohens_d"] = _finite_float(
                    max_abs_cohens_d
                )
                report["effect_sizes"][f"{dimension}_{metric_key}"]["cohens_d_magnitude"] = _cohens_d_magnitude(
                    max_abs_cohens_d
                )
        except Exception as exc:
            logger.warning("ANOVA failed for %s/%s: %s", dimension, metric_key, exc)


def run_statistical_analysis(metrics_by_config: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Run ANOVA and pairwise comparisons on sweep metrics grouped by every
    configurable axis: prompt strategy, context mode, and (agent, model).

    For each axis and each quality metric, runs a one-way ANOVA. When the
    ANOVA is significant (p < 0.05), follows up with pairwise Welch's t-tests
    Bonferroni-corrected for multiple comparisons.

    Args:
        metrics_by_config: List of metric dicts from compute_metrics(), each
            augmented with "prompt_strategy", "context_mode", and optionally
            "agent_id" / "model_id".

    Returns:
        Dict with "anova", "pairwise", "effect_sizes", and "best_configuration"
        sections. Returns a `note` if fewer than 2 configurations are provided.
    """
    best = _best_configuration(metrics_by_config)

    if len(metrics_by_config) < 2:
        return {"note": "Not enough data for statistical analysis", "best_configuration": best}

    report: dict[str, Any] = {"anova": {}, "pairwise": {}, "effect_sizes": {}, "best_configuration": best}

    # Quality metrics we compare across configurations.
    metric_keys = [
        "traceability_score",
        "strict_coverage_score",
        "test_pass_rate",
        "critique_accept_rate",
        "quality_score",
        "mapped_requirements_rate",
        "mapping_confidence_avg",
        "faiss_evidence_per_mapping",
        "generation_coverage_rate",
        "trace_matrix_completion_rate",
        "stage_success_rate",
    ]

    by_strategy: dict[str, list[dict[str, Any]]] = {}
    by_context: dict[str, list[dict[str, Any]]] = {}
    by_agent: dict[str, list[dict[str, Any]]] = {}

    for entry in metrics_by_config:
        by_strategy.setdefault(_format_label(entry, "prompt"), []).append(entry)
        by_context.setdefault(_format_label(entry, "context"), []).append(entry)
        by_agent.setdefault(_format_label(entry, "agent"), []).append(entry)

    _run_anova_group(report, metric_keys, by_strategy, "strategy")
    _run_anova_group(report, metric_keys, by_context, "context")
    # Only useful when the sweep actually varies the agent or model.
    if len(by_agent) > 1:
        _run_anova_group(report, metric_keys, by_agent, "agent")

    return _json_safe(report)


# Lift sign convention: for these metrics, higher is better (positive lift = good).
HIGHER_IS_BETTER_METRICS = (
    "quality_score",
    "traceability_score",
    "strict_coverage_score",
    "critique_accept_rate",
    "critique_mean_score",
    "critique_coverage_rate",
    "mapped_requirements_rate",
    "mapping_confidence_avg",
    "faiss_evidence_count",
    "faiss_evidence_per_mapping",
    "generation_coverage_rate",
    "trace_matrix_completion_rate",
    "stage_success_rate",
)
# For these, lower is better (positive lift = bad → we negate so positive lift always means "better than baseline").
LOWER_IS_BETTER_METRICS = ("latency_total_ms", "tokens_total")


def compute_baseline_diff(ranked_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compute deltas vs. the worst-performing configuration in the sweep.

    The "worst" baseline is the entry with the lowest `quality_score`. For
    each other entry we record:
      - `lift`: signed percentage improvement per metric (positive = better
        than baseline regardless of whether the metric is "higher is better"
        like quality, or "lower is better" like latency).
      - `absolute_diff`: raw delta (entry - baseline).

    The returned dict has the shape:
        {
            "baseline": {"run_id": ..., "metrics": {...}, "label": ...},
            "lifts": [
                {"run_id": ..., "label": ..., "rank": 1, "lift": {...}, "absolute_diff": {...}},
                ...
            ],
        }

    Returns an empty dict when there's nothing to compare against.
    """
    if not ranked_metrics or len(ranked_metrics) < 2:
        return {}

    # Prefer an explicitly marked comparison baseline (used for the direct ACP
    # single-pass floor). Otherwise baseline = the last-ranked configuration,
    # matching the same ordering the UI presents.
    explicit_baselines = [entry for entry in ranked_metrics if entry.get("comparison_baseline")]
    if explicit_baselines and all(isinstance(entry.get("rank"), int) for entry in explicit_baselines):
        baseline = max(explicit_baselines, key=lambda e: int(e.get("rank") or 0))
    elif explicit_baselines:
        baseline = min(
            explicit_baselines,
            key=lambda e: (float(e.get("quality_score") or 0.0), -float(e.get("latency_total_ms") or 0.0)),
        )
    elif all(isinstance(entry.get("rank"), int) for entry in ranked_metrics):
        baseline = max(ranked_metrics, key=lambda e: int(e.get("rank") or 0))
    else:
        baseline = min(
            ranked_metrics,
            key=lambda e: (float(e.get("quality_score") or 0.0), -float(e.get("latency_total_ms") or 0.0)),
        )

    baseline_label = (
        f"{baseline.get('agent_id') or 'agent'}/"
        f"{baseline.get('model_id') or 'default'} · "
        f"{baseline.get('prompt_strategy', 'unknown')} · "
        f"{baseline.get('context_mode', 'unknown')}"
    )

    metric_keys = HIGHER_IS_BETTER_METRICS + LOWER_IS_BETTER_METRICS

    def safe_pct(numerator: float, denominator: float) -> float:
        if abs(denominator) < 1e-9:
            # When baseline is zero we can't compute a percentage; fall back to 0.
            return 0.0
        return (numerator / denominator) * 100.0

    lifts: list[dict[str, Any]] = []
    for entry in ranked_metrics:
        if entry.get("run_id") and baseline.get("run_id") and entry.get("run_id") == baseline.get("run_id"):
            continue
        lift: dict[str, float] = {}
        absolute_diff: dict[str, float] = {}
        for key in metric_keys:
            entry_val = float(entry.get(key) or 0.0)
            base_val = float(baseline.get(key) or 0.0)
            absolute_diff[key] = entry_val - base_val
            if key in HIGHER_IS_BETTER_METRICS:
                lift[key] = safe_pct(entry_val - base_val, base_val if base_val else max(entry_val, 1e-9))
            else:
                # Lower-is-better: positive lift means we *reduced* the value.
                lift[key] = safe_pct(base_val - entry_val, base_val if base_val else max(entry_val, 1e-9))
        lifts.append(
            {
                "run_id": entry.get("run_id"),
                "agent_id": entry.get("agent_id"),
                "model_id": entry.get("model_id"),
                "prompt_strategy": entry.get("prompt_strategy"),
                "context_mode": entry.get("context_mode"),
                "rank": entry.get("rank"),
                "label": (
                    f"{entry.get('agent_id') or 'agent'}/"
                    f"{entry.get('model_id') or 'default'} · "
                    f"{entry.get('prompt_strategy', 'unknown')} · "
                    f"{entry.get('context_mode', 'unknown')}"
                ),
                "lift": lift,
                "absolute_diff": absolute_diff,
            }
        )

    return {
        "baseline": {
            "run_id": baseline.get("run_id"),
            "rank": baseline.get("rank"),
            "label": baseline_label,
            "agent_id": baseline.get("agent_id"),
            "model_id": baseline.get("model_id"),
            "prompt_strategy": baseline.get("prompt_strategy"),
            "context_mode": baseline.get("context_mode"),
            "metrics": {key: float(baseline.get(key) or 0.0) for key in metric_keys},
        },
        "lifts": lifts,
    }


def _best_configuration(metrics_by_config: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not metrics_by_config:
        return None
    return min(
        metrics_by_config,
        key=lambda row: (
            int(row.get("rank", 999999)) if isinstance(row.get("rank"), int) else 999999,
            -float(row.get("quality_score", 0.0) or 0.0),
            float(row.get("latency_total_ms", 0.0) or 0.0),
        ),
    )


def generate_markdown_report(stats: dict[str, Any], baseline: dict[str, Any] | None = None) -> str:
    """
    Generate a human-readable Markdown report from statistical analysis results.

    Formats the ANOVA results and pairwise comparisons as Markdown tables
    suitable for display in the frontend or export. When `baseline` is
    provided (the output of `compute_baseline_diff`), adds a "Lift vs baseline
    configuration" section.

    Args:
        stats: The output dict from run_statistical_analysis().
        baseline: Optional baseline diff dict from compute_baseline_diff().

    Returns:
        Markdown-formatted string with tables for ANOVA, pairwise, and lift.
    """
    lines = ["# Statistical Analysis Report", ""]

    best = stats.get("best_configuration")
    if isinstance(best, dict):
        lines.append("## Best Configuration")
        lines.append("")
        lines.append(
            f"Rank 1: {best.get('prompt_strategy', 'unknown')} / {best.get('context_mode', 'unknown')} "
            f"with {float(best.get('quality_score', 0.0) or 0.0):.3f} quality score, "
            f"{float(best.get('traceability_score', 0.0) or 0.0):.1%} traceability, and "
            f"{float(best.get('critique_accept_rate', 0.0) or 0.0):.1%} critique accept rate."
        )
        lines.append("")

    if isinstance(baseline, dict) and baseline.get("baseline") and baseline.get("lifts"):
        base = baseline["baseline"]
        lines.append("## Lift vs Baseline Configuration")
        lines.append("")
        lines.append(
            f"Baseline: **{base.get('label', 'unknown')}** — "
            f"quality {float(base.get('metrics', {}).get('quality_score', 0.0)):.3f}, "
            f"latency {int(base.get('metrics', {}).get('latency_total_ms', 0))} ms, "
            f"tokens {int(base.get('metrics', {}).get('tokens_total', 0))}."
        )
        lines.append("")
        lines.append("| Configuration | ΔQuality | ΔTraceability | ΔAccept | ΔLatency | ΔTokens |")
        lines.append("|---------------|---------:|--------------:|--------:|---------:|--------:|")
        for lift in baseline["lifts"]:
            row = lift.get("lift", {})
            lines.append(
                f"| {lift.get('label', 'unknown')} | "
                f"{row.get('quality_score', 0.0):+.1f}% | "
                f"{row.get('traceability_score', 0.0):+.1f}% | "
                f"{row.get('critique_accept_rate', 0.0):+.1f}% | "
                f"{row.get('latency_total_ms', 0.0):+.1f}% | "
                f"{row.get('tokens_total', 0.0):+.1f}% |"
            )
        lines.append("")

    if stats.get("anova"):
        lines.append("## ANOVA Results")
        lines.append("")
        lines.append("| Factor | Metric | F-statistic | p-value | Significance | eta-squared | Effect |")
        lines.append("|--------|--------|-------------|---------|--------------|-------------|--------|")
        for key, val in stats["anova"].items():
            lines.append(
                f"| {key} | - | {val['f_statistic']:.4f} | {val['p_value']:.4f} | "
                f"{val.get('significance', 'ns')} | {val['eta_squared']:.4f} | "
                f"{val.get('effect_magnitude', 'n/a')} |"
            )
        lines.append("")

    if stats.get("pairwise"):
        lines.append("## Pairwise Comparisons (Bonferroni-corrected)")
        lines.append("")
        for key, pairs in stats["pairwise"].items():
            lines.append(f"### {key}")
            lines.append("")
            lines.append("| Pair | t-statistic | p-value | Significance | Cohen's d | Magnitude |")
            lines.append("|------|-------------|---------|--------------|-----------|-----------|")
            for p in pairs:
                lines.append(
                    f"| {p['pair'][0]} vs {p['pair'][1]} | "
                    f"{p['t_statistic']:.4f} | {p['p_value_bonferroni']:.4f} | "
                    f"{p.get('significance', 'ns')} | {p['cohens_d']:.4f} | "
                    f"{p.get('cohens_d_magnitude', 'n/a')} |"
                )
            lines.append("")

    return "\n".join(lines)
