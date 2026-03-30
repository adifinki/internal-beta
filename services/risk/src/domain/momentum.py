"""Momentum scoring for individual holdings.

Momentum is one of the most robust return factors in academic literature
(Jegadeesh & Titman 1993, Fama & French 2012). The standard definition:

    Raw momentum = 12-month return minus 1-month return
                   (skips the most recent month to avoid short-term reversal)

    Normalized momentum = raw_momentum / annualized_volatility
                          (risk-adjusted so high-vol stocks don't dominate)

Interpretation:
    > +0.5: Strong positive momentum — price trend is intact
      0 to +0.5: Mild positive momentum
    -0.5 to 0: Mild negative momentum — watch for further deterioration
    < -0.5: Negative momentum — trend is reversing

Why it matters for recommendations:
    - A high-quality stock (good ROIC, margins) in a downtrend may be entering
      a value trap. Smart money is reducing exposure for a reason.
    - Conversely, a stock with good momentum AND good quality is the strongest
      combination: fundamentals AND trend aligned.
    - A stock the system recommends adding should ideally have non-negative momentum.
      Recommending additions into a reversal is the most common systematic error
      in pure-fundamental approaches.

Pure domain module — no I/O, no FastAPI, no httpx.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_momentum(prices: pd.Series) -> dict[str, float | str]:
    """Compute momentum score for a single holding.

    Args:
        prices: daily closing price series (DatetimeIndex), at least 1 year.

    Returns:
        {
          score: normalized momentum (raw_momentum / annualized_vol),
          return_12m: total 12-month return,
          return_1m: total 1-month return,
          return_12m_skip1m: 12m-1m (the raw momentum signal),
          trend: "strong_up" | "up" | "neutral" | "down" | "strong_down"
        }
    """
    if len(prices) < 60:  # need at least 3 months of data
        return {
            "score": 0.0,
            "return_12m": 0.0,
            "return_1m": 0.0,
            "return_12m_skip1m": 0.0,
            "trend": "insufficient_data",
        }

    prices = prices.dropna().sort_index()
    n = len(prices)

    # 12-month return (252 trading days back)
    lookback_12m = min(252, n - 1)
    ret_12m = float(prices.iloc[-1] / prices.iloc[-lookback_12m] - 1)

    # 1-month return (21 trading days back)
    lookback_1m = min(21, n - 1)
    ret_1m = float(prices.iloc[-1] / prices.iloc[-lookback_1m] - 1)

    # Raw momentum: the return from t-12m to t-1m (skipping recent month).
    # This is (1 + ret_12m) / (1 + ret_1m) - 1, which equals P_{t-1m}/P_{t-12m} - 1.
    # Subtracting simple returns (ret_12m - ret_1m) is only an approximation
    # that breaks down for large returns (e.g. 50% 12m, 10% 1m: subtraction
    # gives 0.40, correct answer is 0.364 — a ~10% error).
    raw_momentum = (1 + ret_12m) / (1 + ret_1m) - 1

    # Annualized volatility from daily log returns (for normalization)
    log_r = np.log(prices / prices.shift(1)).dropna()
    ann_vol = float(np.std(log_r, ddof=1) * np.sqrt(252)) if len(log_r) > 10 else 0.15

    # Normalized score
    score = raw_momentum / ann_vol if ann_vol > 0 else 0.0

    # Trend label
    if score > 0.75:
        trend = "strong_up"
    elif score > 0.15:
        trend = "up"
    elif score > -0.15:
        trend = "neutral"
    elif score > -0.75:
        trend = "down"
    else:
        trend = "strong_down"

    return {
        "score": round(score, 4),
        "return_12m": round(ret_12m, 4),
        "return_1m": round(ret_1m, 4),
        "return_12m_skip1m": round(raw_momentum, 4),
        "trend": trend,
    }


def compute_portfolio_momentum(
    returns: pd.DataFrame,
    weights: dict[str, float],
) -> dict[str, float | str]:
    """Compute weighted-average momentum across portfolio holdings.

    Uses log returns to reconstruct a price index per holding, then
    computes individual momentum scores and weights them.
    """
    tickers = [t for t in weights if t in returns.columns]
    if not tickers:
        return {"score": 0.0, "trend": "insufficient_data"}

    scores: list[float] = []
    w_used: list[float] = []

    for t in tickers:
        r = returns[t].dropna()
        if len(r) < 60:
            continue
        # Reconstruct price index from log returns (set base = 100)
        prices = pd.Series(
            100.0 * np.exp(r.values.cumsum()),
            index=r.index,
        )
        result = compute_momentum(prices)
        scores.append(float(result["score"]))
        w_used.append(weights[t])

    if not scores:
        return {"score": 0.0, "trend": "insufficient_data"}

    total_w = sum(w_used)
    weighted_score = sum(s * w for s, w in zip(scores, w_used, strict=True)) / total_w

    if weighted_score > 0.75:
        trend = "strong_up"
    elif weighted_score > 0.15:
        trend = "up"
    elif weighted_score > -0.15:
        trend = "neutral"
    elif weighted_score > -0.75:
        trend = "down"
    else:
        trend = "strong_down"

    return {"score": round(weighted_score, 4), "trend": trend}
