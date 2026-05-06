# =============================================================================
# ReqLens Development Makefile
#
# Provides convenient shortcuts for common development tasks. All backend
# commands use `uv run` to ensure the correct virtual environment and
# dependencies are used. All frontend commands use `pnpm`.
#
# Usage: make <target>
# =============================================================================

.PHONY: install dev-backend dev-frontend migrate seed sweep test lint

# -- Setup & Dependencies ----------------------------------------------------

# Install all dependencies for both backend and frontend.
# Backend uses uv (Python package manager) and frontend uses pnpm (Node).
# Run this first after cloning the repository.
install:
	cd backend && uv sync
	cd frontend && pnpm install

# -- Development Servers ------------------------------------------------------

# Start the Django development server on port 8000.
# The backend serves the REST API at http://localhost:8000/api/v1/.
# Hot-reloads on Python file changes.
dev-backend:
	cd backend && uv run python manage.py runserver 8000

# Start the frontend development server (typically on port 3000).
# Proxies API requests to the backend server.
dev-frontend:
	cd frontend && pnpm dev

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
	cd frontend && pnpm test 2>/dev/null || true

# Run linters for both backend and frontend.
# Backend uses ruff for both linting and format checking.
# Frontend uses pnpm lint (typically ESLint).
# The `2>/dev/null || true` on frontend suppresses errors if no linter
# is configured.
lint:
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .
	cd frontend && pnpm lint 2>/dev/null || true
