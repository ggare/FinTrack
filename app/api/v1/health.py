"""Health check endpoint (used by Docker HEALTHCHECK and monitoring)."""

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.db.session import get_db

router = APIRouter()


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    components: dict[str, str] = {}
    status_code = 200

    try:
        await db.execute(sa.select(1))
        components["database"] = "ok"
    except Exception:
        components["database"] = "error"
        status_code = 503

    try:
        await get_redis().ping()
        components["redis"] = "ok"
    except Exception:
        components["redis"] = "unavailable"

    return JSONResponse(
        {"status": "ok" if status_code == 200 else "degraded", "components": components},
        status_code=status_code,
    )
