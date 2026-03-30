# Cache-aside helper: get(key) / set(key, value, ttl)
# TTL: 24h

from typing import cast

from redis.asyncio import Redis

from src.models import Period

DEFAULT_TTL = 86400  # 24 hours — prices, info
FUNDAMENTALS_TTL = (
    604800  # 7 days — financials, balance sheet, cashflow (change quarterly)
)
INFO_TTL = 172800  # 48 hours — company info


async def cache_get(redis: Redis, key: str) -> str | None:
    return cast(str | None, await redis.get(key))


async def cache_set(redis: Redis, key: str, value: str, ttl: int = DEFAULT_TTL) -> None:
    await redis.set(key, value, ex=ttl)


def get_prices_cache_key(ticker: str, period: Period) -> str:
    return f"prices:{ticker}:{period}"


def get_info_cache_key(ticker: str) -> str:
    return f"info:{ticker}"


def get_financials_cache_key(ticker: str) -> str:
    return f"financials:{ticker}"


def get_balance_sheet_cache_key(ticker: str) -> str:
    return f"balance_sheet:{ticker}"


def get_cashflow_cache_key(ticker: str) -> str:
    return f"cashflow:{ticker}"


def get_quality_cache_key(ticker: str) -> str:
    return f"quality:{ticker}"
