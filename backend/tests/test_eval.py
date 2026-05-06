"""
Tests for the evaluation engine: metrics computation and statistical analysis.
Uses realistic data structures to validate the eval pipeline end-to-end.
"""
import pytest
import numpy as np
from eval.metrics import compute_metrics
from eval.stats import run_statistical_analysis, generate_markdown_report


class TestComputeMetrics:
    """Test metrics computation from stage data."""

    def test_empty_stages(self):
        result = compute_metrics({"stages": []})
        assert result["traceability_score"] == 0.0
        assert result["critique_accept_rate"] == 0.0
        assert result["latency_total_ms"] == 0

    def test_traceability_all_covered(self):
        result = compute_metrics({"stages": [
            {"stage": "trace", "output_payload": {"matrix": [
                {"requirement_id": "REQ-001", "coverage_status": "covered"},
                {"requirement_id": "REQ-002", "coverage_status": "covered"},
                {"requirement_id": "REQ-003", "coverage_status": "covered"},
            ]}, "latency_ms": 100, "token_usage": {}},
        ]})
        assert result["traceability_score"] == 1.0

    def test_traceability_mixed(self):
        result = compute_metrics({"stages": [
            {"stage": "trace", "output_payload": {"matrix": [
                {"requirement_id": "REQ-001", "coverage_status": "covered"},
                {"requirement_id": "REQ-002", "coverage_status": "partial"},
                {"requirement_id": "REQ-003", "coverage_status": "uncovered"},
                {"requirement_id": "REQ-004", "coverage_status": "uncovered"},
            ]}, "latency_ms": 0, "token_usage": {}},
        ]})
        assert result["traceability_score"] == 0.5  # 2 out of 4

    def test_traceability_none_covered(self):
        result = compute_metrics({"stages": [
            {"stage": "trace", "output_payload": {"matrix": [
                {"requirement_id": "REQ-001", "coverage_status": "uncovered"},
                {"requirement_id": "REQ-002", "coverage_status": "uncovered"},
            ]}, "latency_ms": 0, "token_usage": {}},
        ]})
        assert result["traceability_score"] == 0.0

    def test_critique_accept_rate(self):
        result = compute_metrics({"stages": [
            {"stage": "critique", "output_payload": {"scores": [
                {"decision": "accept"},
                {"decision": "accept"},
                {"decision": "revise"},
                {"decision": "reject"},
            ]}, "latency_ms": 200, "token_usage": {}},
        ]})
        assert result["critique_accept_rate"] == 0.5  # 2 of 4

    def test_critique_all_accept(self):
        result = compute_metrics({"stages": [
            {"stage": "critique", "output_payload": {"scores": [
                {"decision": "accept"},
                {"decision": "accept"},
                {"decision": "accept"},
            ]}, "latency_ms": 0, "token_usage": {}},
        ]})
        assert result["critique_accept_rate"] == 1.0

    def test_latency_sums(self):
        result = compute_metrics({"stages": [
            {"stage": "parse", "latency_ms": 100, "token_usage": {}},
            {"stage": "analyze", "latency_ms": 200, "token_usage": {}},
            {"stage": "map", "latency_ms": 300, "token_usage": {}},
            {"stage": "generate", "latency_ms": 400, "token_usage": {}},
            {"stage": "critique", "latency_ms": 150, "token_usage": {}},
            {"stage": "trace", "latency_ms": 50, "token_usage": {}},
        ]})
        assert result["latency_total_ms"] == 1200

    def test_token_usage_sums(self):
        result = compute_metrics({"stages": [
            {"stage": "parse", "latency_ms": 0, "token_usage": {"input": 500, "output": 200}},
            {"stage": "analyze", "latency_ms": 0, "token_usage": {"input": 800, "output": 400}},
        ]})
        assert result["tokens_total"] == 1900

    def test_full_realistic_run(self):
        """Simulate a realistic complete 6-stage run."""
        result = compute_metrics({"stages": [
            {"stage": "parse", "latency_ms": 2100, "token_usage": {"input": 1200, "output": 800}},
            {"stage": "analyze", "latency_ms": 5400, "token_usage": {"input": 3000, "output": 2500}},
            {"stage": "map", "latency_ms": 3200, "token_usage": {"input": 2800, "output": 1500}},
            {"stage": "generate", "latency_ms": 8700, "token_usage": {"input": 4500, "output": 6000}},
            {"stage": "critique", "output_payload": {"scores": [
                {"decision": "accept"}, {"decision": "accept"},
                {"decision": "revise"}, {"decision": "accept"},
                {"decision": "reject"},
            ]}, "latency_ms": 4100, "token_usage": {"input": 3500, "output": 2000}},
            {"stage": "trace", "output_payload": {"matrix": [
                {"requirement_id": "REQ-001", "coverage_status": "covered"},
                {"requirement_id": "REQ-002", "coverage_status": "covered"},
                {"requirement_id": "REQ-003", "coverage_status": "partial"},
                {"requirement_id": "REQ-004", "coverage_status": "uncovered"},
                {"requirement_id": "REQ-005", "coverage_status": "covered"},
            ]}, "latency_ms": 1800, "token_usage": {"input": 1500, "output": 900}},
        ]})
        assert result["traceability_score"] == 0.8  # 4 of 5 (3 covered + 1 partial)
        assert result["critique_accept_rate"] == 0.6  # 3 of 5
        assert result["latency_total_ms"] == 25300
        assert result["tokens_total"] == 30200


class TestStatisticalAnalysis:
    """Test the ANOVA + pairwise t-test statistical analysis."""

    def test_insufficient_data(self):
        result = run_statistical_analysis([{"prompt_strategy": "zero_shot", "traceability_score": 0.5}])
        assert "note" in result

    def test_two_strategy_comparison(self):
        data = [
            {"prompt_strategy": "zero_shot", "context_mode": "full", "traceability_score": 0.5, "test_pass_rate": 0.4, "critique_accept_rate": 0.6},
            {"prompt_strategy": "zero_shot", "context_mode": "full", "traceability_score": 0.55, "test_pass_rate": 0.45, "critique_accept_rate": 0.65},
            {"prompt_strategy": "chain_of_thought", "context_mode": "full", "traceability_score": 0.8, "test_pass_rate": 0.7, "critique_accept_rate": 0.85},
            {"prompt_strategy": "chain_of_thought", "context_mode": "full", "traceability_score": 0.85, "test_pass_rate": 0.75, "critique_accept_rate": 0.9},
        ]
        result = run_statistical_analysis(data)
        assert "anova" in result
        # With such distinct groups, ANOVA should detect a difference
        for key in result["anova"]:
            assert "f_statistic" in result["anova"][key]
            assert "p_value" in result["anova"][key]
            assert "eta_squared" in result["anova"][key]

    def test_four_strategy_full_sweep(self):
        """Simulate a realistic 16-config sweep and run full analysis."""
        np.random.seed(42)
        strategies = ["zero_shot", "chain_of_thought", "few_shot_static", "few_shot_dynamic"]
        contexts = ["minimal", "local", "module", "full"]
        base_scores = {"zero_shot": 0.55, "chain_of_thought": 0.70, "few_shot_static": 0.73, "few_shot_dynamic": 0.80}

        data = []
        for strategy in strategies:
            for context in contexts:
                context_bonus = {"minimal": 0.0, "local": 0.05, "module": 0.10, "full": 0.15}[context]
                score = base_scores[strategy] + context_bonus + np.random.normal(0, 0.02)
                data.append({
                    "prompt_strategy": strategy, "context_mode": context,
                    "traceability_score": min(max(score, 0), 1),
                    "test_pass_rate": min(max(score * 0.9, 0), 1),
                    "critique_accept_rate": min(max(score * 0.85, 0), 1),
                })

        result = run_statistical_analysis(data)

        # With 4 clearly different strategies, ANOVA should be significant
        assert "anova" in result
        anova_keys = list(result["anova"].keys())
        assert len(anova_keys) > 0

        for key in anova_keys:
            assert result["anova"][key]["p_value"] < 0.05, f"ANOVA should be significant for {key}"
            assert result["anova"][key]["eta_squared"] > 0.0

        # Should have pairwise comparisons since ANOVA is significant
        assert "pairwise" in result
        assert len(result["pairwise"]) > 0

    def test_markdown_report_generation(self):
        data = [
            {"prompt_strategy": "zero_shot", "context_mode": "full", "traceability_score": 0.5, "test_pass_rate": 0.4, "critique_accept_rate": 0.3},
            {"prompt_strategy": "chain_of_thought", "context_mode": "full", "traceability_score": 0.9, "test_pass_rate": 0.8, "critique_accept_rate": 0.85},
        ]
        stats = run_statistical_analysis(data)
        md = generate_markdown_report(stats)
        assert "# Statistical Analysis Report" in md
        assert "ANOVA" in md

    def test_identical_groups_not_significant(self):
        data = [
            {"prompt_strategy": "a", "context_mode": "full", "traceability_score": 0.5, "test_pass_rate": 0.5, "critique_accept_rate": 0.5},
            {"prompt_strategy": "a", "context_mode": "full", "traceability_score": 0.5, "test_pass_rate": 0.5, "critique_accept_rate": 0.5},
            {"prompt_strategy": "b", "context_mode": "full", "traceability_score": 0.5, "test_pass_rate": 0.5, "critique_accept_rate": 0.5},
            {"prompt_strategy": "b", "context_mode": "full", "traceability_score": 0.5, "test_pass_rate": 0.5, "critique_accept_rate": 0.5},
        ]
        result = run_statistical_analysis(data)
        # Identical values -> no significant difference
        for key in result.get("anova", {}):
            assert result["anova"][key]["p_value"] >= 0.05 or result["anova"][key]["f_statistic"] == 0.0
