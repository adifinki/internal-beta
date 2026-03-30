"""Marginal Contribution to Risk (MCTR).

MCTR_i = (Σ · w)_i / σ_portfolio

Tells you which position is driving portfolio risk.
"""

import numpy as np


def compute_mctr(
    weights: dict[str, float],
    cov_matrix: np.ndarray,
    tickers: list[str],
) -> dict[str, dict[str, float]]:
    """MCTR per holding.

    Returns: {ticker: {mctr, pct_contribution}}.
    """
    w = np.array([weights[t] for t in tickers])
    port_var = float(w @ cov_matrix @ w)
    port_vol = float(np.sqrt(port_var))

    if port_vol == 0:
        return {t: {"mctr": 0.0, "pct_contribution": 0.0} for t in tickers}

    sigma_w = cov_matrix @ w
    mctr = sigma_w / port_vol

    contributions = w * mctr
    total = float(np.sum(contributions))

    return {
        t: {
            "mctr": float(mctr[i]),
            "pct_contribution": float(contributions[i] / total) if total > 0 else 0.0,
        }
        for i, t in enumerate(tickers)
    }
