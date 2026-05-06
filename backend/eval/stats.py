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
from typing import Any

import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


def run_statistical_analysis(metrics_by_config: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Run ANOVA and pairwise comparisons on sweep metrics grouped by configuration.

    Groups metrics by prompt_strategy and context_mode, then for each quality
    metric runs one-way ANOVA. If the ANOVA is significant (p < 0.05), follows
    up with pairwise Welch's t-tests corrected for multiple comparisons.

    Args:
        metrics_by_config: List of metric dicts from compute_metrics(), each
            augmented with "prompt_strategy" and "context_mode" fields.

    Returns:
        Dict with "anova", "pairwise", and "effect_sizes" sections. Returns
        a note if fewer than 2 configurations are provided (no comparison possible).
    """
    if len(metrics_by_config) < 2:
        return {"note": "Not enough data for statistical analysis"}

    report: dict[str, Any] = {"anova": {}, "pairwise": {}, "effect_sizes": {}}

    # These are the quality metrics we compare across configurations
    metric_keys = ["traceability_score", "test_pass_rate", "critique_accept_rate"]

    # Group metrics by prompt strategy and context mode
    by_strategy: dict[str, list[dict[str, Any]]] = {}
    by_context: dict[str, list[dict[str, Any]]] = {}

    for entry in metrics_by_config:
        strategy = entry.get("prompt_strategy", "unknown")
        context = entry.get("context_mode", "unknown")
        by_strategy.setdefault(strategy, []).append(entry)
        by_context.setdefault(context, []).append(entry)

    for metric_key in metric_keys:
        # Extract metric values grouped by prompt strategy
        groups_strategy = []
        labels_strategy = []
        for label, entries in sorted(by_strategy.items()):
            vals = [e.get(metric_key, 0.0) for e in entries]
            if vals:
                groups_strategy.append(vals)
                labels_strategy.append(label)

        # Need at least 2 groups to run ANOVA
        if len(groups_strategy) >= 2:
            try:
                # One-way ANOVA: tests if any group mean differs significantly
                f_stat, p_value = scipy_stats.f_oneway(*groups_strategy)

                # Compute eta-squared (effect size): proportion of total variance
                # explained by the grouping factor
                ss_between = sum(
                    len(g) * (np.mean(g) - np.mean([v for grp in groups_strategy for v in grp])) ** 2
                    for g in groups_strategy
                )
                ss_total = sum(
                    (v - np.mean([v for grp in groups_strategy for v in grp])) ** 2
                    for grp in groups_strategy
                    for v in grp
                )
                eta_sq = float(ss_between / ss_total) if ss_total > 0 else 0.0

                report["anova"][f"strategy_{metric_key}"] = {
                    "f_statistic": float(f_stat) if not np.isnan(f_stat) else 0.0,
                    "p_value": float(p_value) if not np.isnan(p_value) else 1.0,
                    "eta_squared": eta_sq,
                    "groups": labels_strategy,
                }

                # If ANOVA is significant, do pairwise comparisons
                if p_value < 0.05:
                    # Bonferroni correction: multiply each p-value by the number
                    # of comparisons to control family-wise error rate
                    n_comparisons = len(groups_strategy) * (len(groups_strategy) - 1) // 2
                    pairwise = []
                    for i in range(len(groups_strategy)):
                        for j in range(i + 1, len(groups_strategy)):
                            # Welch's t-test (equal_var=False): does not assume
                            # equal variance between groups
                            t_stat, t_p = scipy_stats.ttest_ind(groups_strategy[i], groups_strategy[j], equal_var=False)
                            adjusted_p = min(float(t_p) * n_comparisons, 1.0) if not np.isnan(t_p) else 1.0

                            # Cohen's d: standardized effect size between two groups
                            pooled_std = np.sqrt((np.var(groups_strategy[i]) + np.var(groups_strategy[j])) / 2)
                            cohens_d = (
                                float((np.mean(groups_strategy[i]) - np.mean(groups_strategy[j])) / pooled_std)
                                if pooled_std > 0
                                else 0.0
                            )

                            pairwise.append(
                                {
                                    "pair": [labels_strategy[i], labels_strategy[j]],
                                    "t_statistic": float(t_stat) if not np.isnan(t_stat) else 0.0,
                                    "p_value_bonferroni": adjusted_p,
                                    "cohens_d": cohens_d,
                                }
                            )
                    report["pairwise"][f"strategy_{metric_key}"] = pairwise

            except Exception as e:
                logger.warning("ANOVA failed for strategy/%s: %s", metric_key, e)

    return report


def generate_markdown_report(stats: dict[str, Any]) -> str:
    """
    Generate a human-readable Markdown report from statistical analysis results.

    Formats the ANOVA results and pairwise comparisons as Markdown tables
    suitable for display in the frontend or export.

    Args:
        stats: The output dict from run_statistical_analysis().

    Returns:
        Markdown-formatted string with tables for ANOVA and pairwise results.
    """
    lines = ["# Statistical Analysis Report", ""]

    if stats.get("anova"):
        lines.append("## ANOVA Results")
        lines.append("")
        lines.append("| Factor | Metric | F-statistic | p-value | eta-squared |")
        lines.append("|--------|--------|-------------|---------|-------------|")
        for key, val in stats["anova"].items():
            lines.append(f"| {key} | - | {val['f_statistic']:.4f} | {val['p_value']:.4f} | {val['eta_squared']:.4f} |")
        lines.append("")

    if stats.get("pairwise"):
        lines.append("## Pairwise Comparisons (Bonferroni-corrected)")
        lines.append("")
        for key, pairs in stats["pairwise"].items():
            lines.append(f"### {key}")
            lines.append("")
            lines.append("| Pair | t-statistic | p-value | Cohen's d |")
            lines.append("|------|-------------|---------|-----------|")
            for p in pairs:
                lines.append(
                    f"| {p['pair'][0]} vs {p['pair'][1]} | "
                    f"{p['t_statistic']:.4f} | {p['p_value_bonferroni']:.4f} | {p['cohens_d']:.4f} |"
                )
            lines.append("")

    return "\n".join(lines)
