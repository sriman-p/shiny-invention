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

import logging
from typing import Any

logger = logging.getLogger(__name__)


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

    # Find the trace stage output (contains the traceability matrix)
    trace_stage = None
    for s in stages:
        if s.get("stage") == "trace" and s.get("output_payload"):
            trace_stage = s["output_payload"]

    # Find the critique stage output (contains test quality scores)
    critique_stage = None
    for s in stages:
        if s.get("stage") == "critique" and s.get("output_payload"):
            critique_stage = s["output_payload"]

    # Traceability score: what fraction of requirements have test coverage?
    traceability_score = 0.0
    if trace_stage and trace_stage.get("matrix"):
        matrix = trace_stage["matrix"]
        covered = sum(1 for r in matrix if r.get("coverage_status") in ("covered", "partial"))
        traceability_score = covered / len(matrix) if matrix else 0.0

    # Critique accept rate: what fraction of generated tests were accepted as-is?
    critique_accept_rate = 0.0
    if critique_stage and critique_stage.get("scores"):
        scores = critique_stage["scores"]
        accepted = sum(1 for s in scores if s.get("decision") == "accept")
        critique_accept_rate = accepted / len(scores) if scores else 0.0

    # Cost metrics: total latency and token usage across all stages
    total_latency = sum(s.get("latency_ms", 0) or 0 for s in stages)
    total_tokens = sum(sum(s.get("token_usage", {}).values()) for s in stages if isinstance(s.get("token_usage"), dict))

    return {
        "traceability_score": traceability_score,
        "test_pass_rate": 0.0,  # Placeholder for future test execution integration
        "line_coverage": 0.0,  # Placeholder for future coverage tool integration
        "critique_accept_rate": critique_accept_rate,
        "latency_total_ms": total_latency,
        "tokens_total": total_tokens,
    }
