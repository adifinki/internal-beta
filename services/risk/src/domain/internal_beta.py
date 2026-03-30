"""Internal / Synthetic Beta.

β_internal = Cov(r_candidate, r_portfolio) / Var(r_portfolio)

Measures how a candidate stock moves relative to YOUR portfolio, not the S&P 500.
β > 1: candidate amplifies portfolio moves.
β < 0: candidate moves against the portfolio (natural hedge).
"""

import numpy as np
import pandas as pd


def compute_internal_beta(
    candidate_returns: pd.Series,
    portfolio_returns: pd.Series,
) -> float:
    """Internal beta of a candidate vs the portfolio.

    Both series must be aligned on the same date index.
    """
    aligned = pd.concat([candidate_returns, portfolio_returns], axis=1).dropna()
    if len(aligned) < 3:
        return 0.0

    cand = aligned.iloc[:, 0].values
    port = aligned.iloc[:, 1].values

    cov = float(np.cov(cand, port, ddof=1)[0, 1])
    var_port = float(np.var(port, ddof=1))

    if var_port == 0:
        return 0.0
    return cov / var_port


def compute_correlation_to_portfolio(
    candidate_returns: pd.Series,
    portfolio_returns: pd.Series,
) -> float:
    """Pearson correlation between candidate and portfolio returns."""
    aligned = pd.concat([candidate_returns, portfolio_returns], axis=1).dropna()
    if len(aligned) < 3:
        return 0.0
    return float(np.corrcoef(aligned.iloc[:, 0], aligned.iloc[:, 1])[0, 1])
