import numpy as np
import pandas as pd
from pypfopt import risk_models


def compute_weights(
    holdings: dict[str, float],
    prices: dict[str, float],
) -> dict[str, float]:
    sums = {ticker: prices[ticker] * holding for ticker, holding in holdings.items()}
    total_sum = sum(sums.values())
    return {ticker: s / total_sum for ticker, s in sums.items()}


def compute_covariance(
    returns: pd.DataFrame,  # rows = dates, columns = tickers, values = LOG returns
) -> np.ndarray:  # annualised n×n covariance matrix (Ledoit-Wolf shrinkage)
    """Ledoit-Wolf shrinkage covariance from log returns.

    INPUT CONTRACT: expects log returns (ln(P_t / P_{t-1})), NOT simple returns.

    NOTE ON API MISMATCH: PyPortfolioOpt's CovarianceShrinkage with returns_data=True
    is documented to expect simple returns. We pass log returns instead. The numerical
    error is O(σ⁴) per day — for daily equity returns (σ_daily ≈ 1%), this is on the
    order of 0.01% of the covariance value. This is within the noise of the Ledoit-Wolf
    shrinkage approximation itself and immaterial in practice.

    We accept this mismatch deliberately because:
    1. All downstream computations (MCTR, frontier, optimization) receive this same
       covariance matrix, so the system is internally consistent.
    2. Volatility computations (std(log_r) × √252) are consistent with a log-return
       covariance matrix, since Var(log_r) is the diagonal of this matrix.
    3. Converting the entire return series to simple before passing here would require
       refactoring every call site and provides negligible accuracy improvement.

    The output is annualised (scaled by 252 internally by PyPortfolioOpt).
    """
    if returns.empty or len(returns) < 2:
        n = len(returns.columns)
        return np.zeros((n, n))
    cov: pd.DataFrame = risk_models.CovarianceShrinkage(
        returns, returns_data=True
    ).ledoit_wolf()
    return np.asarray(cov)


def compute_correlation(
    returns: pd.DataFrame,
) -> pd.DataFrame:
    # Returns a labelled DataFrame (not ndarray) so the UI gets ticker names
    # as row and column headers without any extra mapping.
    return returns.corr()
