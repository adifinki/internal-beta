"""Max drawdown calculation.

Maximum peak-to-trough decline in portfolio value.
More intuitive than VaR for most investors.

NOTE: max_drawdown_dollars applies the historical drawdown percentage to
today's portfolio value. It answers "if that drawdown happened now, how
much would I lose?" — a hypothetical stress scenario, not the actual
historical dollar loss (which occurred at a different portfolio size).

INPUT: daily SIMPLE returns (not log returns).
"""

import pandas as pd


def compute_max_drawdown(
    portfolio_returns: pd.Series,
    portfolio_value: float,
) -> dict[str, float]:
    """Max drawdown as a percentage, in hypothetical dollars, and recovery days.

    Args:
        portfolio_returns: daily simple returns of the portfolio.
        portfolio_value: current total portfolio value.

    Returns:
        {max_drawdown_pct, max_drawdown_dollars, recovery_days}.

        max_drawdown_dollars is a **hypothetical** figure: the historical
        drawdown percentage applied to today's portfolio value. It answers
        "if that drawdown happened now, how much would I lose?" — not "how
        much did I actually lose."
    """
    if portfolio_returns.empty or portfolio_returns.dropna().empty:
        return {
            "max_drawdown_pct": 0.0,
            "max_drawdown_dollars": 0.0,
            "recovery_days": 0,
        }

    # For simple returns: cumulative wealth = cumprod(1 + r)
    cum_returns = (1 + portfolio_returns).cumprod()
    running_max = cum_returns.cummax()
    drawdowns = cum_returns / running_max - 1

    max_dd_pct = float(drawdowns.min())

    # Recovery days: from the trough to the next time wealth reaches the prior peak
    trough_idx = drawdowns.idxmin()
    recovery_days = 0
    if trough_idx is not None:
        after_trough = cum_returns.loc[trough_idx:]  # type: ignore[arg-type]
        peak_before = float(running_max.loc[trough_idx])  # type: ignore[arg-type]
        # Skip the trough day itself, find first day at or above the prior peak
        post_trough = after_trough.iloc[1:]
        recovered = post_trough[post_trough >= peak_before]
        if len(recovered) > 0:
            recovery_days = len(after_trough.loc[: recovered.index[0]])  # type: ignore[index]
        else:
            recovery_days = len(after_trough)

    return {
        "max_drawdown_pct": max_dd_pct,
        "max_drawdown_dollars": max_dd_pct * portfolio_value,
        "recovery_days": recovery_days,
    }
