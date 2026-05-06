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
            '{examples}\n\nNow extract from:\nSchema: {schema}\n\nDocument:\n{document}'
        ),
        "analyze": (
            "Analyze the codebase. Examples:\n{examples}\n\n"
            "Codebase at {code_path}.\nOutput JSON matching: {schema}"
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
        "critique": (
            "Critique tests. Examples:\n{examples}\n\n"
            "Tests:\n{tests}\n\nOutput JSON matching: {schema}"
        ),
        "trace": (
            "Build traceability matrix. Examples:\n{examples}\n\n"
            "Requirements:\n{requirements}\n\nTests:\n{tests}\n\nOutput JSON matching: {schema}"
        ),
    },
    "few_shot_dynamic": {
        "parse": (
            "Extract requirements from the document. Here are similar examples from this project:\n\n"
            '{dynamic_examples}\n\nSchema: {schema}\n\nDocument:\n{document}'
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
    return PROMPT_STRATEGIES.get(strategy, PROMPT_STRATEGIES["zero_shot"]).get(stage, "")
