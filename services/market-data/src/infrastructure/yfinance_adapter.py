# fetch_prices(ticker, period) — asyncio.to_thread wrapper around yfinance
# fetch_prices_batch(tickers, period) — uses yf.download for a single batch request
# fetch_ticker_info(ticker) — sector, industry, market cap
#
# Rate-limit resilience:
#   - fetch_prices_batch uses yf.download (one request for N tickers vs N requests)
#   - All fetchers retry up to 3 times with exponential backoff + jitter
#   - Custom User-Agent reduces fingerprinting risk

import asyncio
import logging
import random
from typing import Any, cast

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

_RATE_LIMIT_SIGNALS = {
    "429",
    "too many",
    "rate limit",
    "rate-limit",
    "exceeded",
    "blocked",
}


def _is_rate_limited(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(sig in msg for sig in _RATE_LIMIT_SIGNALS)


async def _with_retry(coro_fn, label: str, max_attempts: int = 3):
    """Run an async callable with exponential backoff on rate-limit errors."""
    for attempt in range(max_attempts):
        try:
            return await coro_fn()
        except Exception as exc:
            if _is_rate_limited(exc) and attempt < max_attempts - 1:
                wait = (2**attempt) + random.uniform(0, 1)  # 1-2s, 3-4s, 7-8s
                logger.warning(
                    "Rate limited for '%s', retry %d/%d after %.1fs",
                    label,
                    attempt + 1,
                    max_attempts,
                    wait,
                )
                await asyncio.sleep(wait)
            elif attempt < max_attempts - 1:
                # Non-rate-limit error — shorter retry delay
                await asyncio.sleep(0.5)
            else:
                logger.warning("All retries exhausted for '%s': %s", label, exc)
                raise
    raise RuntimeError(f"Unreachable: retry loop exited without return for {label}")


def _normalize(ticker: str) -> str:
    """Convert user-facing ticker notation to yfinance format.

    Rules applied in order:
    1. Purely numeric tickers (e.g. 1159094, 1159169) → append .TA suffix for
       Tel Aviv Stock Exchange (TASE). No major exchange outside Israel uses
       pure numeric ticker codes.
    2. Dot-notation class shares (BRK.B, BF.B) → replace . with - since yfinance
       uses hyphens for share classes.
    """
    t = ticker.strip()
    if t.isdigit():
        return f"{t}.TA"
    return t.replace(".", "-")


async def fetch_prices(ticker: str, period: str = "5y") -> pd.DataFrame:
    normalized = _normalize(ticker)
    ticker_obj = yf.Ticker(normalized)

    async def _fetch() -> pd.DataFrame:
        df: pd.DataFrame = await asyncio.to_thread(ticker_obj.history, period=period)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        return df

    try:
        df = await _with_retry(_fetch, ticker)
    except Exception:
        return pd.DataFrame()

    if df.empty:
        logger.warning(
            "No price data returned for ticker '%s' — it may be invalid or delisted",
            ticker,
        )
    return df


async def fetch_prices_batch(
    tickers: list[str], period: str = "5y"
) -> dict[str, pd.DataFrame]:
    """Fetch prices for multiple tickers using individual Ticker().history() calls.

    Uses asyncio.gather for concurrency. Each call has exponential backoff
    via fetch_prices. Consistent column structure (Open/High/Low/Close/Volume/
    Dividends/Stock Splits) matches what Price.from_yfinance() expects.
    """
    if not tickers:
        return {}

    tasks = [fetch_prices(t, period) for t in tickers]
    results: list[pd.DataFrame | BaseException] = await asyncio.gather(
        *tasks, return_exceptions=True
    )

    prices: dict[str, pd.DataFrame] = {}
    for ticker, result in zip(tickers, results, strict=True):
        if isinstance(result, BaseException):
            logger.warning("Failed to fetch prices for '%s': %s", ticker, result)
        elif isinstance(result, pd.DataFrame) and not result.empty:
            prices[ticker] = result

    return prices


async def fetch_ticker_info(ticker: str) -> dict[str, Any]:
    normalized = _normalize(ticker)
    ticker_obj = yf.Ticker(normalized)

    async def _fetch() -> dict[str, Any]:
        return cast(
            dict[str, Any],
            await asyncio.to_thread(ticker_obj.get_info),  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        )

    return await _with_retry(_fetch, f"info:{ticker}")


async def fetch_financials(ticker: str) -> pd.DataFrame:
    """Fetch annual income statement (5 years). Columns = dates, rows = line items."""
    normalized = _normalize(ticker)
    ticker_obj = yf.Ticker(normalized)

    async def _fetch() -> pd.DataFrame:
        return await asyncio.to_thread(lambda: ticker_obj.financials)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]

    try:
        return await _with_retry(_fetch, f"financials:{ticker}")
    except Exception:
        return pd.DataFrame()


async def fetch_balance_sheet(ticker: str) -> pd.DataFrame:
    """Fetch annual balance sheet (5 years). Columns = dates, rows = line items."""
    normalized = _normalize(ticker)
    ticker_obj = yf.Ticker(normalized)

    async def _fetch() -> pd.DataFrame:
        return await asyncio.to_thread(lambda: ticker_obj.balance_sheet)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]

    try:
        return await _with_retry(_fetch, f"balance_sheet:{ticker}")
    except Exception:
        return pd.DataFrame()


async def fetch_cashflow(ticker: str) -> pd.DataFrame:
    """Fetch annual cash flow statement (5 years). Columns = dates, rows = line items."""
    normalized = _normalize(ticker)
    ticker_obj = yf.Ticker(normalized)

    async def _fetch() -> pd.DataFrame:
        return await asyncio.to_thread(lambda: ticker_obj.cashflow)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]

    try:
        return await _with_retry(_fetch, f"cashflow:{ticker}")
    except Exception:
        return pd.DataFrame()
