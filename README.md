# FinTrack — трекер личных финансов

[![CI](https://github.com/USERNAME/fintrack/actions/workflows/ci.yml/badge.svg)](https://github.com/USERNAME/fintrack/actions)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> Пет-проект для портфолио: полнофункциональный бэкенд на **FastAPI** с базой **PostgreSQL**,
> фоновыми задачами **Celery**, кэшированием и rate limiting в **Redis**, лёгким серверным
> фронтендом на **Jinja2 + HTMX + Tailwind + Chart.js** — и всё это упаковано в Docker
> с CI на GitHub Actions.
>
> *Бейдж CI заработает после того, как вы запушите проект в свой репозиторий —
> замените `USERNAME` в ссылке на свой логин GitHub.*

---

## Возможности

- **Аутентификация**: регистрация и вход, JWT-токены (PyJWT) + пароли bcrypt.
  REST API работает по `Authorization: Bearer`, веб-интерфейс — через httpOnly-cookie
  (один и тот же механизм проверки).
- **Категории** доходов и расходов с цветами; 8 категорий создаётся автоматически
  при регистрации.
- **Транзакции** с валютой, датой и заметкой; фильтры (категория, тип, период)
  и пагинация.
- **Бюджеты** по категориям расходов: лимит на месяц, прогресс-бар, остаток.
- **Аналитика**: сводка за месяц (доходы/расходы/баланс с разбивкой по категориям),
  динамика за 6 месяцев, экспорт в CSV (с BOM для Excel).
- **Мультивалютность**: конвертация по курсам из внешнего API; курсы кэшируются
  в Redis и обновляются фоновым воркером каждые 30 минут.
- **Фоновые задачи (Celery + Redis)**: обновление курсов, ежедневная проверка
  бюджетов с созданием уведомлений (при 80% и 100% лимита), очистка старых уведомлений.
- **Rate limiting** попыток входа (Redis, фиксированное окно, fail-open).
- **Наблюдаемость**: метрики Prometheus (`/metrics`), структурные логи structlog
  с request-id каждого запроса, health-check со статусом зависимостей.
- **Документация API**: Swagger UI (`/api/docs`) и ReDoc, генерируются автоматически.
- **Тесты**: 34 pytest-теста на SQLite in-memory + fakeredis, линтер ruff, CI.

## Стек технологий

| Технология | Зачем здесь |
|---|---|
| **Python 3.12** | язык проекта, type hints, PEP 695-дженерики |
| **FastAPI** | асинхронный REST API + серверный рендеринг страниц |
| **SQLAlchemy 2.0 (async)** | ORM с асинхронным движком, relationship'ы, `selectin`-загрузка |
| **PostgreSQL + asyncpg** | основная БД (в тестах — SQLite + aiosqlite) |
| **Alembic** | миграции схемы (первоначальная миграция + autogenerate) |
| **Redis** | кэш курсов валют, rate limiting, брокер и backend Celery |
| **Celery + Beat + Flower** | фоновые задачи по расписанию, веб-мониторинг воркеров |
| **Pydantic v2 + pydantic-settings** | валидация входных данных и конфигурации из env |
| **PyJWT + bcrypt** | access-токены и хэширование паролей |
| **Jinja2 + HTMX + Tailwind CSS + Chart.js** | серверный фронтенд без сборки: динамическое добавление/удаление строк, опрос уведомлений, графики |
| **structlog** | структурированные логи (JSON в production) |
| **prometheus-fastapi-instrumentator** | метрики HTTP-запросов для Prometheus |
| **Docker + docker compose** | весь стек одной командой: api, worker, beat, flower, db, redis |
| **pytest + pytest-asyncio + fakeredis** | асинхронные тесты с изолированной БД и фейковым Redis |
| **ruff** | линтер и форматтер |
| **GitHub Actions** | CI: lint + тесты с coverage на каждый push/PR |

## Архитектура

```
                       ┌──────────────────────────────┐
   Браузер ──────────▶ │  FastAPI (uvicorn)           │
   (HTMX, Tailwind,    │  ├─ /api/v1/*  — REST API    │───▶ PostgreSQL (SQLAlchemy async)
   Chart.js)           │  ├─ /*        — Jinja2-стр.  │───▶ Redis (курсы, rate limit)
                       │  └─ /metrics  — Prometheus   │
                       └──────────────┬───────────────┘
                                      │  задачи через Redis-брокер
   ┌────────────┐     ┌───────────────▼──────────────┐
   │ Celery Beat│────▶│  Celery Worker               │───▶ PostgreSQL (уведомления)
   │ (расписание)│    │  курсы · бюджеты · очистка   │───▶ внешний API курсов
   └────────────┘     └──────────────┬───────────────┘
                                      │
                                 ┌────▼────┐
                                 │ Flower  │  мониторинг задач (:5555)
                                 └─────────┘
```

Слои приложения:

- `app/core` — конфигурация, безопасность, логирование, исключения, Redis-клиент;
- `app/db` — движок, сессии, декларативная база, демо-данные;
- `app/models` — SQLAlchemy-модели (User, Category, Transaction, Budget, Notification);
- `app/schemas` — Pydantic-схемы запросов/ответов;
- `app/services` — бизнес-логика (не знает про HTTP);
- `app/api/v1` — REST-эндпоинты (тонкие, работают через сервисы);
- `app/web` — серверные страницы и HTMX-эндпоинты;
- `app/workers` — Celery-приложение и задачи.

## Структура проекта

```
fintrack/
├── app/
│   ├── main.py                  # фабрика приложения, middlewares, метрики
│   ├── core/                    # config, security (JWT/bcrypt), logging, cache, exceptions
│   ├── db/                      # engine, session, base, seeds (демо-данные)
│   ├── models/                  # user, category, transaction, budget, notification
│   ├── schemas/                 # Pydantic-схемы
│   ├── api/
│   │   ├── deps.py              # get_current_user (Bearer + cookie)
│   │   └── v1/                  # auth, users, categories, transactions, budgets,
│   │                            # reports, notifications, health, router
│   ├── services/                # users, categories, transactions, budgets,
│   │                            # analytics, exchange, notifications, ratelimit
│   ├── web/
│   │   ├── router.py            # страницы: вход, дашборд, транзакции, бюджеты
│   │   ├── templates/           # Jinja2: base, auth, dashboard, transactions,
│   │   │   └── partials/        #   budgets + HTMX-партиалы
│   │   └── static/              # css/app.css, js/app.js (тосты, сброс форм)
│   └── workers/                 # celery_app (beat-расписание), tasks
├── alembic/                     # env.py (async) + versions/0001_initial.py
├── tests/                       # conftest (SQLite+fakeredis), helpers, 5 файлов тестов
├── .github/workflows/ci.yml     # lint + tests с coverage
├── Dockerfile                   # образ API (non-root, healthcheck)
├── docker-compose.yml           # api + worker + beat + flower + postgres + redis
├── Makefile                     # install/dev/test/lint/migrate/seed/docker-*
├── pyproject.toml               # зависимости, ruff, pytest, coverage
├── alembic.ini
├── .env.example                 # шаблон окружения
└── README.md
```

## Быстрый старт (Docker — рекомендуется)

Нужен только Docker.

```bash
git clone <ваш-форк> fintrack && cd fintrack
cp .env.example .env            # при желании замените SECRET_KEY (openssl rand -hex 32)
docker compose up -d --build
```

Compose поднимет 6 сервисов: PostgreSQL, Redis, API (с миграциями и демо-данными),
Celery-воркер, Celery Beat и Flower. Дождитесь старта (~20–30 сек) и открывайте:

| Сервис | URL | Комментарий |
|---|---|---|
| Веб-интерфейс | http://localhost:8000 | вход: `demo@fintrack.dev` / `demo1234` |
| Swagger UI | http://localhost:8000/api/docs | интерактивная документация API |
| ReDoc | http://localhost:8000/api/redoc | то же в другом формате |
| Метрики Prometheus | http://localhost:8000/metrics | счётчики/гистограммы HTTP |
| Flower | http://localhost:5555 | мониторинг Celery-задач |
| Health | http://localhost:8000/api/v1/health | статусы БД и Redis |

Демо-пользователь уже содержит ~130 транзакций за 3 месяца и 4 бюджета —
дашборд с графиками заполнится сразу.

Остановка: `docker compose down` (данные останутся в volume),
полная очистка: `docker compose down -v`.

## Локальный запуск (без Docker)

Python 3.12+, PostgreSQL и Redis (либо `docker compose up -d db redis`).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # зависимости + dev-инструменты
cp .env.example .env             # проверьте DATABASE_URL и REDIS_URL

alembic upgrade head             # применить миграции
python -m app.db.seeds           # (опционально) демо-данные
uvicorn app.main:app --reload    # API + веб-интерфейс: http://localhost:8000
```

Фоновые задачи — в отдельных терминалах (опционально, приложение работает и без них):

```bash
celery -A app.workers.celery_app worker --loglevel=info
celery -A app.workers.celery_app beat --loglevel=info
celery -A app.workers.celery_app flower --port=5555
```

### Команды Makefile

| Команда | Действие |
|---|---|
| `make install` | установить зависимости для разработки |
| `make dev` | запустить API с автоперезагрузкой |
| `make test` / `make lint` / `make format` | тесты / линтер / форматирование |
| `make migrate` | применить миграции |
| `make autogenerate m="..."` | сгенерировать миграцию из моделей |
| `make seed` | загрузить демо-данные |
| `make worker` / `make beat` / `make flower` | сервисы Celery |
| `make docker-up` / `make docker-down` | стек в Docker |

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` — JSON-логи вместо консольных |
| `DEBUG` | `false` | `true` — SQL-запросы в логах |
| `LOG_LEVEL` | `INFO` | уровень логирования |
| `SECRET_KEY` | dev-значение | **обязательно сменить** в production |
| `DATABASE_URL` | Postgres на localhost | строка подключения (asyncpg) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis: кэш, rate limit, брокер |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | время жизни JWT |
| `LOGIN_RATE_LIMIT` / `LOGIN_RATE_WINDOW` | `5` / `300` | лимит попыток входа |
| `EXCHANGE_API_URL` | open.er-api.com | внешний API курсов валют |
| `CORS_ORIGINS` | JSON-список | разрешённые источники |
| `BCRYPT_ROUNDS` | `12` | стоимость хэширования паролей |

## REST API — обзор

Полная интерактивная документация: `GET /api/v1/openapi.json`, Swagger UI — `/api/docs`.

| Метод и путь | Описание |
|---|---|
| `POST /api/v1/auth/register` | регистрация (+ 8 категорий по умолчанию) |
| `POST /api/v1/auth/login` | вход (OAuth2 password flow) → JWT |
| `GET /api/v1/auth/me` | текущий пользователь |
| `PATCH /api/v1/users/me` | смена имени / базовой валюты |
| `GET/POST /api/v1/categories` | список / создание категорий |
| `PATCH/DELETE /api/v1/categories/{id}` | изменение / удаление (`?force=true` — с транзакциями) |
| `GET/POST /api/v1/transactions` | список с фильтрами и пагинацией / создание |
| `PATCH/DELETE /api/v1/transactions/{id}` | изменение / удаление |
| `GET /api/v1/budgets` | бюджеты с потраченным за месяц |
| `PUT/DELETE /api/v1/budgets/{category_id}` | задать / удалить лимит |
| `GET /api/v1/reports/summary?month=YYYY-MM` | сводка за месяц |
| `GET /api/v1/reports/monthly?months=6` | динамика по месяцам |
| `GET /api/v1/reports/export.csv` | экспорт транзакций в CSV |
| `GET /api/v1/reports/rates` | текущие курсы (из кэша Redis) |
| `GET /api/v1/notifications` | уведомления (бюджетные оповещения) |
| `GET /api/v1/health` | статус БД и Redis |

Примеры (`curl`):

```bash
# 1. Регистрация
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "me@example.com", "username": "me", "password": "strong-password"}'

# 2. Вход (email в поле username — это OAuth2 password flow)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=me@example.com&password=strong-password" | python -c "import json,sys;print(json.load(sys.stdin)['access_token'])")

# 3. Создать транзакцию (категория возьмётся из дефолтных)
curl -X POST http://localhost:8000/api/v1/transactions \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"category_id": 1, "amount": 350.50, "note": "пятёрочка"}'

# 4. Сводка за месяц
curl "http://localhost:8000/api/v1/reports/summary?month=2026-10" \
  -H "Authorization: Bearer $TOKEN"
```

## Тесты и качество

```bash
make test    # 34 теста: auth, категории, транзакции, отчёты, бюджеты, веб-страницы
make lint    # ruff check
make format  # ruff format + автофиксы
```

Тесты выполняются на **SQLite in-memory** и **fakeredis** — не требуют внешних
сервисов и падают за пару секунд. Каждый тест получает чистую БД
(фабрика движка + `dependency_overrides`), Redis подменяется фейк-клиентом.

CI (`.github/workflows/ci.yml`) на каждый push/PR: ruff lint + format check,
затем pytest с coverage-отчётом.

## Идеи для развития

- CSRF-токены для веб-форм и refresh-токены (сейчас один long-lived JWT);
- e2e-тесты интерфейса (Playwright);
- OpenTelemetry-трейсинг вместо/вместе с request-id;
- деплой (k8s/Helm или managed-хостинг) и скрейпинг Prometheus/Grafana;
- тёмная тема, PWA-манифест, импорт банковских выписок (OFX/CSV).

## Лицензия

[MIT](LICENSE)
