"""Portfolio-level weighted fundamentals aggregation.

All functions are pure computation — no I/O. Input is pre-fetched data
from market-data-service endpoints (info, quality).
"""

from typing import Any


def compute_weighted_fundamentals(
    weights: dict[str, float],
    info_by_ticker: dict[str, dict[str, Any]],
) -> dict[str, float | None]:
    """Compute portfolio-weighted P/E, P/B, FCF yield, dividend yield, growth.

    weights: {ticker → portfolio weight}, sums to 1.0.
    info_by_ticker: {ticker → ticker.info dict from market-data-service}.
    """
    fields = {
        "weighted_pe": "trailingPE",
        "weighted_pb": "priceToBook",
        "weighted_fcf_yield": None,  # computed separately
        "weighted_dividend_yield": "dividendYield",
        "weighted_revenue_growth": "revenueGrowth",
        "weighted_earnings_growth": "earningsGrowth",
    }

    result: dict[str, float | None] = {}

    for output_key, info_key in fields.items():
        if info_key is None:
            continue
        total = 0.0
        total_weight = 0.0
        for ticker, w in weights.items():
            info = info_by_ticker.get(ticker, {})
            val = info.get(info_key)
            if val is not None and isinstance(val, (int, float)) and val > 0:
                total += w * float(val)
                total_weight += w
        result[output_key] = total / total_weight if total_weight > 0 else None

    # FCF yield = weighted average of (FCF / market cap) per ticker
    fcf_total = 0.0
    fcf_weight = 0.0
    for ticker, w in weights.items():
        info = info_by_ticker.get(ticker, {})
        fcf = info.get("freeCashflow")
        mcap = info.get("marketCap")
        if (
            fcf
            and mcap
            and isinstance(fcf, (int, float))
            and isinstance(mcap, (int, float))
            and mcap > 0
        ):
            fcf_total += w * (float(fcf) / float(mcap))
            fcf_weight += w
    result["weighted_fcf_yield"] = fcf_total / fcf_weight if fcf_weight > 0 else None

    return result


def compute_weighted_quality(
    weights: dict[str, float],
    quality_by_ticker: dict[str, dict[str, Any]],
) -> dict[str, float | None]:
    """Compute portfolio-weighted quality and GARP scores.

    quality_by_ticker: {ticker → quality response from GET /tickers/{ticker}/quality}.
    """
    q_total = 0.0
    q_weight = 0.0
    g_total = 0.0
    g_weight = 0.0

    for ticker, w in weights.items():
        quality = quality_by_ticker.get(ticker, {})
        qs = quality.get("quality_score")
        gs = quality.get("garp_score")
        if qs is not None:
            q_total += w * float(qs)
            q_weight += w
        if gs is not None:
            g_total += w * float(gs)
            g_weight += w

    return {
        "portfolio_quality_score": q_total / q_weight if q_weight > 0 else None,
        "portfolio_garp_score": g_total / g_weight if g_weight > 0 else None,
    }
