.PHONY: install dev worker beat flower test lint format migrate autogenerate seed docker-up docker-down docker-logs ci

install:            ## Установить зависимости для разработки
	pip install -e ".[dev]"

dev:                ## Запустить API с reload
	uvicorn app.main:app --reload --port 8000

worker:             ## Запустить Celery-воркер
	celery -A app.workers.celery_app worker --loglevel=info

beat:               ## Запустить Celery beat (расписание)
	celery -A app.workers.celery_app beat --loglevel=info

flower:             ## Мониторинг Celery
	celery -A app.workers.celery_app flower --port=5555

test:               ## Прогнать тесты
	pytest -q

lint:               ## Линтер
	ruff check app tests

format:             ## Автоформатирование + исправление импортов
	ruff format app tests && ruff check --fix app tests

migrate:            ## Применить миграции
	alembic upgrade head

autogenerate:       ## Сгенерировать миграцию: make autogenerate m="add table"
	alembic revision --autogenerate -m "$(m)"

seed:               ## Загрузить демо-данные
	python -m app.db.seeds

docker-up:          ## Поднять весь стек в Docker
	docker compose up -d --build

docker-down:        ## Остановить стек (данные останутся в volume)
	docker compose down

docker-logs:        ## Логи API
	docker compose logs -f api

ci: lint test       ## Локальная проверка как в CI
