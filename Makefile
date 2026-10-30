.PHONY: install dev worker beat flower test lint format migrate autogenerate seed docker-up docker-down docker-logs ci

install:            ## Install development dependencies
	pip install -e ".[dev]"

dev:                ## Run the API with auto-reload
	uvicorn app.main:app --reload --port 8000

worker:             ## Start a Celery worker
	celery -A app.workers.celery_app worker --loglevel=info

beat:               ## Start Celery beat (the schedule)
	celery -A app.workers.celery_app beat --loglevel=info

flower:             ## Celery monitoring dashboard
	celery -A app.workers.celery_app flower --port=5555

test:               ## Run the tests
	pytest -q

lint:               ## Linter
	ruff check app tests

format:             ## Auto-format + fix imports
	ruff format app tests && ruff check --fix app tests

migrate:            ## Apply migrations
	alembic upgrade head

autogenerate:       ## Generate a migration: make autogenerate m="add table"
	alembic revision --autogenerate -m "$(m)"

seed:               ## Load demo data
	python -m app.db.seeds

docker-up:          ## Start the whole stack in Docker
	docker compose up -d --build

docker-down:        ## Stop the stack (data stays in volumes)
	docker compose down

docker-logs:        ## API logs
	docker compose logs -f api

ci: lint test       ## Local check, same as CI
