.PHONY: install dev-backend dev-frontend migrate seed sweep test lint

install:
	cd backend && uv sync
	cd frontend && pnpm install

dev-backend:
	cd backend && uv run python manage.py runserver 8000

dev-frontend:
	cd frontend && pnpm dev

migrate:
	cd backend && uv run python manage.py migrate

seed:
	cd backend && uv run python manage.py seed_benchmark

sweep:
	cd backend && uv run python manage.py run_sweep

test:
	cd backend && uv run pytest
	cd frontend && pnpm test 2>/dev/null || true

lint:
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .
	cd frontend && pnpm lint 2>/dev/null || true
