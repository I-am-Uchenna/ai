.PHONY: help install dev-install build up down restart logs shell db-shell test lint format clean etl

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# =============================================================================
# Installation
# =============================================================================

install: ## Install production dependencies
	cd backend && pip install -r requirements.txt

dev-install: ## Install development dependencies
	cd backend && pip install -r requirements-dev.txt
	cd backend && pre-commit install

# =============================================================================
# Docker Commands
# =============================================================================

build: ## Build Docker images
	docker-compose build

up: ## Start all services
	docker-compose up -d
	@echo "Services started!"
	@echo "  - API: http://localhost:8000"
	@echo "  - API Docs: http://localhost:8000/docs"
	@echo "  - PgAdmin: http://localhost:5050"
	@echo ""
	@echo "Run 'make logs' to view logs"

down: ## Stop all services
	docker-compose down

restart: ## Restart all services
	docker-compose restart

logs: ## View logs from all services
	docker-compose logs -f

logs-backend: ## View backend logs only
	docker-compose logs -f backend

logs-postgres: ## View Postgres logs only
	docker-compose logs -f postgres

shell: ## Open shell in backend container
	docker-compose exec backend /bin/bash

db-shell: ## Open PostgreSQL shell
	docker-compose exec postgres psql -U variantiq -d variantiq

# =============================================================================
# Development
# =============================================================================

run-local: ## Run backend locally (without Docker)
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test: ## Run tests
	cd backend && pytest -v --cov=app --cov-report=html

test-watch: ## Run tests in watch mode
	cd backend && pytest-watch

lint: ## Run linters
	cd backend && ruff check app tests
	cd backend && mypy app

format: ## Format code
	cd backend && black app tests
	cd backend && isort app tests
	cd backend && ruff check app tests --fix

# =============================================================================
# Database
# =============================================================================

db-init: ## Initialize database (creates tables)
	docker-compose exec backend python -c "import asyncio; from app.db.base import init_db; asyncio.run(init_db())"

db-migrate: ## Run database migrations
	docker-compose exec backend alembic upgrade head

db-reset: ## Reset database (WARNING: destroys all data)
	@echo "⚠️  WARNING: This will destroy all data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down -v; \
		docker-compose up -d postgres redis; \
		sleep 5; \
		make db-init; \
		echo "✅ Database reset complete"; \
	fi

# =============================================================================
# ETL / Data Pipeline
# =============================================================================

etl: ## Run all ETL pipelines (incremental update)
	docker-compose exec backend python scripts/run_etl.py

etl-full: ## Run full ETL refresh (reload all data)
	docker-compose exec backend python scripts/run_etl.py --full-refresh

etl-drugs: ## Load drug data only
	docker-compose exec backend python scripts/run_etl.py --pipelines drugs

etl-clinvar: ## Load ClinVar data only (limit 100 for testing)
	docker-compose exec backend python scripts/run_etl.py --pipelines clinvar --limit 100

etl-trials: ## Load clinical trials data only
	docker-compose exec backend python scripts/run_etl.py --pipelines trials --limit 50

etl-pubmed: ## Load PubMed data only
	docker-compose exec backend python scripts/run_etl.py --pipelines pubmed --limit 50

etl-test: ## Run ETL with small limits (for testing)
	docker-compose exec backend python scripts/run_etl.py --limit 20

# =============================================================================
# Utilities
# =============================================================================

clean: ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true

status: ## Show status of all services
	docker-compose ps

stats: ## Show Docker stats
	docker stats

# =============================================================================
# Quick Start
# =============================================================================

quickstart: ## Quick start: build, start services, init DB, load seed data
	@echo "🚀 Starting VariantIQ quickstart..."
	@echo ""
	@echo "Step 1/5: Building Docker images..."
	docker-compose build
	@echo ""
	@echo "Step 2/5: Starting services..."
	docker-compose up -d
	@echo "Waiting for services to be healthy..."
	sleep 10
	@echo ""
	@echo "Step 3/5: Initializing database..."
	docker-compose exec backend python -c "import asyncio; from app.db.base import init_db; asyncio.run(init_db())"
	@echo ""
	@echo "Step 4/5: Loading seed data (drugs)..."
	docker-compose exec backend python scripts/run_etl.py --pipelines drugs
	@echo ""
	@echo "Step 5/5: Loading sample variants (limited)..."
	docker-compose exec backend python scripts/run_etl.py --pipelines clinvar --limit 50
	@echo ""
	@echo "✅ Quickstart complete!"
	@echo ""
	@echo "🌐 Access the application:"
	@echo "   API:          http://localhost:8000"
	@echo "   API Docs:     http://localhost:8000/docs"
	@echo "   PgAdmin:      http://localhost:5050"
	@echo ""
	@echo "📊 Try these example queries:"
	@echo "   curl http://localhost:8000/api/v1/variants/"
	@echo "   curl http://localhost:8000/api/v1/variants/stats/summary"
	@echo ""
	@echo "📖 See README.md for more information"
