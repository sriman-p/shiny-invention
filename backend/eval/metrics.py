"""
Metrics computation for pipeline run evaluation.

This module computes quality and cost metrics from a completed pipeline run's
stage data. These metrics are used by the sweep runner to compare different
pipeline configurations (prompt strategies, context modes, agents).

Computed metrics:
  - traceability_score: fraction of requirements that have "covered" or "partial"
    coverage in the traceability matrix (from the trace stage). Higher is better.
    Missing trace rows count as uncovered against the canonical parse-stage
    requirements, so an incomplete trace matrix cannot look artificially perfect.
  - test_pass_rate: placeholder (always 0.0) for future integration with actual
    test execution. Would measure what fraction of generated tests pass.
  - line_coverage: placeholder (always 0.0) for future integration with coverage
    tools. Would measure what fraction of code lines are exercised by tests.
  - critique_accept_rate: fraction of generated tests that the critique stage
    accepted (decision == "accept"). Higher means the generator is producing
    better tests.
  - mapped_requirements_rate / mapping_confidence_avg / faiss_evidence_count:
    map-stage retrieval and symbol-linking indicators. Higher is better.
  - generation_coverage_rate: fraction of parsed requirements that received at
    least one generated test.
  - critique_coverage_rate: fraction of generated tests that received a critique
    score.
  - stage_success_rate: fraction of the six pipeline stages that succeeded.
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


def _clamp_fraction(value: Any) -> float:
    return min(max(_as_number(value), 0.0), 1.0)


def _stage_payload(stages: list[dict[str, Any]], stage_name: str) -> dict[str, Any]:
    for stage in stages:
        if stage.get("stage") == stage_name and isinstance(stage.get("output_payload"), dict):
            return stage["output_payload"]
    return {}


def _requirement_ids(parse_stage: dict[str, Any]) -> list[str]:
    requirements = parse_stage.get("requirements") if isinstance(parse_stage, dict) else None
    if not isinstance(requirements, list):
        return []
    ids = [str(req.get("id")) for req in requirements if isinstance(req, dict) and req.get("id")]
    return list(dict.fromkeys(ids))


def _best_coverage_status(current: str, incoming: str) -> str:
    order = {"uncovered": 0, "partial": 1, "covered": 2}
    return incoming if order.get(incoming, 0) > order.get(current, 0) else current


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
    map_stage = _stage_payload(stages, "map")
    parse_stage = _stage_payload(stages, "parse")
    parsed_requirement_ids = _requirement_ids(parse_stage)

    # Traceability score: what fraction of requirements have test coverage?
    traceability_score = 0.0
    strict_coverage_score = 0.0
    coverage_counts = {"covered": 0, "partial": 0, "uncovered": 0}
    total_requirements = len(parsed_requirement_ids)
    if trace_stage and trace_stage.get("matrix"):
        matrix = trace_stage["matrix"]
        if isinstance(matrix, list):
            coverage_by_requirement = {req_id: "uncovered" for req_id in parsed_requirement_ids}
            for row in matrix:
                if not isinstance(row, dict):
                    continue
                requirement_id = str(row.get("requirement_id") or "")
                if requirement_id not in coverage_by_requirement:
                    continue
                status = str(row.get("coverage_status", "uncovered"))
                if status not in coverage_counts:
                    continue
                if status in {"covered", "partial"} and not row.get("test_files"):
                    status = "uncovered"
                coverage_by_requirement[requirement_id] = _best_coverage_status(
                    coverage_by_requirement[requirement_id],
                    status,
                )
            coverage_counts = {
                status: sum(1 for value in coverage_by_requirement.values() if value == status)
                for status in coverage_counts
            }
            covered_or_partial = coverage_counts["covered"] + coverage_counts["partial"]
            traceability_score = covered_or_partial / total_requirements if total_requirements else 0.0
            strict_coverage_score = coverage_counts["covered"] / total_requirements if total_requirements else 0.0
    trace_matrix_completion_rate = 0.0
    if total_requirements:
        matrix_rows = trace_stage.get("matrix", []) if isinstance(trace_stage.get("matrix"), list) else []
        canonical_rows = {
            str(row.get("requirement_id"))
            for row in matrix_rows
            if isinstance(row, dict) and str(row.get("requirement_id") or "") in parsed_requirement_ids
        }
        trace_matrix_completion_rate = len(canonical_rows) / total_requirements

    # Critique accept rate: what fraction of generated tests were accepted as-is?
    critique_accept_rate = 0.0
    critique_mean_score = 0.0
    critique_scores_count = 0
    if critique_stage and critique_stage.get("scores"):
        scores = critique_stage["scores"]
        if isinstance(scores, list):
            valid_scores = [s for s in scores if isinstance(s, dict)]
            critique_scores_count = len(valid_scores)
            accepted = sum(1 for s in valid_scores if s.get("decision") == "accept")
            critique_accept_rate = accepted / len(valid_scores) if valid_scores else 0.0
            score_values = [
                _clamp_fraction(
                    (_as_number(s.get("relevance"))
                    + _as_number(s.get("completeness"))
                    + _as_number(s.get("correctness")))
                    / 15
                )
                for s in valid_scores
            ]
            critique_mean_score = sum(score_values) / len(score_values) if score_values else 0.0

    generated_tests_count = 0
    generated_requirement_ids: set[str] = set()
    generated_test_files: set[str] = set()
    if generate_stage and isinstance(generate_stage.get("tests"), list):
        generated_tests_count = len(generate_stage["tests"])
        generated_requirement_ids = {
            str(test.get("requirement_id"))
            for test in generate_stage["tests"]
            if isinstance(test, dict) and test.get("requirement_id")
        }
        generated_test_files = {
            str(test.get("file_path"))
            for test in generate_stage["tests"]
            if isinstance(test, dict) and test.get("file_path")
        }
    if (
        generated_tests_count
        and generated_test_files
        and critique_stage
        and isinstance(critique_stage.get("scores"), list)
    ):
        matched_scores = [
            score
            for score in critique_stage["scores"]
            if isinstance(score, dict) and str(score.get("test_file") or "") in generated_test_files
        ]
        critique_scores_count = len(matched_scores)
        accepted = sum(1 for score in matched_scores if score.get("decision") == "accept")
        critique_accept_rate = accepted / critique_scores_count if critique_scores_count else 0.0
        score_values = [
            _clamp_fraction(
                (_as_number(score.get("relevance"))
                + _as_number(score.get("completeness"))
                + _as_number(score.get("correctness")))
                / 15
            )
            for score in matched_scores
        ]
        critique_mean_score = sum(score_values) / len(score_values) if score_values else 0.0
    if generated_tests_count == 0:
        # Critique scores without generated tests are not meaningful evidence.
        critique_scores_count = 0
        critique_accept_rate = 0.0
        critique_mean_score = 0.0
    generation_coverage_rate = (
        len(generated_requirement_ids.intersection(parsed_requirement_ids)) / total_requirements
        if total_requirements
        else 0.0
    )
    critique_coverage_rate = min(critique_scores_count / generated_tests_count, 1.0) if generated_tests_count else 0.0

    mapped_requirements_rate = 0.0
    mapping_confidence_avg = 0.0
    faiss_evidence_count = 0
    faiss_evidence_per_mapping = 0.0
    if map_stage and isinstance(map_stage.get("mappings"), list):
        mappings = [m for m in map_stage["mappings"] if isinstance(m, dict)]
        mapped_requirement_ids = {
            str(m.get("requirement_id"))
            for m in mappings
            if m.get("symbol") and str(m.get("requirement_id")) in parsed_requirement_ids
        }
        confidences = [_clamp_fraction(m.get("confidence")) for m in mappings]
        faiss_evidence_count = sum(
            len(m.get("evidence_snippets") or [])
            for m in mappings
            if isinstance(m.get("evidence_snippets"), list)
        )
        mapped_requirements_rate = len(mapped_requirement_ids) / total_requirements if total_requirements else 0.0
        mapping_confidence_avg = sum(confidences) / len(confidences) if confidences else 0.0
        faiss_evidence_per_mapping = faiss_evidence_count / len(mappings) if mappings else 0.0

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
    stage_success_rate = completed_stages / 6 if stages else 0.0
    quality_score = (
        (traceability_score * 0.30)
        + (mapped_requirements_rate * 0.20)
        + (generation_coverage_rate * 0.15)
        + (critique_accept_rate * 0.15)
        + (critique_mean_score * 0.10)
        + (trace_matrix_completion_rate * 0.05)
        + (stage_success_rate * 0.05)
    )
    if total_requirements == 0:
        quality_score = 0.0

    return {
        "traceability_score": traceability_score,
        "strict_coverage_score": strict_coverage_score,
        "test_pass_rate": 0.0,  # Placeholder for future test execution integration
        "line_coverage": 0.0,  # Placeholder for future coverage tool integration
        "critique_accept_rate": critique_accept_rate,
        "critique_mean_score": critique_mean_score,
        "critique_coverage_rate": critique_coverage_rate,
        "mapped_requirements_rate": mapped_requirements_rate,
        "mapping_confidence_avg": mapping_confidence_avg,
        "faiss_evidence_count": faiss_evidence_count,
        "faiss_evidence_per_mapping": faiss_evidence_per_mapping,
        "generation_coverage_rate": generation_coverage_rate,
        "trace_matrix_completion_rate": trace_matrix_completion_rate,
        "stage_success_rate": stage_success_rate,
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
