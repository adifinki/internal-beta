"""Async httpx clients for market-data-service and portfolio-service.

All data flows through the existing service endpoints — no direct yfinance access.
"""

import asyncio
from typing import Any

import httpx
import pandas as pd


async def fetch_returns(
    client: httpx.AsyncClient,
    tickers: list[str],
    period: str,
) -> pd.DataFrame:
    """Call GET /tickers/returns on market-data-service."""
    res = await client.get(
        "/tickers/returns",
        params={"tickers": tickers, "period": period},
        timeout=60.0,
    )
    res.raise_for_status()
    data: dict[str, dict[str, float]] = res.json()
    return pd.DataFrame(data)


async def fetch_ticker_info(
    client: httpx.AsyncClient,
    ticker: str,
) -> dict[str, Any]:
    """Call GET /tickers/{ticker}/info on market-data-service."""
    res = await client.get(f"/tickers/{ticker}/info", timeout=30.0)
    res.raise_for_status()
    return res.json()  # type: ignore[no-any-return]


async def fetch_ticker_quality(
    client: httpx.AsyncClient,
    ticker: str,
) -> dict[str, Any]:
    """Call GET /tickers/{ticker}/quality on market-data-service."""
    res = await client.get(f"/tickers/{ticker}/quality", timeout=30.0)
    res.raise_for_status()
    return res.json()  # type: ignore[no-any-return]


async def fetch_info_batch(
    client: httpx.AsyncClient,
    tickers: list[str],
) -> dict[str, dict[str, Any]]:
    """Fetch info for multiple tickers in parallel."""
    tasks = [fetch_ticker_info(client, t) for t in tickers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {
        t: r
        for t, r in zip(tickers, results, strict=True)
        if not isinstance(r, BaseException)
    }


async def fetch_quality_batch(
    client: httpx.AsyncClient,
    tickers: list[str],
) -> dict[str, dict[str, Any]]:
    """Fetch quality scores for multiple tickers in parallel."""
    tasks = [fetch_ticker_quality(client, t) for t in tickers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {
        t: r
        for t, r in zip(tickers, results, strict=True)
        if not isinstance(r, BaseException)
    }
