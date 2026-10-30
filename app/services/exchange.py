"""Exchange rates: Redis-cached, with an offline fallback.

Rates are USD-based: rate["RUB"] = 92.0 means 1 USD = 92 RUB.
"""

import json
from decimal import Decimal

import httpx
import redis.asyncio as aioredis
import structlog

from app.core.cache import get_redis
from app.core.config import get_settings
from app.core.exceptions import ValidationDomainError

logger = structlog.get_logger(__name__)

RATES_CACHE_KEY = "fintrack:exchange:rates"
RATES_TTL = 3600  # seconds

# Approximate fallback rates used when neither Redis nor the external API
# is available (offline demo mode).
FALLBACK_RATES: dict[str, float] = {
    "USD": 1.0,
    "RUB": 92.0,
    "EUR": 0.92,
    "KZT": 480.0,
    "BYN": 3.3,
    "GBP": 0.79,
    "CNY": 7.2,
}


async def get_rates(redis: aioredis.Redis | None = None) -> dict[str, float]:
    client = redis or get_redis()
    try:
        raw = await client.get(RATES_CACHE_KEY)
        if raw:
            return json.loads(raw)
    except Exception:
        logger.warning("redis_unavailable_for_rates")
    return dict(FALLBACK_RATES)


async def fetch_and_cache_rates(redis: aioredis.Redis | None = None) -> dict[str, float]:
    """Fetch fresh rates from the external API and cache them in Redis."""
    settings = get_settings()
    client = redis or get_redis()
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            response = await http.get(settings.exchange_api_url)
            response.raise_for_status()
            rates = (response.json() or {}).get("rates")
        if not rates or "USD" not in rates:
            raise ValueError("unexpected API response")
        await client.set(RATES_CACHE_KEY, json.dumps(rates), ex=RATES_TTL)
        logger.info("exchange_rates_updated", count=len(rates))
        return rates
    except Exception as exc:
        logger.warning("exchange_rates_fetch_failed", error=str(exc))
        return await get_rates(redis)


def convert(amount: Decimal, currency: str, base: str, rates: dict[str, float]) -> Decimal:
    """Convert ``amount`` from ``currency`` to ``base`` using USD-based rates."""
    if currency == base:
        return amount
    rate_from = rates.get(currency)
    rate_to = rates.get(base)
    if not rate_from or not rate_to:
        raise ValidationDomainError(f"No exchange rate to convert {currency} to {base}")
    result = Decimal(str(amount)) / Decimal(str(rate_from)) * Decimal(str(rate_to))
    return result.quantize(Decimal("0.01"))
