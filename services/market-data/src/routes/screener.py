# GET /screener/cheap-quality — scan global stock universe for cheap quality stocks

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from starlette.responses import StreamingResponse

from src.dependencies import get_redis_client
from src.domain.quality import garp_score, quality_score
from src.domain.screener import cheap_quality_score, screen_universe
from src.infrastructure.redis_cache import (
    INFO_TTL,
    cache_get,
    cache_set,
    get_info_cache_key,
    get_quality_cache_key,
)
from src.infrastructure.yfinance_adapter import (
    fetch_balance_sheet,
    fetch_cashflow,
    fetch_financials,
    fetch_ticker_info,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/screener",
    tags=["screener"],
)

# Batch size and delay for yfinance calls to avoid 429s on cold cache.
_BATCH_SIZE = 10
_BATCH_DELAY = 1.5  # seconds between batches

_DATA_DIR = Path(__file__).parent.parent / "data"

# Available ticker universes — loaded on first use
_UNIVERSES: dict[str, str] = {
    "us": "sp400.json",
    "us_large": "sp500.json",
    "us_extra": "us_extra.json",
    "israel": "israel.json",
    "europe": "europe.json",
    "emerging": "emerging_markets.json",
}


def _load_universe(name: str) -> list[str]:
    """Load a ticker universe by name. Returns empty list if not found."""
    filename = _UNIVERSES.get(name)
    if filename is None:
        return []
    path = _DATA_DIR / filename
    if not path.exists():
        return []
    with open(path) as f:
        tickers: list[str] = json.load(f)
    return tickers


def _load_universes(names: list[str]) -> list[str]:
    """Load and merge multiple universes, deduplicating."""
    seen: set[str] = set()
    result: list[str] = []
    for name in names:
        for t in _load_universe(name):
            if t not in seen:
                seen.add(t)
                result.append(t)
    return result


async def _get_info_cached_local(ticker: str, redis: Redis) -> dict[str, Any]:
    """Cache-aware info fetch for the screener — checks Redis before hitting yfinance."""
    cache_key = get_info_cache_key(ticker)
    cached = await cache_get(redis, cache_key)
    if cached is not None:
        return cast(dict[str, Any], json.loads(cached))
    info = await fetch_ticker_info(ticker)
    await cache_set(redis, cache_key, json.dumps(info), ttl=INFO_TTL)
    return info


async def _fetch_info_single(ticker: str, redis: Redis) -> dict[str, Any] | None:
    """Fetch ticker info with cache. Returns None on failure."""
    try:
        return await _get_info_cached_local(ticker, redis)
    except Exception:
        logger.warning("Failed to fetch info for %s", ticker, exc_info=True)
        return None


async def _fetch_quality_single(ticker: str, redis: Redis) -> dict[str, Any] | None:
    """Fetch quality score for one ticker with cache. Returns None on failure."""
    cache_key = get_quality_cache_key(ticker)
    cached = await cache_get(redis, cache_key)
    if cached is not None:
        return cast(dict[str, Any], json.loads(cached))

    try:
        info = await _get_info_cached_local(ticker, redis)
        fin = await fetch_financials(ticker)
        bs = await fetch_balance_sheet(ticker)
        cf = await fetch_cashflow(ticker)

        result: dict[str, Any] = {
            "ticker": ticker,
            "quality_score": quality_score(info, fin, bs, cf),
            "garp_score": garp_score(info),
        }
        await cache_set(redis, cache_key, json.dumps(result, default=str))
        return result
    except Exception:
        logger.warning("Failed to fetch quality for %s", ticker, exc_info=True)
        return None


def _sse(event_type: str, data: Any) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"


@router.get("/universes")
async def get_universes() -> dict[str, int]:
    """Return available universe names and their ticker counts."""
    return {name: len(_load_universe(name)) for name in _UNIVERSES}


@router.get("/cheap-quality")
async def get_cheap_quality(
    limit: int = Query(20, description="Max results to return"),
    min_quality: int = Query(50, description="Minimum quality score (0-100)"),
    universe: list[str] = Query(
        ["us"],
        description="Universes to scan: us (S&P 400 midcap), us_large (S&P 500), us_extra, israel, europe, emerging. Pass multiple to combine.",
    ),
    redis: Redis = Depends(get_redis_client),
) -> StreamingResponse:
    """SSE stream: emits progress events then the final result.

    Events:
      event: progress  data: {"pct": 0-100, "phase": "info"|"quality"}
      event: result    data: [<scored ticker objects>]
    """

    async def generate() -> AsyncGenerator[str]:
        tickers = _load_universes(universe)
        if not tickers:
            yield _sse("result", [])
            return

        # Check endpoint-level cache
        universes_key = ",".join(sorted(universe))
        result_cache_key = f"screener:{universes_key}:q{min_quality}:l{limit}"
        cached_result = await cache_get(redis, result_cache_key)
        if cached_result is not None:
            yield _sse("progress", {"pct": 100, "phase": "done"})
            yield _sse("result", json.loads(cached_result))
            return

        total = len(tickers)
        num_batches = (total + _BATCH_SIZE - 1) // _BATCH_SIZE
        # Phase 1 = 0-40%, Phase 2 = 40-95%, scoring = 95-100%

        # --- Phase 1: info ---
        info_results: list[dict[str, Any] | None] = []
        for batch_idx in range(num_batches):
            start = batch_idx * _BATCH_SIZE
            batch = tickers[start : start + _BATCH_SIZE]
            if batch_idx > 0:
                await asyncio.sleep(_BATCH_DELAY)
            batch_results = await asyncio.gather(
                *[_fetch_info_single(t, redis) for t in batch]
            )
            info_results.extend(batch_results)
            pct = round((batch_idx + 1) / num_batches * 40)
            yield _sse("progress", {"pct": pct, "phase": "info"})

        # --- Phase 2: quality ---
        quality_results: list[dict[str, Any] | None] = []
        for batch_idx in range(num_batches):
            start = batch_idx * _BATCH_SIZE
            batch = tickers[start : start + _BATCH_SIZE]
            if batch_idx > 0:
                await asyncio.sleep(_BATCH_DELAY)
            batch_results = await asyncio.gather(
                *[_fetch_quality_single(t, redis) for t in batch]
            )
            quality_results.extend(batch_results)
            pct = round(40 + (batch_idx + 1) / num_batches * 55)
            yield _sse("progress", {"pct": pct, "phase": "quality"})

        # --- Scoring ---
        scored: list[dict[str, Any]] = []
        for i, ticker in enumerate(tickers):
            q = quality_results[i]
            info = info_results[i]
            if q is None or info is None:
                continue
            cq_score = cheap_quality_score(q, info)
            scored.append(
                {
                    "ticker": ticker,
                    "quality_score": q.get("quality_score", 0),
                    "garp_score": q.get("garp_score", 0),
                    "cheap_quality_score": round(cq_score, 2),
                    "forward_pe": info.get("forwardPE"),
                    "peg_ratio": info.get("trailingPegRatio"),
                    "sector": info.get("sector"),
                }
            )

        results = screen_universe(scored, min_quality=min_quality, limit=limit)
        await cache_set(redis, result_cache_key, json.dumps(results), ttl=3600)

        yield _sse("progress", {"pct": 100, "phase": "done"})
        yield _sse("result", results)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
