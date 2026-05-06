"""
Prompt templates for each pipeline stage, organized by prompt strategy.

This module defines the actual text prompts sent to AI agents. Each prompt
strategy has a different approach to eliciting good responses:

  - zero_shot: Direct instructions with no examples. Simplest and cheapest,
    but relies entirely on the agent's training data.

  - chain_of_thought: Prefixes instructions with "Think step by step" to
    encourage the agent to reason through the problem before answering.
    Often produces more accurate results at the cost of more tokens.

  - few_shot_static: Includes hardcoded example outputs in the prompt so
    the agent can see what correct output looks like. Examples are the same
    regardless of the project being analyzed.

  - few_shot_dynamic: Similar to few_shot_static, but examples are retrieved
    from the specific project being analyzed (e.g., previous runs). This can
    produce the most contextually relevant outputs.

Templates use Python string formatting placeholders:
  - {schema}: JSON schema of the expected output structure
  - {document}: raw requirements document text
  - {code_path}: path to the project's source code
  - {requirements}: formatted list of requirements
  - {symbols}: formatted list of code symbols
  - {retrieval_hints}: hybrid retrieval results from the FAISS+BM25 index
  - {mappings}: requirement-to-code mappings
  - {tests}: generated test descriptions
  - {few_shot_examples}: in-project examples for style reference
  - {examples}: static few-shot examples
  - {dynamic_examples}: project-specific few-shot examples

The get_prompt_template() function looks up the correct template by strategy
and stage, falling back to zero_shot if the requested strategy is not found.
"""

PROMPT_STRATEGIES = {
    "zero_shot": {
        "parse": (
            "Extract all requirements from the following requirements document. "
            "Output JSON matching the schema below.\n\n"
            "Schema: {schema}\n\nDocument:\n{document}"
        ),
        "analyze": (
            "Walk this codebase at {code_path}. Use your file-reading tools. "
            "Return a symbol inventory (functions, classes, methods with file paths, line numbers, signatures) "
            "and a 1-paragraph project summary.\n\nOutput JSON matching: {schema}"
        ),
        "map": (
            "For each requirement below, identify the implementing code symbol(s) from the symbol inventory. "
            "Use this hybrid retrieval shortlist as a hint:\n{retrieval_hints}\n\n"
            "Requirements:\n{requirements}\n\nSymbols:\n{symbols}\n\n"
            "Output JSON matching: {schema}"
        ),
        "generate": (
            "For each requirement-to-symbol mapping below, generate pytest test(s). "
            "Use these in-project examples as style reference:\n{few_shot_examples}\n\n"
            "Mappings:\n{mappings}\n\nOutput JSON matching: {schema}"
        ),
        "critique": (
            "Score each generated test on relevance, completeness, and correctness (1-5). "
            "Decide: accept, revise, or reject. For revised tests, rewrite them.\n\n"
            "Tests:\n{tests}\n\nOutput JSON matching: {schema}"
        ),
        "trace": (
            "Build a traceability matrix mapping requirements to test files. "
            "Identify coverage gaps and produce a Markdown gap report.\n\n"
            "Requirements:\n{requirements}\n\nTests:\n{tests}\n\n"
            "Output JSON matching: {schema}"
        ),
    },
    "chain_of_thought": {
        "parse": (
            "Think step by step. Extract all requirements from the document below. "
            "First identify sections, then extract each requirement with its details.\n\n"
            "Schema: {schema}\n\nDocument:\n{document}"
        ),
        "analyze": (
            "Think step by step. Walk the codebase at {code_path}. "
            "First list the files, then identify key symbols in each.\n\nOutput JSON matching: {schema}"
        ),
        "map": (
            "Think step by step. For each requirement, reason about which symbol implements it. "
            "Consider the retrieval hints:\n{retrieval_hints}\n\n"
            "Requirements:\n{requirements}\n\nSymbols:\n{symbols}\n\nOutput JSON matching: {schema}"
        ),
        "generate": (
            "Think step by step. For each mapping, design test cases before writing code.\n\n"
            "Examples:\n{few_shot_examples}\n\nMappings:\n{mappings}\n\nOutput JSON matching: {schema}"
        ),
        "critique": (
            "Think step by step. Evaluate each test carefully before scoring.\n\n"
            "Tests:\n{tests}\n\nOutput JSON matching: {schema}"
        ),
        "trace": (
            "Think step by step. Map each requirement to its test coverage.\n\n"
            "Requirements:\n{requirements}\n\nTests:\n{tests}\n\nOutput JSON matching: {schema}"
        ),
    },
    "few_shot_static": {
        "parse": (
            "Extract requirements from the document. Here are examples of correct output:\n\n"
            "{examples}\n\nNow extract from:\nSchema: {schema}\n\nDocument:\n{document}"
        ),
        "analyze": (
            "Analyze the codebase. Examples:\n{examples}\n\nCodebase at {code_path}.\nOutput JSON matching: {schema}"
        ),
        "map": (
            "Map requirements to symbols. Examples:\n{examples}\n\n"
            "Hints:\n{retrieval_hints}\n\nRequirements:\n{requirements}\n\n"
            "Symbols:\n{symbols}\n\nOutput JSON matching: {schema}"
        ),
        "generate": (
            "Generate tests. Examples:\n{examples}\n\n"
            "Style reference:\n{few_shot_examples}\n\nMappings:\n{mappings}\n\nOutput JSON matching: {schema}"
        ),
        "critique": ("Critique tests. Examples:\n{examples}\n\nTests:\n{tests}\n\nOutput JSON matching: {schema}"),
        "trace": (
            "Build traceability matrix. Examples:\n{examples}\n\n"
            "Requirements:\n{requirements}\n\nTests:\n{tests}\n\nOutput JSON matching: {schema}"
        ),
    },
    "few_shot_dynamic": {
        "parse": (
            "Extract requirements from the document. Here are similar examples from this project:\n\n"
            "{dynamic_examples}\n\nSchema: {schema}\n\nDocument:\n{document}"
        ),
        "analyze": (
            "Analyze the codebase. Similar analyses:\n{dynamic_examples}\n\n"
            "Codebase at {code_path}.\nOutput JSON matching: {schema}"
        ),
        "map": (
            "Map requirements to symbols. Similar mappings:\n{dynamic_examples}\n\n"
            "Hints:\n{retrieval_hints}\n\nRequirements:\n{requirements}\n\n"
            "Symbols:\n{symbols}\n\nOutput JSON matching: {schema}"
        ),
        "generate": (
            "Generate tests. Project-specific examples:\n{dynamic_examples}\n\n"
            "Mappings:\n{mappings}\n\nOutput JSON matching: {schema}"
        ),
        "critique": (
            "Critique tests. Project-specific examples:\n{dynamic_examples}\n\n"
            "Tests:\n{tests}\n\nOutput JSON matching: {schema}"
        ),
        "trace": (
            "Build traceability matrix. Similar reports:\n{dynamic_examples}\n\n"
            "Requirements:\n{requirements}\n\nTests:\n{tests}\n\nOutput JSON matching: {schema}"
        ),
    },
}


def get_prompt_template(strategy: str, stage: str) -> str:
    """
    Retrieve the prompt template for a given strategy and stage.

    Falls back to the zero_shot strategy if the requested strategy is not found,
    and returns an empty string if the stage is not found within the strategy.

    Args:
        strategy: The prompt strategy name (e.g., "zero_shot", "chain_of_thought").
        stage: The pipeline stage name (e.g., "parse", "analyze", "map").

    Returns:
        A format string with placeholders ready for .format() substitution.
    """
    return PROMPT_STRATEGIES.get(strategy, PROMPT_STRATEGIES["zero_shot"]).get(stage, "")
