# GET /tickers/prices — fetch OHLCV prices for multiple tickers in parallel
# GET /tickers/returns — log returns matrix (columns=tickers, index=dates)
# GET /tickers/{ticker}/info — sector, industry, market cap
# GET /tickers/{ticker}/quality — quality score, GARP score, thesis health, moat

import asyncio
import json
from io import StringIO
from typing import Any, cast

import pandas as pd
from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis

from src.dependencies import get_redis_client
from src.domain.market_data import compute_returns
from src.domain.quality import (
    garp_score,
    is_etf,
    moat_rating,
    quality_score,
    thesis_health_check,
)
from src.infrastructure.redis_cache import (
    FUNDAMENTALS_TTL,
    INFO_TTL,
    cache_get,
    cache_set,
    get_balance_sheet_cache_key,
    get_cashflow_cache_key,
    get_financials_cache_key,
    get_info_cache_key,
    get_prices_cache_key,
    get_quality_cache_key,
)
from src.infrastructure.yfinance_adapter import (
    fetch_balance_sheet,
    fetch_cashflow,
    fetch_financials,
    fetch_prices_batch,
    fetch_ticker_info,
)
from src.models import Period, Price

router = APIRouter(
    prefix="/tickers",
    tags=["tickers"],
)


# ---------------------------------------------------------------------------
# Shared cache-aside helpers — every data source fetched exactly once
# ---------------------------------------------------------------------------


def _dataframe_from_prices_cache(cached: str) -> pd.DataFrame | None:
    """Deserialize prices written with DataFrame.to_json(orient='split')."""
    try:
        parsed: Any = json.loads(cached)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict) or "columns" not in parsed or "data" not in parsed:
        return None
    try:
        return pd.read_json(StringIO(cached), orient="split")
    except (TypeError, ValueError):
        return None


def _dataframe_from_split_cache(cached: str) -> pd.DataFrame | None:
    """Deserialize any DataFrame cached with orient='split'."""
    try:
        return pd.read_json(StringIO(cached), orient="split")
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


async def _get_prices_cached(
    tickers: list[str],
    period: Period,
    redis: Redis,
) -> dict[str, pd.DataFrame]:
    """Cache-aside price fetch shared by /prices and /returns."""
    out: dict[str, pd.DataFrame] = {}
    missing: list[str] = []

    for ticker in tickers:
        cached = await cache_get(redis, get_prices_cache_key(ticker, period))
        if cached is not None:
            df = _dataframe_from_prices_cache(cached)
            if df is not None:
                out[ticker] = df
                continue
        missing.append(ticker)

    if missing:
        # Fetch in batches of 10 with a small gap to avoid Yahoo rate limits.
        # Portfolios with 15-20 tickers were hitting 429 Too Many Requests.
        BATCH_SIZE = 10
        for i in range(0, len(missing), BATCH_SIZE):
            batch = missing[i : i + BATCH_SIZE]
            if i > 0:
                await asyncio.sleep(1)  # 1s between batches
            fetched = await fetch_prices_batch(batch, period)
            for ticker, df in fetched.items():
                payload = cast(
                    str,
                    df.to_json(orient="split", date_format="iso"),  # pyright: ignore[reportUnknownMemberType]
                )
                await cache_set(redis, get_prices_cache_key(ticker, period), payload)
                out[ticker] = df

    return out


async def _get_info_cached(ticker: str, redis: Redis) -> dict[str, Any]:
    """Cache-aside info fetch. Reused by /info and /quality."""
    cached = await cache_get(redis, get_info_cache_key(ticker))
    if cached is not None:
        return cast(dict[str, Any], json.loads(cached))
    out = await fetch_ticker_info(ticker)
    await cache_set(redis, get_info_cache_key(ticker), json.dumps(out), ttl=INFO_TTL)
    return out


async def _get_financials_cached(ticker: str, redis: Redis) -> pd.DataFrame:
    """Cache-aside financials fetch. Reused by /quality."""
    cached = await cache_get(redis, get_financials_cache_key(ticker))
    if cached is not None:
        df = _dataframe_from_split_cache(cached)
        if df is not None:
            return df
    df = await fetch_financials(ticker)
    payload = cast(
        str,
        df.to_json(orient="split", date_format="iso"),  # pyright: ignore[reportUnknownMemberType]
    )
    await cache_set(
        redis, get_financials_cache_key(ticker), payload, ttl=FUNDAMENTALS_TTL
    )
    return df


async def _get_balance_sheet_cached(ticker: str, redis: Redis) -> pd.DataFrame:
    """Cache-aside balance sheet fetch."""
    cached = await cache_get(redis, get_balance_sheet_cache_key(ticker))
    if cached is not None:
        df = _dataframe_from_split_cache(cached)
        if df is not None:
            return df
    df = await fetch_balance_sheet(ticker)
    payload = cast(
        str,
        df.to_json(orient="split", date_format="iso"),  # pyright: ignore[reportUnknownMemberType]
    )
    await cache_set(
        redis, get_balance_sheet_cache_key(ticker), payload, ttl=FUNDAMENTALS_TTL
    )
    return df


async def _get_cashflow_cached(ticker: str, redis: Redis) -> pd.DataFrame:
    """Cache-aside cash flow fetch."""
    cached = await cache_get(redis, get_cashflow_cache_key(ticker))
    if cached is not None:
        df = _dataframe_from_split_cache(cached)
        if df is not None:
            return df
    df = await fetch_cashflow(ticker)
    payload = cast(
        str,
        df.to_json(orient="split", date_format="iso"),  # pyright: ignore[reportUnknownMemberType]
    )
    await cache_set(
        redis, get_cashflow_cache_key(ticker), payload, ttl=FUNDAMENTALS_TTL
    )
    return df


# ---------------------------------------------------------------------------
# Route handlers — thin, delegate to cached helpers + domain functions
# ---------------------------------------------------------------------------


@router.get("/prices")
async def get_prices(
    tickers: list[str] = Query(..., description="The tickers to fetch prices for"),
    period: Period = Query(Period.MAX, description="The period to fetch prices for"),
    redis: Redis = Depends(get_redis_client),
) -> dict[str, list[Price]]:
    dfs = await _get_prices_cached(tickers, period, redis)
    return {
        ticker: Price.from_yfinance(
            json.loads(
                cast(
                    str,
                    df.to_json(orient="records", date_format="iso"),  # pyright: ignore[reportUnknownMemberType]
                )
            )
        )
        for ticker, df in dfs.items()
    }


@router.get("/returns")
async def get_returns(
    tickers: list[str] = Query(..., description="The tickers to compute returns for"),
    period: Period = Query(Period.MAX, description="The period to fetch prices for"),
    redis: Redis = Depends(get_redis_client),
) -> dict[str, dict[str, float]]:
    dfs = await _get_prices_cached(tickers, period, redis)

    close_df = pd.DataFrame({ticker: df["Close"] for ticker, df in dfs.items()})
    returns_df = compute_returns(close_df)

    returns_json = cast(
        str,
        returns_df.to_json(orient="columns", date_format="iso"),  # pyright: ignore[reportUnknownMemberType]
    )
    return cast(dict[str, dict[str, float]], json.loads(returns_json))


@router.get("/{ticker}/info")
async def get_info(
    ticker: str,
    redis: Redis = Depends(get_redis_client),
) -> dict[str, Any]:
    return await _get_info_cached(ticker, redis)


@router.get("/{ticker}/quality")
async def get_quality(
    ticker: str,
    redis: Redis = Depends(get_redis_client),
) -> dict[str, Any]:
    """Quality score, GARP score, thesis health check, and moat rating.

    Composes from the same cached data sources as /info, /financials, etc.
    If ticker info or financials were already fetched by another endpoint,
    the cached versions are reused — no duplicate yfinance calls.
    """
    cache_key = get_quality_cache_key(ticker)
    cached = await cache_get(redis, cache_key)
    if cached is not None:
        return cast(dict[str, Any], json.loads(cached))

    # Fetch info first to detect ETF vs stock
    info = await _get_info_cached(ticker, redis)

    if is_etf(info):
        # ETFs don't have financial statements — use simplified scoring
        empty = pd.DataFrame()
        result: dict[str, Any] = {
            "ticker": ticker,
            "type": "ETF",
            "quality_score": quality_score(info, empty, empty, empty),
            "garp_score": garp_score(info),
            "thesis_health": thesis_health_check(info, empty, empty, empty),
            "moat": "N/A",
            "category": info.get("category"),
            "fund_family": info.get("fundFamily"),
        }
    else:
        # Stocks: fetch full financial statements
        financials, balance_sheet, cashflow = await asyncio.gather(
            _get_financials_cached(ticker, redis),
            _get_balance_sheet_cached(ticker, redis),
            _get_cashflow_cached(ticker, redis),
        )
        result = {
            "ticker": ticker,
            "type": "EQUITY",
            "quality_score": quality_score(info, financials, balance_sheet, cashflow),
            "garp_score": garp_score(info),
            "thesis_health": thesis_health_check(
                info, financials, balance_sheet, cashflow
            ),
            "moat": moat_rating(financials, balance_sheet),
        }

    await cache_set(redis, cache_key, json.dumps(result, default=str))
    return result
