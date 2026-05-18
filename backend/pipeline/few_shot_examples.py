# ruff: noqa: E501
"""Curated static few-shot examples for benchmark projects.

These examples are intentionally small and deterministic. They are not pulled
from previous runs, so the `few_shot_static` sweep axis stays stable across
machines and over time.
"""

from __future__ import annotations

from textwrap import dedent

STAGES = ("parse", "analyze", "map", "generate", "critique", "trace")


def _normalize_project_name(name: str) -> str:
    return name.lower().replace("_", "-").replace(" ", "-")


GENERIC_EXAMPLES = {
    "parse": dedent(
        """
        Example output:
        ```json
        {"requirements":[{"id":"REQ-001","title":"Create item","description":"Users can create a valid item.","type":"functional","priority":"high","acceptance_criteria":["Valid input creates a persisted item"],"source_location":"requirements.md:1"}]}
        ```
        """
    ).strip(),
    "analyze": dedent(
        """
        Example output:
        ```json
        {"symbols":[{"qualified_name":"app.service.create_item","kind":"function","file_path":"app/service.py","line_start":10,"line_end":24,"signature":"create_item(data: dict) -> dict","docstring":null}],"project_summary":"Small service with CRUD-style operations."}
        ```
        """
    ).strip(),
    "map": dedent(
        """
        Example output:
        ```json
        {"mappings":[{"requirement_id":"REQ-001","symbol":{"qualified_name":"app.service.create_item","kind":"function","file_path":"app/service.py","line_start":10,"line_end":24,"signature":"create_item(data: dict) -> dict","docstring":null},"confidence":0.9,"rationale":"The function validates input and persists the item.","evidence_snippets":["def create_item(data):"]}]}
        ```
        """
    ).strip(),
    "generate": dedent(
        """
        Example output:
        ```json
        {"tests":[{"requirement_id":"REQ-001","file_path":"tests/test_req001_create_item.py","code":"def test_create_item_persists_valid_input():\\n    result = create_item({'name': 'demo'})\\n    assert result['name'] == 'demo'","target_symbol":"app.service.create_item","rationale":"Covers the successful create path from the requirement."}]}
        ```
        """
    ).strip(),
    "critique": dedent(
        """
        Example output:
        ```json
        {"scores":[{"test_file":"tests/test_req001_create_item.py","relevance":5,"completeness":4,"correctness":5,"decision":"accept","notes":"Directly verifies the required create behavior."}],"revised_tests":[]}
        ```
        """
    ).strip(),
    "trace": dedent(
        """
        Example output:
        ```json
        {"matrix":[{"requirement_id":"REQ-001","symbol":"app.service.create_item","test_files":["tests/test_req001_create_item.py"],"coverage_status":"covered"}],"gap_report_md":"# Traceability Gap Report\\n\\nAll listed requirements are covered."}
        ```
        """
    ).strip(),
}


STATIC_FEW_SHOT_EXAMPLES = {
    "todo-api": {
        "parse": dedent(
            """
            Example output for a todo API:
            ```json
            {"requirements":[{"id":"REQ-001","title":"Create Todo","description":"Users can create a todo with a title and optional description.","type":"functional","priority":"high","acceptance_criteria":["A valid title creates a todo","New todos default to incomplete","Empty titles are rejected"],"source_location":"requirements.md:1"}]}
            ```
            """
        ).strip(),
        "analyze": dedent(
            """
            Example output for a todo API:
            ```json
            {"symbols":[{"qualified_name":"todo_api.create_todo","kind":"function","file_path":"todo_api.py","line_start":12,"line_end":31,"signature":"create_todo(title: str, description: str | None = None) -> dict","docstring":null}],"project_summary":"In-memory todo service exposing create, list, complete, and delete operations."}
            ```
            """
        ).strip(),
        "map": dedent(
            """
            Example output for a todo API:
            ```json
            {"mappings":[{"requirement_id":"REQ-001","symbol":{"qualified_name":"todo_api.create_todo","kind":"function","file_path":"todo_api.py","line_start":12,"line_end":31,"signature":"create_todo(title: str, description: str | None = None) -> dict","docstring":null},"confidence":0.94,"rationale":"create_todo validates title, assigns an id, and stores incomplete todos.","evidence_snippets":["def create_todo(title, description=None):","todo = {'id': next_id, 'title': title, 'completed': False}"]}]}
            ```
            """
        ).strip(),
        "generate": dedent(
            """
            Example output for a todo API:
            ```json
            {"tests":[{"requirement_id":"REQ-001","file_path":"tests/test_req001_create_todo.py","code":"def test_create_todo_defaults_to_incomplete():\\n    todo = create_todo('Buy milk')\\n    assert todo['title'] == 'Buy milk'\\n    assert todo['completed'] is False\\n\\ndef test_create_todo_rejects_empty_title():\\n    with pytest.raises(ValueError):\\n        create_todo('')","target_symbol":"todo_api.create_todo","rationale":"Covers valid creation and required title validation."}]}
            ```
            """
        ).strip(),
        "critique": dedent(
            """
            Example output for a todo API:
            ```json
            {"scores":[{"test_file":"tests/test_req001_create_todo.py","relevance":5,"completeness":5,"correctness":5,"decision":"accept","notes":"Checks title persistence, incomplete default, and invalid empty title behavior."}],"revised_tests":[]}
            ```
            """
        ).strip(),
        "trace": dedent(
            """
            Example output for a todo API:
            ```json
            {"matrix":[{"requirement_id":"REQ-001","symbol":"todo_api.create_todo","test_files":["tests/test_req001_create_todo.py"],"coverage_status":"covered"}],"gap_report_md":"# Traceability Gap Report\\n\\nREQ-001 is covered by tests for successful creation and title validation."}
            ```
            """
        ).strip(),
    },
    "url-shortener": {
        "parse": dedent(
            """
            Example output for a URL shortener:
            ```json
            {"requirements":[{"id":"REQ-001","title":"Shorten URL","description":"Users can submit a valid long URL and receive a short code.","type":"functional","priority":"high","acceptance_criteria":["Valid URLs return a unique code","Invalid URLs are rejected"],"source_location":"requirements.md:1"}]}
            ```
            """
        ).strip(),
        "analyze": dedent(
            """
            Example output for a URL shortener:
            ```json
            {"symbols":[{"qualified_name":"shortener.create_short_url","kind":"function","file_path":"shortener.py","line_start":8,"line_end":27,"signature":"create_short_url(url: str) -> str","docstring":null}],"project_summary":"URL shortening service that validates URLs, stores code mappings, and resolves redirects."}
            ```
            """
        ).strip(),
        "map": dedent(
            """
            Example output for a URL shortener:
            ```json
            {"mappings":[{"requirement_id":"REQ-001","symbol":{"qualified_name":"shortener.create_short_url","kind":"function","file_path":"shortener.py","line_start":8,"line_end":27,"signature":"create_short_url(url: str) -> str","docstring":null},"confidence":0.93,"rationale":"The function validates the input URL and creates a stored short code.","evidence_snippets":["def create_short_url(url):","if not is_valid_url(url): raise ValueError"]}]}
            ```
            """
        ).strip(),
        "generate": dedent(
            """
            Example output for a URL shortener:
            ```json
            {"tests":[{"requirement_id":"REQ-001","file_path":"tests/test_req001_shorten_url.py","code":"def test_create_short_url_returns_code_for_valid_url():\\n    code = create_short_url('https://example.com/page')\\n    assert isinstance(code, str)\\n    assert resolve_short_url(code) == 'https://example.com/page'\\n\\ndef test_create_short_url_rejects_invalid_url():\\n    with pytest.raises(ValueError):\\n        create_short_url('not-a-url')","target_symbol":"shortener.create_short_url","rationale":"Covers code creation, persistence, resolution, and invalid input."}]}
            ```
            """
        ).strip(),
        "critique": dedent(
            """
            Example output for a URL shortener:
            ```json
            {"scores":[{"test_file":"tests/test_req001_shorten_url.py","relevance":5,"completeness":5,"correctness":5,"decision":"accept","notes":"Validates both the successful shortening path and invalid URL rejection."}],"revised_tests":[]}
            ```
            """
        ).strip(),
        "trace": dedent(
            """
            Example output for a URL shortener:
            ```json
            {"matrix":[{"requirement_id":"REQ-001","symbol":"shortener.create_short_url","test_files":["tests/test_req001_shorten_url.py"],"coverage_status":"covered"}],"gap_report_md":"# Traceability Gap Report\\n\\nREQ-001 is covered for valid URL shortening and invalid URL rejection."}
            ```
            """
        ).strip(),
    },
    "calculator": {
        "parse": dedent(
            """
            Example output for a calculator:
            ```json
            {"requirements":[{"id":"REQ-001","title":"Add Numbers","description":"Users can add two numeric values and receive their sum.","type":"functional","priority":"high","acceptance_criteria":["Positive numbers add correctly","Negative numbers add correctly"],"source_location":"requirements.md:1"}]}
            ```
            """
        ).strip(),
        "analyze": dedent(
            """
            Example output for a calculator:
            ```json
            {"symbols":[{"qualified_name":"calculator.add","kind":"function","file_path":"calculator.py","line_start":3,"line_end":4,"signature":"add(a: float, b: float) -> float","docstring":"Return the sum of two numbers."}],"project_summary":"Small arithmetic module exposing addition, subtraction, multiplication, and division helpers."}
            ```
            """
        ).strip(),
        "map": dedent(
            """
            Example output for a calculator:
            ```json
            {"mappings":[{"requirement_id":"REQ-001","symbol":{"qualified_name":"calculator.add","kind":"function","file_path":"calculator.py","line_start":3,"line_end":4,"signature":"add(a: float, b: float) -> float","docstring":"Return the sum of two numbers."},"confidence":0.98,"rationale":"The add function directly implements numeric addition.","evidence_snippets":["def add(a, b): return a + b"]}]}
            ```
            """
        ).strip(),
        "generate": dedent(
            """
            Example output for a calculator:
            ```json
            {"tests":[{"requirement_id":"REQ-001","file_path":"tests/test_req001_add_numbers.py","code":"def test_add_positive_numbers():\\n    assert add(2, 3) == 5\\n\\ndef test_add_negative_numbers():\\n    assert add(-2, -3) == -5","target_symbol":"calculator.add","rationale":"Covers positive and negative addition acceptance criteria."}]}
            ```
            """
        ).strip(),
        "critique": dedent(
            """
            Example output for a calculator:
            ```json
            {"scores":[{"test_file":"tests/test_req001_add_numbers.py","relevance":5,"completeness":4,"correctness":5,"decision":"accept","notes":"Covers core addition behavior for positive and negative operands."}],"revised_tests":[]}
            ```
            """
        ).strip(),
        "trace": dedent(
            """
            Example output for a calculator:
            ```json
            {"matrix":[{"requirement_id":"REQ-001","symbol":"calculator.add","test_files":["tests/test_req001_add_numbers.py"],"coverage_status":"covered"}],"gap_report_md":"# Traceability Gap Report\\n\\nREQ-001 is covered by positive and negative addition tests."}
            ```
            """
        ).strip(),
    },
}


def get_static_examples(project_name: str, stage: str, prompt_strategy: str) -> str:
    """Return curated examples only for the static few-shot strategy."""
    if prompt_strategy != "few_shot_static":
        return ""
    normalized = _normalize_project_name(project_name)
    examples = STATIC_FEW_SHOT_EXAMPLES.get(normalized, GENERIC_EXAMPLES)
    return examples.get(stage, GENERIC_EXAMPLES.get(stage, ""))
