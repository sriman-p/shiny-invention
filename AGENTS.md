# AGENTS.md

## Cursor Cloud specific instructions

ReqLens is a requirement-traced test generation tool: Django 5.x backend + Next.js 15 frontend monorepo.

### Services

| Service | Command | Port |
|---------|---------|------|
| Backend (Django) | `make dev-backend` or `cd backend && uv run python manage.py runserver 8000` | 8000 |
| Frontend (Next.js) | `make dev-frontend` or `cd frontend && corepack enable && pnpm dev` | 3000 |

### Common tasks

- `make install` — install all dependencies (backend + frontend)
- `make migrate` — run Django migrations
- `make seed` — seed benchmark projects (calculator, url-shortener, todo-api)
- `make test` — run backend pytest + frontend lint
- `make lint` — ruff + ruff format check (backend) + eslint (frontend)

### Backend details

- Managed with `uv`; virtual env at `backend/.venv/`
- Always prefix backend commands with `cd backend && uv run ...`
- SQLite database at `backend/data/reqlens.db` — auto-created on migrate
- Lint: `cd backend && uv run ruff check .` — migrations excluded in pyproject.toml
- Tests: `cd backend && uv run pytest -v`
- All LLM interactions use ACP (Agent Client Protocol); no direct SDK calls

### Frontend details

- Next.js (App Router) + React 19 + shadcn/ui (v4) + Tailwind v4
- Package manager: **pnpm** via Corepack (`frontend/package.json` `packageManager`; pnpm 9 so Node 20.9+ works)
- Lint: `cd frontend && corepack enable && pnpm lint`
- Build: `cd frontend && corepack enable && pnpm build`

### Gotchas

- The VM may not have `python3.12-venv` pre-installed; the update script handles this.
- Node.js >=20.9 (Next requirement). Use **`make`** targets for the frontend (`corepack enable` picks pnpm from `frontend/package.json`); global Homebrew **pnpm 11** needs Node 22+ (`node:sqlite`).
- ACP agents (claude-code, codex, gemini, etc.) are not installed in the Cloud VM; the Agent Registry page shows them as "Missing" which is expected. The app functions fully for configuration and UI work without them.
- Django runs in a background thread for pipeline execution (no Celery). Long-running operations won't block the dev server.
- The `geist` font package provides both sans and mono fonts used in the frontend layout.
- **Background task supervision:** `core/apps.py:CoreConfig.ready()` runs `reap_stale_background_tasks()` on startup, marking any `Run`/`Sweep` whose heartbeat is older than 5 minutes as `failed`. The reaper deliberately skips the `migrate`/`makemigrations`/`collectstatic` commands and the pytest harness; it only fires for `runserver` and other long-running processes.
- **Cancellation interrupts agents:** `POST /runs/<id>/cancel` flips the DB row; the orchestrator's parallel `_cancel_watcher` polls every 1s and calls `task.cancel()`, which propagates into `acp_client/runner.py` where the agent subprocess is `terminate()`d (then `kill()`ed after 2s if it doesn't exit).
- **Permission round-trip:** non-`auto` permission modes broadcast `permission_required` SSE events and pause the stage on a future. The frontend run page renders a `<PermissionPromptCard>`; resolving it via `POST /runs/<id>/permissions/<prompt_id>` calls `acp_client.permissions.resolve_permission` and unblocks the stage.
- **SSE replay:** `_broadcast` keeps a per-key bounded deque (last 200 events) annotated with monotonic `seq` ids. The EventSource `id:` field flows back to clients as `Last-Event-ID` on reconnect so events aren't lost.
- **Sweep matrix is multi-axis and parallel:** every cell is `(agent_id, model_id, prompt_strategy, context_mode)`. `POST /projects/<id>/sweeps/preview` accepts an `axes` payload and returns the flat matrix it would execute. The runner queues every cell up front and executes up to `SWEEP_MAX_CONCURRENCY` runs concurrently (default 4), so a full 4x4 strategy/context sweep runs in four-run batches unless overridden. `compute_baseline_diff` provides "Lift vs Worst" deltas for the UI.
