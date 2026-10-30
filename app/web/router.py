"""Server-rendered web UI (Jinja2 + HTMX).

Аутентификация — через httpOnly-cookie с JWT (та же зависимость get_current_user,
что и в REST API). Страницы рендерятся на сервере, интерактивность — HTMX.
"""

import datetime as dt
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional
from app.core.config import get_settings
from app.core.exceptions import DomainError
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.category import CategoryKind
from app.models.user import User
from app.schemas.transaction import TransactionCreate
from app.services import (
    analytics,
    ratelimit,
)
from app.services import (
    budgets as budget_service,
)
from app.services import (
    categories as category_service,
)
from app.services import (
    notifications as notification_service,
)
from app.services import (
    transactions as tx_service,
)
from app.services import (
    users as user_service,
)

router = APIRouter(include_in_schema=False)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

MONTHS_RU = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]


def _money(value) -> str:
    """12345.6 -> '12 345,60' (русский формат)."""
    try:
        return f"{Decimal(str(value)):,.2f}".replace(",", " ").replace(".", ",")
    except (InvalidOperation, ValueError, TypeError):
        return str(value)


templates.env.filters["money"] = _money


def _user_payload(username: str, email: str, password: str):
    from app.schemas.user import UserCreate

    return UserCreate(username=username, email=email, password=password)


def _set_auth_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )


def _login_redirect() -> RedirectResponse:
    return RedirectResponse("/login", status_code=307)


# --------------------------------------------------------------------------- #
# Auth pages
# --------------------------------------------------------------------------- #


@router.get("/", response_class=HTMLResponse)
async def index(user: User | None = Depends(get_current_user_optional)) -> Response:
    if user:
        return RedirectResponse("/dashboard", status_code=307)
    return RedirectResponse("/login", status_code=307)


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    user: User | None = Depends(get_current_user_optional),
) -> Response:
    if user:
        return RedirectResponse("/dashboard", status_code=307)
    return templates.TemplateResponse(request, "login.html", {})


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    settings = get_settings()
    await ratelimit.enforce_rate_limit(
        request,
        scope="web-login",
        limit=settings.login_rate_limit,
        window_seconds=settings.login_rate_window,
    )
    user = await user_service.authenticate(db, email, password)
    if user is None:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Неверный email или пароль"},
            status_code=400,
        )
    response = RedirectResponse("/dashboard", status_code=303)
    _set_auth_cookie(response, create_access_token(str(user.id)))
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    user: User | None = Depends(get_current_user_optional),
) -> Response:
    if user:
        return RedirectResponse("/dashboard", status_code=307)
    return templates.TemplateResponse(request, "register.html", {})


@router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        user = await user_service.register_user(db, _user_payload(username, email, password))
    except DomainError as exc:
        return templates.TemplateResponse(
            request, "register.html", {"error": exc.detail}, status_code=400
        )
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Проверьте поля: имя от 3 символов, пароль от 8 символов, корректный email"},
            status_code=400,
        )
    response = RedirectResponse("/dashboard", status_code=303)
    _set_auth_cookie(response, create_access_token(str(user.id)))
    return response


@router.get("/logout")
async def logout() -> Response:
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("access_token")
    return response


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if user is None:
        return _login_redirect()

    month = dt.date.today()
    summary = await analytics.monthly_summary(db, user, month)
    series = await analytics.monthly_series(db, user, months=6)
    recent = await tx_service.recent_transactions(db, user.id, limit=6)
    unread = await notification_service.list_notifications(db, user.id, unread_only=True)

    donut = [
        {"label": c.name, "value": float(c.total), "color": c.color}
        for c in summary.by_category
        if c.kind == CategoryKind.expense and c.total > 0
    ]

    context = {
        "active": "dashboard",
        "user": user,
        "month_label": f"{MONTHS_RU[month.month - 1]} {month.year}",
        "summary": summary,
        "recent": recent,
        "notifications": unread,
        "donut": donut,
        "series_labels": [p.month for p in series],
        "series_income": [float(p.income) for p in series],
        "series_expense": [float(p.expense) for p in series],
    }
    return templates.TemplateResponse(request, "dashboard.html", context)


@router.get("/partials/notifications", response_class=HTMLResponse)
async def notifications_partial(
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if user is None:
        return _login_redirect()
    unread = await notification_service.list_notifications(db, user.id, unread_only=True)
    return templates.TemplateResponse(
        request, "partials/_notifications.html", {"notifications": unread}
    )


@router.post("/notifications/read-all")
async def mark_notifications_read(
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if user is None:
        return Response("Требуется вход", status_code=401)
    await notification_service.mark_all_read(db, user.id)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request, "partials/_notifications.html", {"notifications": []}
        )
    return RedirectResponse("/dashboard", status_code=303)


# --------------------------------------------------------------------------- #
# Transactions page
# --------------------------------------------------------------------------- #


@router.get("/transactions", response_class=HTMLResponse)
async def transactions_page(
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    category_id: str = "",
    kind: str = "",
    date_from: str = "",
    date_to: str = "",
    page: int = 1,
) -> Response:
    if user is None:
        return _login_redirect()

    def _parse_date(value: str) -> dt.date | None:
        try:
            return dt.date.fromisoformat(value) if value else None
        except ValueError:
            return None

    try:
        cat_id = int(category_id) if category_id else None
    except ValueError:
        cat_id = None
    kind_enum = CategoryKind(kind) if kind in ("expense", "income") else None

    per_page = 15
    page = max(page, 1)
    filters = tx_service.TransactionFilters(
        category_id=cat_id,
        kind=kind_enum,
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
    )
    items, total = await tx_service.list_transactions(
        db, user.id, filters, limit=per_page, offset=(page - 1) * per_page
    )
    categories = await category_service.list_categories(db, user.id)
    pages = max((total + per_page - 1) // per_page, 1)

    def _page_url(target_page: int) -> str:
        params = {
            k: v
            for k, v in {
                "category_id": category_id,
                "kind": kind,
                "date_from": date_from,
                "date_to": date_to,
                "page": target_page,
            }.items()
            if v
        }
        return f"/transactions?{urlencode(params)}"

    context = {
        "active": "transactions",
        "user": user,
        "transactions": items,
        "categories": categories,
        "total": total,
        "page": page,
        "pages": pages,
        "prev_url": _page_url(page - 1) if page > 1 else None,
        "next_url": _page_url(page + 1) if page < pages else None,
        "filters": {
            "category_id": category_id,
            "kind": kind,
            "date_from": date_from,
            "date_to": date_to,
        },
        "today": dt.date.today().isoformat(),
        "currencies": ["RUB", "USD", "EUR", "KZT", "BYN", "GBP", "CNY"],
    }
    return templates.TemplateResponse(request, "transactions.html", context)


@router.post("/transactions", response_class=HTMLResponse)
async def add_transaction(
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    category_id: int = Form(...),
    amount: str = Form(...),
    currency: str = Form("RUB"),
    happened_at: str = Form(""),
    note: str = Form(""),
) -> Response:
    if user is None:
        return Response("Требуется вход", status_code=401)

    try:
        payload = TransactionCreate(
            category_id=category_id,
            amount=Decimal(amount.replace(",", ".")),
            currency=currency.upper(),
            happened_at=dt.date.fromisoformat(happened_at) if happened_at else dt.date.today(),
            note=note.strip() or None,
        )
        tx = await tx_service.create_transaction(db, user, payload)
    except (InvalidOperation, ValueError, ValidationError):
        return Response("Некорректная сумма или дата", status_code=422)
    except DomainError as exc:
        return Response(exc.detail, status_code=422)

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "partials/_tx_row.html", {"tx": tx})
    return RedirectResponse("/transactions", status_code=303)


@router.delete("/transactions/{transaction_id}")
async def delete_transaction_web(
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    transaction_id: int = 0,
) -> Response:
    if user is None:
        return Response("Требуется вход", status_code=401)
    try:
        await tx_service.delete_transaction(db, user, transaction_id)
    except DomainError:
        return Response("Транзакция не найдена", status_code=404)
    return Response(status_code=200)  # HTMX: hx-swap="delete" уберёт строку


# --------------------------------------------------------------------------- #
# Budgets page
# --------------------------------------------------------------------------- #


@router.get("/budgets", response_class=HTMLResponse)
async def budgets_page(
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if user is None:
        return _login_redirect()

    budgets = await budget_service.list_with_spent(db, user)
    categories = await category_service.list_categories(db, user.id)
    budgeted_ids = {b.category.id for b in budgets}
    available = [
        c for c in categories if c.kind == CategoryKind.expense and c.id not in budgeted_ids
    ]

    context = {
        "active": "budgets",
        "user": user,
        "budgets": budgets,
        "available_categories": available,
    }
    return templates.TemplateResponse(request, "budgets.html", context)


@router.post("/budgets", response_class=HTMLResponse)
async def save_budget(
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    category_id: int = Form(...),
    monthly_limit: str = Form(...),
) -> Response:
    if user is None:
        return Response("Требуется вход", status_code=401)

    try:
        limit = Decimal(monthly_limit.replace(",", "."))
        if limit <= 0:
            raise ValueError
        budget = await budget_service.set_budget(db, user, category_id, limit)
    except (InvalidOperation, ValueError):
        return Response("Лимит должен быть положительным числом", status_code=422)
    except DomainError as exc:
        return Response(exc.detail, status_code=422)

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "partials/_budget_row.html", {"b": budget})
    return RedirectResponse("/budgets", status_code=303)


@router.delete("/budgets/{category_id}")
async def delete_budget_web(
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    category_id: int = 0,
) -> Response:
    if user is None:
        return Response("Требуется вход", status_code=401)
    try:
        await budget_service.delete_budget(db, user, category_id)
    except DomainError:
        return Response("Бюджет не найден", status_code=404)
    return Response(status_code=200)
