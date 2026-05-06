import logging
from typing import Any

import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


def run_statistical_analysis(metrics_by_config: list[dict[str, Any]]) -> dict[str, Any]:
    if len(metrics_by_config) < 2:
        return {"note": "Not enough data for statistical analysis"}

    report: dict[str, Any] = {"anova": {}, "pairwise": {}, "effect_sizes": {}}

    metric_keys = ["traceability_score", "test_pass_rate", "critique_accept_rate"]

    by_strategy: dict[str, list[dict[str, Any]]] = {}
    by_context: dict[str, list[dict[str, Any]]] = {}

    for entry in metrics_by_config:
        strategy = entry.get("prompt_strategy", "unknown")
        context = entry.get("context_mode", "unknown")
        by_strategy.setdefault(strategy, []).append(entry)
        by_context.setdefault(context, []).append(entry)

    for metric_key in metric_keys:
        groups_strategy = []
        labels_strategy = []
        for label, entries in sorted(by_strategy.items()):
            vals = [e.get(metric_key, 0.0) for e in entries]
            if vals:
                groups_strategy.append(vals)
                labels_strategy.append(label)

        if len(groups_strategy) >= 2:
            try:
                f_stat, p_value = scipy_stats.f_oneway(*groups_strategy)
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

                if p_value < 0.05:
                    n_comparisons = len(groups_strategy) * (len(groups_strategy) - 1) // 2
                    pairwise = []
                    for i in range(len(groups_strategy)):
                        for j in range(i + 1, len(groups_strategy)):
                            t_stat, t_p = scipy_stats.ttest_ind(
                                groups_strategy[i], groups_strategy[j], equal_var=False
                            )
                            adjusted_p = min(float(t_p) * n_comparisons, 1.0) if not np.isnan(t_p) else 1.0

                            pooled_std = np.sqrt(
                                (np.var(groups_strategy[i]) + np.var(groups_strategy[j])) / 2
                            )
                            cohens_d = (
                                float((np.mean(groups_strategy[i]) - np.mean(groups_strategy[j])) / pooled_std)
                                if pooled_std > 0
                                else 0.0
                            )

                            pairwise.append({
                                "pair": [labels_strategy[i], labels_strategy[j]],
                                "t_statistic": float(t_stat) if not np.isnan(t_stat) else 0.0,
                                "p_value_bonferroni": adjusted_p,
                                "cohens_d": cohens_d,
                            })
                    report["pairwise"][f"strategy_{metric_key}"] = pairwise

            except Exception as e:
                logger.warning("ANOVA failed for strategy/%s: %s", metric_key, e)

    return report


def generate_markdown_report(stats: dict[str, Any]) -> str:
    lines = ["# Statistical Analysis Report", ""]

    if stats.get("anova"):
        lines.append("## ANOVA Results")
        lines.append("")
        lines.append("| Factor | Metric | F-statistic | p-value | eta-squared |")
        lines.append("|--------|--------|-------------|---------|-------------|")
        for key, val in stats["anova"].items():
            lines.append(
                f"| {key} | - | {val['f_statistic']:.4f} | {val['p_value']:.4f} | {val['eta_squared']:.4f} |"
            )
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
