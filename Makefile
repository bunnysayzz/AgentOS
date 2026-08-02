.PHONY: dev-backend dev-frontend dev install test build clean docker-up docker-down lint format

# ─── Development ───────────────────────────────────────────

dev-backend:  ## Start the FastAPI backend dev server
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:  ## Start the Vite frontend dev server
	cd frontend && npm run dev

dev:  ## Start both backend and frontend dev servers
	@echo "Starting AgentOS Studio in development mode..."
	@trap 'kill 0' EXIT; \
		$(MAKE) dev-backend & \
		$(MAKE) dev-frontend & \
		wait

install:  ## Install all dependencies
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

# ─── Testing ───────────────────────────────────────────────

test:  ## Run the FULL test pipeline (backend + frontend + e2e)
	./scripts/run_all_tests.sh

test-all:  ## Alias for `make test` — full pipeline
	./scripts/run_all_tests.sh

test-backend:  ## Backend tests only (pytest)
	cd backend && .venv/bin/python -m pytest -q

test-frontend:  ## Frontend unit tests + typecheck + lint
	cd frontend && npx tsc --noEmit && npm run lint && npx vitest run

test-e2e:  ## Playwright end-to-end tests (boots backend + frontend)
	cd frontend && npx playwright test

# ─── Building ──────────────────────────────────────────────

build:  ## Build everything for production
	cd frontend && npm run build

# ─── Docker ────────────────────────────────────────────────

docker-up:  ## Start all services with Docker Compose
	docker-compose up --build -d

docker-down:  ## Stop all Docker services
	docker-compose down

docker-logs:  ## View Docker logs
	docker-compose logs -f

# ─── Code Quality ──────────────────────────────────────────

lint:  ## Run all linters
	cd backend && ruff check .
	cd backend && mypy app --ignore-missing-imports
	cd frontend && npm run lint

format:  ## Format all code
	cd backend && ruff format .
	cd frontend && npx prettier --write "src/**/*.{ts,tsx,css}"

# ─── Database ──────────────────────────────────────────────

migrate:  ## Run Alembic migrations
	cd backend && alembic upgrade head

migration:  ## Create a new Alembic migration
	cd backend && alembic revision --autogenerate -m "$(name)"

# ─── Help ──────────────────────────────────────────────────

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
