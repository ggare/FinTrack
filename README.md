# FinTrack — Personal Finance Tracker

[![CI](https://github.com/USERNAME/fintrack/actions/workflows/ci.yml/badge.svg)](https://github.com/USERNAME/fintrack/actions)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-black.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> A portfolio pet project: a full-featured **FastAPI** backend on **PostgreSQL**, with background
> jobs on **Celery**, caching and rate limiting in **Redis**, and a lightweight server-rendered
> frontend built with **Jinja2 + HTMX + Tailwind CSS + Chart.js** — all packaged with
> Docker Compose and a GitHub Actions CI pipeline.
>
> *The CI badge will start working once you push the project to your own repository —
> just replace `USERNAME` in the badge URL with your GitHub username.*

---

## Features

- **Authentication** — registration & login, JWT tokens (PyJWT) with bcrypt password hashing.
  The REST API uses `Authorization: Bearer`, the web UI uses an httpOnly cookie
  (a single verification mechanism behind both).
- **Categories** — income/expense categories with colors; 8 categories are created
  automatically for every new user.
- **Transactions** — amount, currency, date and note; filters (category, kind, period)
  and pagination.
- **Budgets** — monthly spending limits per expense category, with progress bars
  and remaining amounts.
- **Analytics** — monthly summary (income/expenses/balance broken down by category),
  a 6-month trend, and CSV export (with a BOM so Excel opens it correctly).
- **Multi-currency support** — conversion via an external exchange-rate API; rates are
  cached in Redis and refreshed by a background worker every 30 minutes.
- **Background jobs (Celery + Redis)** — exchange-rate refresh, a daily budget check
  that creates notifications at 80% and 100% of a limit, and cleanup of stale notifications.
- **Rate limiting** — Redis fixed-window limiter on login attempts (fails open if Redis is down).
- **Observability** — Prometheus metrics (`/metrics`), structured logs via structlog
  with a per-request `request_id`, and a health endpoint reporting dependency status.
- **API documentation** — Swagger UI (`/api/docs`) and ReDoc, generated automatically.
- **Tests** — 34 pytest tests on in-memory SQLite + fakeredis, ruff linting, CI.

## Tech Stack

| Technology | What it's used for |
|---|---|
| **Python 3.12** | project language, type hints, PEP 695 generics |
| **FastAPI** | async REST API + server-side page rendering |
| **SQLAlchemy 2.0 (async)** | ORM with an async engine, relationships, `selectin` loading |
| **PostgreSQL + asyncpg** | primary database (SQLite + aiosqlite in tests) |
| **Alembic** | schema migrations (initial migration + autogenerate support) |
| **Redis** | exchange-rate cache, rate limiting, Celery broker & backend |
| **Celery + Beat + Flower** | scheduled background jobs + a web dashboard for workers |
| **Pydantic v2 + pydantic-settings** | request/response validation and env-based configuration |
| **PyJWT + bcrypt** | access tokens and password hashing |
| **Jinja2 + HTMX + Tailwind CSS + Chart.js** | server-rendered frontend with no build step: dynamic rows, notification polling, charts |
| **structlog** | structured logging (JSON in production) |
| **prometheus-fastapi-instrumentator** | HTTP metrics for Prometheus |
| **Docker + docker compose** | the whole stack in one command: api, worker, beat, flower, db, redis |
| **pytest + pytest-asyncio + fakeredis** | async tests with an isolated DB and a fake Redis |
| **ruff** | linter and formatter |
| **GitHub Actions** | CI: lint + tests with coverage on every push/PR |

## Architecture

```
                      ┌──────────────────────────────┐
  Browser ──────────▶ │  FastAPI (uvicorn)           │
  (HTMX, Tailwind,    │  ├─ /api/v1/*  — REST API    │───▶ PostgreSQL (SQLAlchemy async)
  Chart.js)           │  ├─ /*        — Jinja2 pages │───▶ Redis (rates, rate limit)
                      │  └─ /metrics  — Prometheus   │
                      └──────────────┬───────────────┘
                                     │  tasks via the Redis broker
  ┌────────────┐     ┌───────────────▼──────────────┐
  │ Celery Beat│────▶│  Celery Worker               │───▶ PostgreSQL (notifications)
  │ (schedule) │     │  rates · budgets · cleanup   │───▶ external rates API
  └────────────┘     └──────────────┬───────────────┘
                                     │
                                ┌────▼────┐
                                │ Flower  │  task monitoring (:5555)
                                └─────────┘
```

Application layers:

- `app/core` — configuration, security, logging, exceptions, the Redis client;
- `app/db` — engine, sessions, declarative base, demo data;
- `app/models` — SQLAlchemy models (User, Category, Transaction, Budget, Notification);
- `app/schemas` — Pydantic request/response schemas;
- `app/services` — business logic (HTTP-agnostic);
- `app/api/v1` — thin REST endpoints that delegate to services;
- `app/web` — server-rendered pages and HTMX endpoints;
- `app/workers` — the Celery application and its tasks.

## Project Structure

```
fintrack/
├── app/
│   ├── main.py                  # application factory, middlewares, metrics
│   ├── core/                    # config, security (JWT/bcrypt), logging, cache, exceptions
│   ├── db/                      # engine, session, base, seeds (demo data)
│   ├── models/                  # user, category, transaction, budget, notification
│   ├── schemas/                 # Pydantic schemas
│   ├── api/
│   │   ├── deps.py              # get_current_user (Bearer + cookie)
│   │   └── v1/                  # auth, users, categories, transactions, budgets,
│   │                            # reports, notifications, health, router
│   ├── services/                # users, categories, transactions, budgets,
│   │                            # analytics, exchange, notifications, ratelimit
│   ├── web/
│   │   ├── router.py            # pages: login, dashboard, transactions, budgets
│   │   ├── templates/           # Jinja2: base, auth, dashboard, transactions,
│   │   │   └── partials/        #   budgets + HTMX partials
│   │   └── static/              # css/app.css, js/app.js (toasts, form resets)
│   └── workers/                 # celery_app (beat schedule), tasks
├── alembic/                     # env.py (async) + versions/0001_initial.py
├── tests/                       # conftest (SQLite+fakeredis), helpers, 5 test modules
├── .github/workflows/ci.yml     # lint + tests with coverage
├── Dockerfile                   # API image (non-root, healthcheck)
├── docker-compose.yml           # api + worker + beat + flower + postgres + redis
├── Makefile                     # install/dev/test/lint/migrate/seed/docker-*
├── pyproject.toml               # dependencies, ruff, pytest, coverage
├── alembic.ini
├── .env.example                 # environment template
└── README.md
```

## Quick Start (Docker — recommended)

Only Docker is required.

```bash
git clone <your-fork> fintrack && cd fintrack
cp .env.example .env            # optionally replace SECRET_KEY (openssl rand -hex 32)
docker compose up -d --build
```

Compose starts 6 services: PostgreSQL, Redis, the API (with migrations and demo data),
a Celery worker, Celery Beat, and Flower. Wait ~20–30 seconds, then open:

| Service | URL | Notes |
|---|---|---|
| Web UI | http://localhost:8000 | login: `demo@fintrack.dev` / `demo1234` |
| Swagger UI | http://localhost:8000/api/docs | interactive API documentation |
| ReDoc | http://localhost:8000/api/redoc | same, different layout |
| Prometheus metrics | http://localhost:8000/metrics | HTTP counters/histograms |
| Flower | http://localhost:5555 | Celery task monitoring |
| Health | http://localhost:8000/api/v1/health | DB and Redis status |

The demo user already has ~130 transactions spanning 3 months and 4 budgets,
so the dashboard with its charts is populated right away.

Stop with `docker compose down` (data persists in volumes),
wipe everything with `docker compose down -v`.

## Running on Windows (WSL Ubuntu)

Everything below runs inside a WSL2 Ubuntu terminal; the browser opens on Windows as usual
(WSL2 forwards `localhost` automatically, so `http://localhost:8000` just works).

### 0. Install WSL + Ubuntu (skip if you already have it)

In an **administrator PowerShell**:

```powershell
wsl --install -d Ubuntu-24.04
```

Reboot, launch *Ubuntu* from the Start menu and create your Linux user. Update the system:

```bash
sudo apt update && sudo apt upgrade -y
```

### 1. Get the project into WSL

Keep the code inside the Linux filesystem (e.g. `~/fintrack`), not on `/mnt/c/...` —
file IO and Docker bind mounts are dramatically faster this way.

```bash
cd ~
# either clone your fork, or unpack the zip you downloaded:
unzip /mnt/c/Users/<YourName>/Downloads/fintrack.zip
cd fintrack
```

### 2. Choose how to run it

#### Option A — Docker inside WSL (recommended)

Install the native Docker Engine in Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER   # then close and reopen the terminal
```

(Alternative: install **Docker Desktop** on Windows and enable
*Settings → Resources → WSL Integration* for your Ubuntu distro — then skip the block above.)

WSL usually has no systemd enabled; start Docker manually and verify:

```bash
sudo service docker start
docker run --rm hello-world
```

Then launch the whole stack:

```bash
cp .env.example .env
docker compose up -d --build
```

Open http://localhost:8000 in your Windows browser and sign in with
`demo@fintrack.dev` / `demo1234`.

> Tip: to have Docker start automatically, enable systemd in `/etc/wsl.conf`:
> `[boot]` → `systemd=true`, then `wsl --shutdown` from PowerShell.

#### Option B — native Python + services

Ubuntu 24.04 ships Python 3.12 out of the box (on 22.04 use the deadsnakes PPA:
`sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt install python3.12 python3.12-venv`).

```bash
sudo apt install -y python3.12 python3.12-venv
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Start PostgreSQL and Redis — the easiest way is to borrow them from the compose file:

```bash
docker compose up -d db redis    # needs Docker from Option A
```

or install them natively:

```bash
sudo apt install -y postgresql redis-server
sudo service postgresql start && sudo service redis-server start
sudo -u postgres psql -c "CREATE USER fintrack WITH PASSWORD 'fintrack';"
sudo -u postgres psql -c "CREATE DATABASE fintrack OWNER fintrack;"
```

Apply migrations, load demo data and run the app:

```bash
cp .env.example .env
alembic upgrade head
python -m app.db.seeds
uvicorn app.main:app --reload
```

The API and web UI are at http://localhost:8000.

## Running Locally (Linux / macOS)

Python 3.12+, PostgreSQL and Redis (or just `docker compose up -d db redis`).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # dependencies + dev tooling
cp .env.example .env             # check DATABASE_URL and REDIS_URL

alembic upgrade head             # apply migrations
python -m app.db.seeds           # (optional) demo data
uvicorn app.main:app --reload    # API + web UI: http://localhost:8000
```

Background jobs — in separate terminals (optional, the app works without them):

```bash
celery -A app.workers.celery_app worker --loglevel=info
celery -A app.workers.celery_app beat --loglevel=info
celery -A app.workers.celery_app flower --port=5555
```

### Makefile Commands

| Command | Action |
|---|---|
| `make install` | install development dependencies |
| `make dev` | run the API with auto-reload |
| `make test` / `make lint` / `make format` | tests / linter / formatting |
| `make migrate` | apply migrations |
| `make autogenerate m="..."` | generate a migration from the models |
| `make seed` | load demo data |
| `make worker` / `make beat` / `make flower` | Celery services |
| `make docker-up` / `make docker-down` | the whole stack in Docker |

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` — JSON logs instead of console logs |
| `DEBUG` | `false` | `true` — log SQL queries |
| `LOG_LEVEL` | `INFO` | logging level |
| `SECRET_KEY` | dev value | **must be changed** in production |
| `DATABASE_URL` | Postgres on localhost | connection string (asyncpg) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis: cache, rate limit, broker |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | JWT lifetime |
| `LOGIN_RATE_LIMIT` / `LOGIN_RATE_WINDOW` | `5` / `300` | login attempts per IP |
| `EXCHANGE_API_URL` | open.er-api.com | external exchange-rate API |
| `CORS_ORIGINS` | JSON list | allowed origins |
| `BCRYPT_ROUNDS` | `12` | password hashing cost |

## REST API Overview

Full interactive docs: `GET /api/openapi.json`, Swagger UI at `/api/docs`.

| Method & Path | Description |
|---|---|
| `POST /api/v1/auth/register` | register (+ 8 default categories) |
| `POST /api/v1/auth/login` | login (OAuth2 password flow) → JWT |
| `GET /api/v1/auth/me` | current user |
| `PATCH /api/v1/users/me` | update name / base currency |
| `GET/POST /api/v1/categories` | list / create categories |
| `PATCH/DELETE /api/v1/categories/{id}` | update / delete (`?force=true` — with transactions) |
| `GET/POST /api/v1/transactions` | list with filters & pagination / create |
| `PATCH/DELETE /api/v1/transactions/{id}` | update / delete |
| `GET /api/v1/budgets` | budgets with month-to-date spending |
| `PUT/DELETE /api/v1/budgets/{category_id}` | set / remove a limit |
| `GET /api/v1/reports/summary?month=YYYY-MM` | monthly summary |
| `GET /api/v1/reports/monthly?months=6` | month-over-month dynamics |
| `GET /api/v1/reports/export.csv` | export transactions to CSV |
| `GET /api/v1/reports/rates` | current exchange rates (from the Redis cache) |
| `GET /api/v1/notifications` | notifications (budget alerts) |
| `POST /api/v1/notifications/read-all` | mark all notifications as read |
| `POST /api/v1/notifications/{id}/read` | mark one notification as read |
| `GET /api/v1/health` | DB and Redis status |

Examples (`curl`):

```bash
# 1. Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "me@example.com", "username": "me", "password": "strong-password"}'

# 2. Login (email goes in the username field — OAuth2 password flow)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=me@example.com&password=strong-password" | python -c "import json,sys;print(json.load(sys.stdin)['access_token'])")

# 3. Create a transaction (the category comes from the defaults)
curl -X POST http://localhost:8000/api/v1/transactions \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"category_id": 1, "amount": 350.50, "note": "groceries"}'

# 4. Monthly summary
curl "http://localhost:8000/api/v1/reports/summary?month=2026-10" \
  -H "Authorization: Bearer $TOKEN"
```

## Background Jobs

Defined in `app/workers/tasks.py`, scheduled by Celery Beat:

| Task | Schedule | What it does |
|---|---|---|
| `update_exchange_rates` | every 30 minutes | fetch USD-based rates from the external API and cache them in Redis |
| `check_budgets` | daily at 09:00 | compare each user's monthly spending against their budgets, create notifications at 80% and 100% of a limit |
| `cleanup_old_notifications` | daily at 03:30 | delete notifications older than 30 days |

Each task spins up its own event loop and fresh DB/Redis connections — the safe pattern
for asyncio code inside a synchronous Celery worker process. Flower (`:5555`) shows
task history and results.

## Testing & Quality

```bash
make test    # 34 tests: auth, categories, transactions, reports, budgets, web pages
make lint    # ruff check
make format  # ruff format + autofixes
```

The tests run on **in-memory SQLite** and **fakeredis** — no external services needed,
they finish in a couple of seconds. Every test gets a clean database
(an engine factory + `dependency_overrides`), and Redis is replaced with a fake client.

CI (`.github/workflows/ci.yml`) runs on every push/PR: ruff lint + format check,
followed by pytest with a coverage report.

## Roadmap Ideas

- CSRF tokens for the web forms and refresh tokens (currently a single long-lived JWT);
- E2E tests for the UI (Playwright);
- OpenTelemetry tracing alongside (or instead of) request IDs;
- deployment (k8s/Helm or a managed host) and Prometheus/Grafana scraping;
- dark theme, a PWA manifest, bank statement import (OFX/CSV).

## License

[MIT](LICENSE)
