"""Hedging exposure analysis.

Analyses portfolio exposure to market beta, sectors, geographies,
and identifies correlation clusters (groups of highly correlated holdings).
"""

from typing import Any

import pandas as pd


def compute_portfolio_beta(
    weights: dict[str, float],
    info_by_ticker: dict[str, dict[str, Any]],
) -> float:
    """Weighted portfolio beta vs S&P 500."""
    total = 0.0
    total_weight = 0.0
    for ticker, w in weights.items():
        info = info_by_ticker.get(ticker, {})
        beta = info.get("beta") or info.get("beta3Year")
        if beta is not None and isinstance(beta, (int, float)):
            total += w * float(beta)
            total_weight += w
    return total / total_weight if total_weight > 0 else 1.0


def compute_correlation_clusters(
    returns: pd.DataFrame,
    tickers: list[str],
    threshold: float = 0.8,
) -> list[list[str | float]]:
    """Find pairs of holdings with pairwise correlation above threshold.

    Returns list of [ticker_a, ticker_b, correlation] triples.
    """
    corr = returns[tickers].corr()
    clusters: list[list[str | float]] = []

    for i, t1 in enumerate(tickers):
        for j, t2 in enumerate(tickers):
            if j <= i:
                continue
            val = float(corr.loc[t1, t2])
            if abs(val) >= threshold:
                clusters.append([t1, t2, round(val, 4)])

    return clusters
