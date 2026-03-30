"""Historical Sharpe ratio — backward-looking performance score.

CONVENTION: We use the GEOMETRIC Sharpe ratio (CAGR-based), not the
original Sharpe (1966) formula which uses the arithmetic mean.

    Geometric Sharpe = (CAGR - Rf) / σ
    CAGR = (∏(1 + r_simple))^(252/n) - 1
    σ = std(log(1 + r_simple), ddof=1) × √252

WHY CAGR AND NOT ARITHMETIC MEAN:
  Sharpe (1966) defined S = E[Rp - Rf] / σ(Rp - Rf) using arithmetic mean.
  The arithmetic annualized return ≈ CAGR + σ²/2 (Jensen's gap).
  For a portfolio with σ = 20% annual, arithmetic mean exceeds CAGR by ~2%.
  This means the arithmetic Sharpe is ~0.01-0.02 higher than what we report.

  We deliberately use CAGR because:
  1. It is what PyPortfolioOpt computes internally via mean_historical_return
     with compounding=True (the default). Using CAGR keeps the Sharpe ratio
     numerically consistent with the efficient frontier visualization.
  2. CAGR is the realized compound return — what an investor actually earned
     over the holding period. It is more honest for a buy-and-hold investor.
  3. Mixing CAGR in the frontier with arithmetic Sharpe in the metric card
     would show a portfolio dot below the curve even when the portfolio is
     efficient — a confusing visual contradiction.

  Callers should document this choice when displaying Sharpe ratios to users.

INPUT: daily SIMPLE returns (not log returns). Log conversion is done
internally where needed (volatility calculation).

Informative only. NOT used as an optimization target.
"""

import numpy as np
import pandas as pd


def sharpe_from_daily(
    daily_simple: np.ndarray, risk_free_rate: float
) -> tuple[float, float, float]:
    """Core Sharpe computation on a pre-computed daily simple return series.

    Returns (sharpe, ann_vol, ann_return). Shared by compute_sharpe and
    the optimal allocation scorer so both always use identical math.
    """
    n = len(daily_simple)
    if n == 0:
        return 0.0, 0.0, 0.0
    ann_return = float((1 + daily_simple).prod() ** (252 / n) - 1)
    # Volatility from log returns for consistency with covariance matrix
    daily_log = np.log1p(daily_simple)
    ann_vol = float(np.std(daily_log, ddof=1) * np.sqrt(252))
    sharpe = (ann_return - risk_free_rate) / ann_vol if ann_vol > 0 else 0.0
    return sharpe, ann_vol, ann_return


def sortino_from_daily(
    daily_simple: np.ndarray, mar: float = 0.0
) -> tuple[float, bool]:
    """Compute Sortino ratio from a daily simple return series.

    Uses CAGR (geometric mean) in the numerator — same convention as the
    Sharpe ratio in this module — so both ratios are directly comparable.
    Downside deviation sums over ALL N observations (not just negative ones),
    using MAR_daily = (1 + MAR)^(1/252) - 1 (exact daily compounding).

    Args:
        daily_simple: array of daily simple returns.
        mar: minimum acceptable return (annualised). Default 0.0 (capital preservation).

    Returns:
        (sortino, reliable) — reliable=False when fewer than 12 observations are
        below MAR (not enough data to estimate downside deviation).
    """
    n = len(daily_simple)
    if n == 0:
        return 0.0, False

    # CAGR — identical to sharpe_from_daily numerator
    ann_return = float((1 + daily_simple).prod() ** (252 / n) - 1) if n > 0 else 0.0

    # Convert annual MAR to exact daily MAR (compound, not divide-by-252)
    mar_daily = (1 + mar) ** (1 / 252) - 1
    shortfalls = np.minimum(daily_simple - mar_daily, 0.0)
    n_below = int(np.sum(daily_simple < mar_daily))
    downside_variance = float(np.mean(shortfalls**2))
    downside_dev_ann = float(np.sqrt(downside_variance) * np.sqrt(252))

    sortino = (ann_return - mar) / downside_dev_ann if downside_dev_ann > 0 else 0.0
    reliable = n_below >= 12
    return sortino, reliable


def compute_sharpe(
    returns: pd.DataFrame,
    weights: dict[str, float],
    risk_free_rate: float = 0.04,
) -> dict[str, float]:
    """Compute historical Sharpe and Sortino ratios for a given set of weights.

    Args:
        returns: log returns (index=dates, columns=tickers).
        weights: {ticker → weight}, sums to 1.0.
        risk_free_rate: annualised risk-free rate.

    Returns:
        {sharpe, volatility, annual_return, sortino, sortino_reliable}.
    """
    # Only use tickers present in the returns DataFrame (rate limits can cause gaps)
    tickers = [t for t in weights if t in returns.columns]
    if not tickers:
        return {
            "sharpe": 0.0,
            "volatility": 0.0,
            "annual_return": 0.0,
            "sortino": 0.0,
            "sortino_reliable": False,
        }
    w_total = sum(weights[t] for t in tickers)
    w = np.array([weights[t] / w_total for t in tickers])  # re-normalise

    # Convert log returns to simple, then aggregate correctly across assets
    simple_returns = np.exp(returns[tickers].values) - 1
    daily_simple = simple_returns @ w

    sharpe, ann_vol, ann_return = sharpe_from_daily(daily_simple, risk_free_rate)
    sortino, sortino_reliable = sortino_from_daily(daily_simple)
    return {
        "sharpe": sharpe,
        "volatility": ann_vol,
        "annual_return": ann_return,
        "sortino": sortino,
        "sortino_reliable": sortino_reliable,
    }
