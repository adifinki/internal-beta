"""Min-variance portfolio optimization.

Uses only the covariance matrix (Σ) — makes no return predictions.
Answers: "how should I reweight what I already own to reduce risk?"

The historical Sharpe and return in the response are informative only —
backward-looking performance scores, not optimization targets.
"""

import numpy as np
import pandas as pd
from pypfopt import EfficientFrontier, expected_returns

from src.domain.portfolio import compute_covariance


def optimize_min_variance(
    returns: pd.DataFrame,
    current_weights: dict[str, float],
    holdings: dict[str, float],
    prices: dict[str, float],
    risk_free_rate: float = 0.04,
) -> dict[str, object]:
    """Find the min-variance allocation across existing holdings.

    Args:
        returns: log returns DataFrame (index=dates, columns=tickers).
        current_weights: {ticker → current portfolio weight}.
        holdings: {ticker → number of shares}.
        prices: {ticker → current price per share}.
        risk_free_rate: for informative Sharpe calculation only.

    Returns:
        Dict with optimized_weights, metrics, rebalancing_trades.
    """
    tickers = list(current_weights.keys())
    cov = compute_covariance(returns[tickers])
    cov_df = pd.DataFrame(cov, index=tickers, columns=tickers)

    # Historical mean returns — used ONLY to report informative Sharpe,
    # NOT as an optimization input. min_volatility() ignores mu.
    # Convert log → simple returns because PyPortfolioOpt expects simple returns.
    simple = np.exp(returns[tickers]) - 1
    mu = expected_returns.mean_historical_return(  # pyright: ignore[reportUnknownMemberType]
        simple, returns_data=True, frequency=252
    )

    ef = EfficientFrontier(mu, cov_df)  # pyright: ignore[reportArgumentType]
    ef.min_volatility()

    raw_weights: dict[str, float] = ef.clean_weights()  # pyright: ignore[reportAssignmentType, reportUnknownMemberType]
    ret, vol, sharpe = ef.portfolio_performance(risk_free_rate=risk_free_rate)  # pyright: ignore[reportUnknownMemberType]

    # Compute rebalancing trades: how many shares to buy/sell
    total_value = sum(holdings[t] * prices[t] for t in tickers)
    trades: dict[str, float] = {}
    for t in tickers:
        target_value = total_value * raw_weights[t]
        current_value = holdings[t] * prices[t]
        delta_shares = (target_value - current_value) / prices[t]
        trades[t] = round(delta_shares, 2)

    return {
        "optimized_weights": raw_weights,
        "historical_annual_return": float(ret),
        "annual_volatility": float(vol),
        "historical_sharpe": float(sharpe),
        "current_weights": current_weights,
        "rebalancing_trades": trades,
    }
