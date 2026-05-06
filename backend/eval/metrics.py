"""
Metrics computation for pipeline run evaluation.

This module computes quality and cost metrics from a completed pipeline run's
stage data. These metrics are used by the sweep runner to compare different
pipeline configurations (prompt strategies, context modes, agents).

Computed metrics:
  - traceability_score: fraction of requirements that have "covered" or "partial"
    coverage in the traceability matrix (from the trace stage). Higher is better.
  - test_pass_rate: placeholder (always 0.0) for future integration with actual
    test execution. Would measure what fraction of generated tests pass.
  - line_coverage: placeholder (always 0.0) for future integration with coverage
    tools. Would measure what fraction of code lines are exercised by tests.
  - critique_accept_rate: fraction of generated tests that the critique stage
    accepted (decision == "accept"). Higher means the generator is producing
    better tests.
  - latency_total_ms: sum of all stage latencies in milliseconds. Lower is better.
  - tokens_total: total token count across all stages. Lower is better (cheaper).

The traceability_score and critique_accept_rate are the primary quality metrics.
Latency and tokens are cost metrics used to assess efficiency.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _as_number(value: Any) -> float:
    return float(value) if isinstance(value, int | float) else 0.0


def _stage_payload(stages: list[dict[str, Any]], stage_name: str) -> dict[str, Any]:
    for stage in stages:
        if stage.get("stage") == stage_name and isinstance(stage.get("output_payload"), dict):
            return stage["output_payload"]
    return {}


def compute_metrics(run_data: dict[str, Any]) -> dict[str, Any]:
    """
    Compute evaluation metrics from a completed pipeline run.

    Reads the output payloads from the trace and critique stages to calculate
    quality metrics, and sums latency/token usage across all stages for cost metrics.

    Args:
        run_data: Dict with a "stages" key containing a list of stage execution
            dicts. Each stage dict should have "stage", "output_payload",
            "latency_ms", and "token_usage" fields.

    Returns:
        Dict of metric names to values, ready for storage in Sweep.metrics_summary.
    """
    stages = run_data.get("stages", [])
    stages = stages if isinstance(stages, list) else []

    trace_stage = _stage_payload(stages, "trace")
    critique_stage = _stage_payload(stages, "critique")
    generate_stage = _stage_payload(stages, "generate")

    # Traceability score: what fraction of requirements have test coverage?
    traceability_score = 0.0
    strict_coverage_score = 0.0
    coverage_counts = {"covered": 0, "partial": 0, "uncovered": 0}
    total_requirements = 0
    if trace_stage and trace_stage.get("matrix"):
        matrix = trace_stage["matrix"]
        if isinstance(matrix, list):
            total_requirements = len(matrix)
            for row in matrix:
                if not isinstance(row, dict):
                    continue
                status = str(row.get("coverage_status", "uncovered"))
                if status in coverage_counts:
                    coverage_counts[status] += 1
            covered_or_partial = coverage_counts["covered"] + coverage_counts["partial"]
            traceability_score = covered_or_partial / total_requirements if total_requirements else 0.0
            strict_coverage_score = coverage_counts["covered"] / total_requirements if total_requirements else 0.0

    # Critique accept rate: what fraction of generated tests were accepted as-is?
    critique_accept_rate = 0.0
    critique_mean_score = 0.0
    if critique_stage and critique_stage.get("scores"):
        scores = critique_stage["scores"]
        if isinstance(scores, list):
            accepted = sum(1 for s in scores if isinstance(s, dict) and s.get("decision") == "accept")
            critique_accept_rate = accepted / len(scores) if scores else 0.0
            score_values = [
                (_as_number(s.get("relevance")) + _as_number(s.get("completeness")) + _as_number(s.get("correctness")))
                / 15
                for s in scores
                if isinstance(s, dict)
            ]
            critique_mean_score = sum(score_values) / len(score_values) if score_values else 0.0

    generated_tests_count = 0
    if generate_stage and isinstance(generate_stage.get("tests"), list):
        generated_tests_count = len(generate_stage["tests"])

    # Cost metrics: total latency and token usage across all stages
    total_latency = sum(s.get("latency_ms", 0) or 0 for s in stages)
    total_tokens = sum(sum(s.get("token_usage", {}).values()) for s in stages if isinstance(s.get("token_usage"), dict))
    output_bytes = sum(
        len(json.dumps(s.get("output_payload", {}), default=str))
        for s in stages
        if isinstance(s.get("output_payload"), dict)
    )
    completed_stages = sum(1 for s in stages if s.get("status") == "succeeded")
    failed_stages = sum(1 for s in stages if s.get("status") == "failed")
    quality_score = (traceability_score * 0.6) + (critique_accept_rate * 0.25) + (critique_mean_score * 0.15)

    return {
        "traceability_score": traceability_score,
        "strict_coverage_score": strict_coverage_score,
        "test_pass_rate": 0.0,  # Placeholder for future test execution integration
        "line_coverage": 0.0,  # Placeholder for future coverage tool integration
        "critique_accept_rate": critique_accept_rate,
        "critique_mean_score": critique_mean_score,
        "quality_score": quality_score,
        "coverage_counts": coverage_counts,
        "total_requirements": total_requirements,
        "generated_tests_count": generated_tests_count,
        "completed_stages": completed_stages,
        "failed_stages": failed_stages,
        "output_bytes": output_bytes,
        "latency_total_ms": total_latency,
        "tokens_total": total_tokens,
    }


def rank_metrics(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank sweep metrics by quality first, then lower latency and token cost."""
    ranked = sorted(
        metrics,
        key=lambda row: (
            -_as_number(row.get("quality_score")),
            -_as_number(row.get("traceability_score")),
            _as_number(row.get("latency_total_ms")),
            _as_number(row.get("tokens_total")),
        ),
    )
    result: list[dict[str, Any]] = []
    for index, row in enumerate(ranked, start=1):
        result.append({**row, "rank": index, "is_winner": index == 1})
    return result
