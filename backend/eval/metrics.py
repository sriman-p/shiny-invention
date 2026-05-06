import logging
from typing import Any

logger = logging.getLogger(__name__)


def compute_metrics(run_data: dict[str, Any]) -> dict[str, Any]:
    stages = run_data.get("stages", [])

    trace_stage = None
    for s in stages:
        if s.get("stage") == "trace" and s.get("output_payload"):
            trace_stage = s["output_payload"]

    critique_stage = None
    for s in stages:
        if s.get("stage") == "critique" and s.get("output_payload"):
            critique_stage = s["output_payload"]

    traceability_score = 0.0
    if trace_stage and trace_stage.get("matrix"):
        matrix = trace_stage["matrix"]
        covered = sum(1 for r in matrix if r.get("coverage_status") in ("covered", "partial"))
        traceability_score = covered / len(matrix) if matrix else 0.0

    critique_accept_rate = 0.0
    if critique_stage and critique_stage.get("scores"):
        scores = critique_stage["scores"]
        accepted = sum(1 for s in scores if s.get("decision") == "accept")
        critique_accept_rate = accepted / len(scores) if scores else 0.0

    total_latency = sum(s.get("latency_ms", 0) or 0 for s in stages)
    total_tokens = sum(
        sum(s.get("token_usage", {}).values()) for s in stages if isinstance(s.get("token_usage"), dict)
    )

    return {
        "traceability_score": traceability_score,
        "test_pass_rate": 0.0,
        "line_coverage": 0.0,
        "critique_accept_rate": critique_accept_rate,
        "latency_total_ms": total_latency,
        "tokens_total": total_tokens,
    }
