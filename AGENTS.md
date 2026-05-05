# AGENTS.md

## Cursor Cloud specific instructions

This is a Python project (skeleton/new). The `.gitignore` is configured for Python with Django, Flask, Celery, Redis, and RabbitMQ patterns.

### Environment

- **Python**: 3.12 (system), virtual environment at `.venv/`
- **Package manager**: pip (no `requirements.txt` or `pyproject.toml` committed yet)
- Activate the venv before any Python command: `source .venv/bin/activate`

### Dev tooling available in the venv

| Tool | Purpose | Command |
|------|---------|---------|
| ruff | Linting & formatting | `ruff check .` / `ruff format .` |
| mypy | Type checking | `mypy --ignore-missing-imports .` |
| pytest | Testing | `pytest` |

### Gotchas

- The base VM image may not have `python3.12-venv` installed. The update script handles creating the venv if missing.
- There is no application code yet — all lint/type/test commands will report "no files" until source files are added.
- When a `requirements.txt` or `pyproject.toml` is added to the repo, the update script will automatically install dependencies from it.
