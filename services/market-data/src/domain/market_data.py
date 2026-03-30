from typing import cast

import numpy as np
import pandas as pd


def compute_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Compute daily log returns from a DataFrame of close prices.

    Expected input
    --------------
    A DataFrame where each column is one ticker's close price series,
    indexed by date (trading days only, as returned by yfinance).
    Example:
                   AAPL    MSFT
        2024-01-02  185.2   374.0
        2024-01-03  184.4   373.1
        ...

    Missing prices
    --------------
    Short gaps (≤ 5 consecutive missing days) are filled with linear
    interpolation — e.g. $1 on day 1, $4 on day 4 → $2, $3 on days 2–3.
    Gaps longer than 5 days are left as NaN and the affected rows are
    dropped. Filling more than a trading week of missing prices would
    introduce artificial price movements large enough to distort covariance
    and VaR calculations.

    Why log returns, not simple returns?
    -------------------------------------
    Simple return:  (P_t - P_{t-1}) / P_{t-1}
    Log return:     ln(P_t / P_{t-1})

    Two reasons we prefer log returns here:
    1. Time-additivity: a 3-day log return is simply the sum of 3 daily log
       returns. Simple returns compound multiplicatively, making aggregation
       harder.
    2. Normality: log returns are closer to normally distributed than simple
       returns. The covariance matrix (Ledoit-Wolf) and parametric VaR both
       assume approximate normality — log returns make that assumption more
       defensible.

    Returns
    -------
    DataFrame of the same column structure as the input, with one fewer row
    (the first row is always NaN after differencing and is dropped).
    Rows that still contain NaN after interpolation are also dropped.
    """
    # ── Step 1: fill short internal gaps with log-linear interpolation ──────────
    # Why log-linear instead of plain linear?
    # Prices grow multiplicatively — a stock going from $1 to $4 in 3 days
    # most plausibly grew at a constant *rate* each day (×1.587 each step),
    # not by a constant *dollar amount* ($1/day). Interpolating on log(price)
    # and then exponentiating back captures that compounding behaviour.
    #
    # Implementation: interpolate on the log-transformed prices (which turns
    # the geometric curve into a straight line), then undo the log with exp().
    # limit=5 caps how many consecutive NaNs we fill — gaps longer than one
    # trading week suggest bad data or a trading halt and should not be papered
    # over with synthetic prices.
    log_prices = cast(pd.DataFrame, np.log(prices))
    filled_log = log_prices.interpolate(method="linear", limit=5)  # pyright: ignore[reportUnknownMemberType]
    filled = cast(pd.DataFrame, np.exp(filled_log))

    # ── Step 2: forward-fill any remaining gaps at the tail of a series ───────
    # interpolate() cannot fill trailing NaN (no right anchor), so ffill
    # carries the last valid price forward for up to 2 days.
    filled = filled.ffill(limit=2)

    # ── Step 3: compute log returns ───────────────────────────────────────────
    # np.log(P_t / P_{t-1})  ≡  np.log(P_t) - np.log(P_{t-1})
    # .shift(1) shifts the column down by one row so each cell is divided
    # by the previous day's price.
    log_returns: pd.DataFrame = np.log(filled / filled.shift(1))

    # ── Step 4: drop rows that are still incomplete ───────────────────────────
    # - First row is always NaN (no P_{t-1} to divide by).
    # - Rows where ALL tickers are NaN are useless — drop them.
    # - Rows where only SOME tickers are NaN (e.g. BRK.B on NYSE has different
    #   holidays than NASDAQ tickers) are filled with 0.0 (no return = price
    #   unchanged on that day) rather than dropping the entire row, which would
    #   eliminate valid data for all other tickers.
    #
    #   KNOWN LIMITATION: filling with 0.0 slightly suppresses volatility and
    #   cross-market correlation for tickers on exchanges with different holiday
    #   calendars (e.g. TASE vs NYSE). For a portfolio mixing US and Israeli
    #   stocks, ~10 days/year get artificial zero returns for one side, which
    #   biases pairwise correlation downward by a few percent. This is standard
    #   practice (forward-fill price = zero return) and preferable to dropping
    #   data, but users should be aware of the effect on multi-market portfolios.
    #
    # Drop rows where every value is NaN (truly empty dates)
    log_returns = log_returns.dropna(how="all")
    # For remaining isolated NaNs (calendar mismatches), fill with 0 = no move
    return log_returns.fillna(0.0)
