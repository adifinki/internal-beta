import asyncio
from typing import Any

import httpx
import pandas as pd


async def fetch_returns(
    client: httpx.AsyncClient,
    tickers: list[str],
    period: str,
) -> pd.DataFrame:
    res = await client.get(
        "/tickers/returns",
        params={"tickers": tickers, "period": period},
        timeout=120.0,
    )
    res.raise_for_status()

    # Response shape: {ticker: {date_iso: return_value}}
    # pd.DataFrame(data) reconstructs: columns=tickers, index=date strings.
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
    """Fetch info for multiple tickers in parallel via market-data-service."""
    tasks = [fetch_ticker_info(client, t) for t in tickers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: dict[str, dict[str, Any]] = {}
    for ticker, result in zip(tickers, results, strict=True):
        if not isinstance(result, BaseException):
            out[ticker] = result
    return out


async def fetch_quality_batch(
    client: httpx.AsyncClient,
    tickers: list[str],
) -> dict[str, dict[str, Any]]:
    """Fetch quality scores for multiple tickers in parallel via market-data-service."""
    tasks = [fetch_ticker_quality(client, t) for t in tickers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: dict[str, dict[str, Any]] = {}
    for ticker, result in zip(tickers, results, strict=True):
        if not isinstance(result, BaseException):
            out[ticker] = result
    return out
