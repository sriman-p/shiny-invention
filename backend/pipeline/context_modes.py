def build_context(
    mode: str,
    *,
    requirement_text: str,
    symbol_text: str = "",
    siblings: str = "",
    module_text: str = "",
    project_summary: str = "",
) -> str:
    if mode == "minimal":
        return f"Requirement:\n{requirement_text}\n\nSymbol:\n{symbol_text}"

    if mode == "local":
        return (
            f"Requirement:\n{requirement_text}\n\n"
            f"Symbol:\n{symbol_text}\n\n"
            f"Same-file siblings:\n{siblings}"
        )

    if mode == "module":
        return (
            f"Requirement:\n{requirement_text}\n\n"
            f"Symbol:\n{symbol_text}\n\n"
            f"Full module:\n{module_text}"
        )

    # full
    return (
        f"Project summary:\n{project_summary}\n\n"
        f"Requirement:\n{requirement_text}\n\n"
        f"Symbol:\n{symbol_text}\n\n"
        f"Full module:\n{module_text}"
    )


CONTEXT_MODES = ["minimal", "local", "module", "full"]
