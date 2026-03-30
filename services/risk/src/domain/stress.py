"""Stress scenario analysis.

Simulates portfolio performance during historical market shocks.
Uses actual returns from defined date windows — no assumptions, no models.

2020 crash: 2020-02-19 to 2020-03-23 (COVID shock, S&P -34%)
2022 shock: 2022-01-03 to 2022-12-31 (rate hikes, S&P -19%)
"""

import numpy as np
import pandas as pd

STRESS_WINDOWS: dict[str, tuple[str, str]] = {
    "2020_crash": ("2020-02-19", "2020-03-23"),
    "2022_shock": ("2022-01-03", "2022-12-31"),
}


def compute_stress(
    returns: pd.DataFrame,
    weights: dict[str, float],
    portfolio_value: float,
) -> dict[str, dict[str, float]]:
    """Compute portfolio performance during each stress window.

    Args:
        returns: log returns (index=dates, columns=tickers).
        weights: {ticker → weight}.
        portfolio_value: total current portfolio value.

    Returns:
        {window_name: {return_pct, dollars}}.
    """
    tickers = [t for t in weights if t in returns.columns]
    if not tickers:
        return {name: {"return_pct": 0.0, "dollars": 0.0} for name in STRESS_WINDOWS}
    total_w = sum(weights[t] for t in tickers)
    w = (
        np.array([weights[t] / total_w for t in tickers])
        if total_w > 0
        else np.zeros(len(tickers))
    )

    result: dict[str, dict[str, float]] = {}

    for name, (start, end) in STRESS_WINDOWS.items():
        window = returns.loc[start:end, tickers]  # type: ignore[misc]
        if window.empty:
            result[name] = {"return_pct": 0.0, "dollars": 0.0}
            continue

        # Convert log returns to simple returns BEFORE cross-sectional aggregation.
        # Weighted sum of simple returns is the exact portfolio simple return;
        # weighted sum of log returns is only an approximation that breaks down
        # during high-volatility stress periods (exactly when accuracy matters).
        simple_window = np.exp(window.values) - 1
        daily_simple = simple_window @ w
        # Compound simple returns across the window
        cum_return = float(np.prod(1 + daily_simple) - 1)

        result[name] = {
            "return_pct": cum_return,
            "dollars": cum_return * portfolio_value,
        }

    return result
