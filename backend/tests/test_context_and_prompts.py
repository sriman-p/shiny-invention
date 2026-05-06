"""
Tests for context mode builder and prompt template system.
Validates that different modes produce correctly structured output
and that all 4 strategies x 6 stages have templates.
"""
import pytest
from pipeline.context_modes import build_context, CONTEXT_MODES
from pipeline.prompts import get_prompt_template, PROMPT_STRATEGIES


class TestContextModes:
    def test_all_modes_defined(self):
        assert CONTEXT_MODES == ["minimal", "local", "module", "full"]

    def test_minimal_only_has_requirement_and_symbol(self):
        result = build_context("minimal", requirement_text="Add numbers", symbol_text="def add()")
        assert "Add numbers" in result
        assert "def add()" in result
        assert "siblings" not in result.lower()
        assert "module" not in result.lower()
        assert "summary" not in result.lower()

    def test_local_includes_siblings(self):
        result = build_context("local", requirement_text="R", symbol_text="S", siblings="sibling_func()")
        assert "sibling_func()" in result
        assert "R" in result
        assert "S" in result

    def test_module_includes_full_module(self):
        result = build_context("module", requirement_text="R", symbol_text="S", module_text="import os\nclass Foo: pass")
        assert "import os" in result
        assert "class Foo" in result

    def test_full_includes_project_summary(self):
        result = build_context("full", requirement_text="R", symbol_text="S",
                               module_text="code here", project_summary="A calculator app")
        assert "A calculator app" in result
        assert "code here" in result
        assert "R" in result

    def test_context_length_increases_with_mode(self):
        """More context mode = longer prompt. This validates the hierarchy."""
        lengths = {}
        for mode in CONTEXT_MODES:
            result = build_context(
                mode, requirement_text="requirement text here",
                symbol_text="def add(a, b): return a + b",
                siblings="def subtract(a, b): return a - b",
                module_text="import math\n\nclass Calculator:\n    def add(a, b): return a + b\n    def subtract(a, b): return a - b",
                project_summary="This is a calculator application that performs basic arithmetic.",
            )
            lengths[mode] = len(result)

        assert lengths["minimal"] < lengths["local"]
        assert lengths["local"] < lengths["module"]
        assert lengths["module"] < lengths["full"]


class TestPromptStrategies:
    STAGES = ["parse", "analyze", "map", "generate", "critique", "trace"]

    def test_all_four_strategies_exist(self):
        assert set(PROMPT_STRATEGIES.keys()) == {"zero_shot", "chain_of_thought", "few_shot_static", "few_shot_dynamic"}

    def test_all_strategies_cover_all_stages(self):
        for strategy in PROMPT_STRATEGIES:
            for stage in self.STAGES:
                template = get_prompt_template(strategy, stage)
                assert template, f"Missing template for {strategy}/{stage}"
                assert len(template) > 20, f"Template too short for {strategy}/{stage}"

    def test_zero_shot_has_no_examples_keyword(self):
        for stage in self.STAGES:
            t = get_prompt_template("zero_shot", stage)
            assert "examples" not in t.lower() or "{" in t  # Only format placeholders, not real examples

    def test_chain_of_thought_mentions_step_by_step(self):
        for stage in self.STAGES:
            t = get_prompt_template("chain_of_thought", stage)
            assert "step by step" in t.lower()

    def test_few_shot_static_mentions_examples(self):
        for stage in self.STAGES:
            t = get_prompt_template("few_shot_static", stage)
            assert "{examples}" in t

    def test_few_shot_dynamic_mentions_dynamic_examples(self):
        for stage in self.STAGES:
            t = get_prompt_template("few_shot_dynamic", stage)
            assert "{dynamic_examples}" in t

    def test_parse_template_has_schema_and_document(self):
        t = get_prompt_template("zero_shot", "parse")
        assert "{schema}" in t
        assert "{document}" in t

    def test_map_template_has_retrieval_hints(self):
        t = get_prompt_template("zero_shot", "map")
        assert "{retrieval_hints}" in t

    def test_unknown_strategy_falls_back(self):
        t = get_prompt_template("nonexistent_strategy", "parse")
        # Should fall back to zero_shot
        assert "{schema}" in t
