"""Efficient frontier computation (descriptive, historical).

Computes the frontier curve using historical returns and Ledoit-Wolf
covariance. This is a backward-looking visualization. NOT a prediction.

INPUT CONTRACT: all public functions expect LOG returns (ln(P_t/P_{t-1})).

RETURN CONVENTION: uses CAGR (geometric mean) for the Y-axis, not
arithmetic mean. See sharpe.py for the full explanation of this choice.
Consistency: the portfolio dot and individual holding dots all use the
same CAGR formula as the frontier curve, so no dot can appear above the
frontier due to a formula mismatch.

COVARIANCE: computed from log returns via compute_covariance (Ledoit-Wolf).
The X-axis volatility = sqrt(diag(cov)), consistent with the same matrix.

SIMPLE RETURNS: PyPortfolioOpt's mean_historical_return and portfolio_performance
expect simple returns for the RETURN axis. We convert log → simple
(exp(r) - 1) at the PyPortfolioOpt boundary only — covariance stays in
log-return space.
"""

import numpy as np
import pandas as pd
from pypfopt import EfficientFrontier, expected_returns

from src.domain.portfolio import compute_covariance


def _log_to_simple(log_returns: pd.DataFrame) -> pd.DataFrame:
    """Convert log returns to simple returns: exp(r) - 1."""
    return np.exp(log_returns) - 1  # type: ignore[return-value]


def compute_efficient_frontier(
    returns: pd.DataFrame,
    n_points: int = 30,
) -> list[dict[str, float]]:
    """Compute frontier points by sweeping target volatility."""
    simple = _log_to_simple(returns)
    cov = compute_covariance(returns)

    # PyPortfolioOpt expects simple returns for mean_historical_return
    mu = expected_returns.mean_historical_return(  # pyright: ignore[reportUnknownMemberType]
        simple, returns_data=True, frequency=252
    )

    cov_df = pd.DataFrame(cov, index=returns.columns, columns=returns.columns)

    # Find min-variance portfolio to get the left edge
    ef_min = EfficientFrontier(mu, cov_df)  # pyright: ignore[reportArgumentType]
    ef_min.min_volatility()
    min_ret, min_vol, _ = ef_min.portfolio_performance()  # pyright: ignore[reportUnknownMemberType]

    # Find the max volatility of any individual asset for the right edge.
    # cov is already annualised by Ledoit-Wolf (returns_data=True × 252),
    # so diag values are annual variances — just take sqrt.
    individual_vols = np.sqrt(np.diag(cov))
    max_vol = float(np.max(individual_vols))

    # Sweep from min_vol to max_vol
    points: list[dict[str, float]] = []
    targets = np.linspace(min_vol * 1.001, max_vol, n_points)

    for target_vol in targets:
        try:
            ef = EfficientFrontier(mu, cov_df)  # pyright: ignore[reportArgumentType]
            ef.efficient_risk(float(target_vol))  # pyright: ignore[reportUnknownMemberType]
            ret, vol, _ = ef.portfolio_performance()  # pyright: ignore[reportUnknownMemberType]
            points.append({"volatility": float(vol), "historical_return": float(ret)})
        except Exception:
            continue

    # Prepend the min-variance point
    points.insert(
        0, {"volatility": float(min_vol), "historical_return": float(min_ret)}
    )

    return points


def compute_portfolio_frontier_position(
    weights: dict[str, float],
    returns: pd.DataFrame,
) -> dict[str, float]:
    """Where the current portfolio sits on the risk/return plane.

    Uses the SAME return method as the frontier curve: w @ mu, where mu
    is per-ticker CAGR from PyPortfolioOpt's mean_historical_return.

    NOTE: w @ mu is the weighted average of individual CAGRs, NOT the
    portfolio CAGR. Due to Jensen's inequality these can differ slightly
    (weighted avg of geometric means vs geometric mean of weighted sums).
    We use w @ mu deliberately because PyPortfolioOpt's efficient_risk()
    uses the same formula for frontier points. Using the true portfolio
    CAGR would place the dot on a different Y-axis scale than the curve,
    potentially showing the portfolio above the frontier — a visual
    contradiction. Both formulas are "wrong" in the same way, so the
    relative positioning is correct.
    """
    simple = _log_to_simple(returns)
    tickers = list(weights.keys())
    w = np.array([weights[t] for t in tickers])

    # Annualised return: w @ mu where mu is per-ticker CAGR — identical to
    # PyPortfolioOpt's mean_historical_return(compounding=True). This ensures
    # the portfolio dot uses the same formula as the frontier curve points.
    mu = expected_returns.mean_historical_return(  # pyright: ignore[reportUnknownMemberType]
        simple, returns_data=True, frequency=252
    )
    ann_return = float(np.dot(w, [mu[t] for t in tickers]))

    # Annualised volatility (on log returns for consistency with covariance)
    daily_log = returns[tickers].values @ w
    ann_vol = float(np.std(daily_log, ddof=1) * np.sqrt(252))

    return {"volatility": ann_vol, "historical_return": ann_return}


def compute_individual_positions(
    returns: pd.DataFrame,
) -> list[dict[str, str | float]]:
    """Each holding as a dot: {ticker, volatility, historical_return}."""
    simple = _log_to_simple(returns)
    positions: list[dict[str, str | float]] = []
    for ticker in returns.columns:
        s = simple[ticker].dropna()
        r = returns[ticker].dropna()
        n = len(s)
        ann_return = float((1 + s).prod() ** (252 / n) - 1) if n > 0 else 0.0
        ann_vol = float(r.std(ddof=1) * np.sqrt(252))
        positions.append(
            {
                "ticker": ticker,
                "volatility": ann_vol,
                "historical_return": ann_return,
            }
        )
    return positions
