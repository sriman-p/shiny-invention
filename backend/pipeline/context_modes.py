"""
Context mode builder for pipeline stage prompts.

Context modes control how much surrounding information is included when the
pipeline constructs prompts for AI agents. This is important because:
  - Too little context means the agent may miss important relationships
  - Too much context wastes tokens and can confuse the agent

The four modes, from least to most context:
  1. "minimal" -- Only the requirement text and the target symbol. Cheapest
     and fastest, but the agent has no surrounding code context.
  2. "local" -- Adds same-file siblings (other functions/classes in the same file).
     Gives the agent a sense of the symbol's immediate neighborhood.
  3. "module" -- Adds the full module text. The agent can see imports, constants,
     and all code in the module to understand the symbol's role.
  4. "full" -- Adds a project summary on top of module context. The agent gets
     the complete picture of the project's purpose and architecture.

These modes are used primarily by the Map and Generate stages, where the agent
needs to understand code context to produce accurate mappings and tests.
Sweeps can compare modes to find the best accuracy/cost trade-off for a project.
"""


def build_context(
    mode: str,
    *,
    requirement_text: str,
    symbol_text: str = "",
    siblings: str = "",
    module_text: str = "",
    project_summary: str = "",
) -> str:
    """
    Assemble a context string based on the selected mode.

    Args:
        mode: One of "minimal", "local", "module", or "full".
        requirement_text: The requirement being processed.
        symbol_text: The target code symbol's signature/docstring.
        siblings: Other symbols in the same file (for "local" mode).
        module_text: Full source text of the module (for "module"/"full" modes).
        project_summary: High-level project description (for "full" mode only).

    Returns:
        A formatted string combining the relevant context sections.
    """
    if mode == "minimal":
        return f"Requirement:\n{requirement_text}\n\nSymbol:\n{symbol_text}"

    if mode == "local":
        return f"Requirement:\n{requirement_text}\n\nSymbol:\n{symbol_text}\n\nSame-file siblings:\n{siblings}"

    if mode == "module":
        return f"Requirement:\n{requirement_text}\n\nSymbol:\n{symbol_text}\n\nFull module:\n{module_text}"

    # "full" mode: include everything, starting with the project overview
    return (
        f"Project summary:\n{project_summary}\n\n"
        f"Requirement:\n{requirement_text}\n\n"
        f"Symbol:\n{symbol_text}\n\n"
        f"Full module:\n{module_text}"
    )


# Canonical list of valid context modes, used for validation and iteration.
CONTEXT_MODES = ["minimal", "local", "module", "full"]
