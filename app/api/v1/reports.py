"""Report endpoints: summary, monthly series, CSV export, exchange rates."""

import csv
import datetime as dt
import io
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.report import MonthlyPoint, SummaryReport
from app.services import analytics, exchange
from app.services import transactions as tx_service

router = APIRouter()

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


def _parse_month(month: str | None) -> dt.date:
    if not month:
        return dt.date.today()
    return dt.date.fromisoformat(f"{month}-01")


@router.get("/summary", response_model=SummaryReport)
async def summary(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    month: str | None = Query(default=None, pattern=MONTH_PATTERN, description="YYYY-MM"),
) -> SummaryReport:
    return await analytics.monthly_summary(db, user, _parse_month(month))


@router.get("/monthly", response_model=list[MonthlyPoint])
async def monthly(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    months: int = Query(default=6, ge=1, le=24),
) -> list[MonthlyPoint]:
    return await analytics.monthly_series(db, user, months)


@router.get("/export.csv")
async def export_csv(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> Response:
    filters = tx_service.TransactionFilters(date_from=date_from, date_to=date_to)
    items, _ = await tx_service.list_transactions(db, user.id, filters, limit=10000, offset=0)

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["date", "category", "kind", "amount", "currency", "note"])
    for tx in items:
        writer.writerow(
            [
                tx.happened_at.isoformat(),
                tx.category.name,
                tx.kind.value,
                f"{tx.amount:.2f}",
                tx.currency,
                tx.note or "",
            ]
        )

    filename = f"fintrack-transactions-{dt.date.today().isoformat()}.csv"
    # BOM — чтобы Excel корректно открыл UTF-8.
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/rates")
async def rates() -> dict:
    return {"base": "USD", "rates": await exchange.get_rates()}
