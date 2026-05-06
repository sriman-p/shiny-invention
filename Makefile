# =============================================================================
# ReqLens Development Makefile
#
# Provides convenient shortcuts for common development tasks. All backend
# commands use `uv run` to ensure the correct virtual environment and
# dependencies are used. Frontend uses Corepack-driven pnpm from
# frontend/package.json "packageManager" (pnpm 9 works on Node 20+;
# global Homebrew pnpm 11 requires Node 22+).
#
# Usage: make <target>
# =============================================================================

.PHONY: install dev-backend dev-frontend migrate seed sweep test lint

# Django dev server: first attempted port (see dev-backend).
BACKEND_PORT ?= 8000

# -- Setup & Dependencies ----------------------------------------------------

# Install all dependencies for both backend and frontend.
# Backend uses uv (Python package manager) and frontend uses pnpm (Node).
# Run this first after cloning the repository.
install:
	cd backend && uv sync
	cd backend/acp_client/cursor_sdk && npm install
	cd frontend && corepack enable && CI=1 pnpm install

# -- Development Servers ------------------------------------------------------

# Start the Django development server on the first free port in
# [BACKEND_PORT, BACKEND_PORT + 9] (defaults from 8000) so an old runserver
# does not block startup. Logs show the chosen port. Example: BACKEND_PORT=9000 make dev-backend
dev-backend:
	cd backend && PORT=$$(uv run python pick_free_port.py --start $(BACKEND_PORT)) && uv run python manage.py runserver $$PORT

# Start the frontend development server (typically on port 3000).
# Proxies API requests to the backend server.
dev-frontend:
	cd frontend && corepack enable && pnpm dev

# -- Database -----------------------------------------------------------------

# Apply all pending Django database migrations.
# Run this after pulling changes that include new migrations, or after
# initial setup to create the SQLite database schema.
migrate:
	cd backend && uv run python manage.py migrate

# Seed the database with benchmark projects (calculator, url-shortener, todo-api).
# These projects are used for development testing and sweep benchmarking.
# Idempotent: safe to run multiple times.
seed:
	cd backend && uv run python manage.py seed_benchmark

# -- Evaluation ---------------------------------------------------------------

# Run a parameter sweep using the Django management command.
# Executes the pipeline multiple times with different configurations and
# produces statistical analysis comparing results.
sweep:
	cd backend && uv run python manage.py run_sweep

# -- Quality Assurance --------------------------------------------------------

# Run all automated tests for both backend and frontend.
# Backend tests use pytest; frontend tests use pnpm test.
# The `2>/dev/null || true` on frontend suppresses errors if no test runner
# is configured (frontend tests are optional during early development).
test:
	cd backend && uv run pytest
	cd frontend && corepack enable && pnpm test 2>/dev/null || true

# Run linters for both backend and frontend.
# Backend uses ruff for both linting and format checking.
# Frontend uses pnpm lint (typically ESLint).
# The `2>/dev/null || true` on frontend suppresses errors if no linter
# is configured.
lint:
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .
	cd frontend && corepack enable && pnpm lint 2>/dev/null || true
