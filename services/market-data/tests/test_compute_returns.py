"""Tests for market-data domain: compute_returns.

Every expected value is computed by hand using the mathematical definitions.
No random data, no approximations — only exact or analytically derived values.

Log return definition:  r_t = ln(P_t / P_{t-1})
Log-linear interpolation:  interpolate on ln(P), then exp() back.
"""

import math

import numpy as np
import pandas as pd

from src.domain.market_data import compute_returns

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _prices_df(data: dict[str, list[float | None]], dates: list[str]) -> pd.DataFrame:
    """Build a price DataFrame matching yfinance structure."""
    index = pd.to_datetime(dates)
    return pd.DataFrame(
        {k: [np.nan if v is None else v for v in vals] for k, vals in data.items()},
        index=index,
    )


# ---------------------------------------------------------------------------
# Basic log returns
# ---------------------------------------------------------------------------


class TestBasicLogReturns:
    """Verify log returns match the formula: r_t = ln(P_t / P_{t-1})."""

    def test_two_day_single_ticker(self) -> None:
        """100 → 110: log return = ln(110/100) = ln(1.1) ≈ 0.09531."""
        prices = _prices_df(
            {"AAPL": [100.0, 110.0]},
            ["2024-01-02", "2024-01-03"],
        )
        result = compute_returns(prices)

        expected = math.log(110.0 / 100.0)  # 0.09531017980432486
        assert result.shape == (1, 1)
        assert result.columns.tolist() == ["AAPL"]
        np.testing.assert_almost_equal(result.iloc[0, 0], expected, decimal=10)

    def test_three_day_single_ticker(self) -> None:
        """100 → 110 → 121: two log returns, both ln(1.1)."""
        prices = _prices_df(
            {"AAPL": [100.0, 110.0, 121.0]},
            ["2024-01-02", "2024-01-03", "2024-01-04"],
        )
        result = compute_returns(prices)

        r1 = math.log(110.0 / 100.0)
        r2 = math.log(121.0 / 110.0)
        assert result.shape == (2, 1)
        np.testing.assert_almost_equal(result.iloc[0, 0], r1, decimal=10)
        np.testing.assert_almost_equal(result.iloc[1, 0], r2, decimal=10)

    def test_two_tickers(self) -> None:
        """Two tickers, independent log returns verified individually."""
        prices = _prices_df(
            {
                "AAPL": [100.0, 105.0, 110.0],
                "MSFT": [200.0, 210.0, 200.0],
            },
            ["2024-01-02", "2024-01-03", "2024-01-04"],
        )
        result = compute_returns(prices)

        assert result.shape == (2, 2)
        np.testing.assert_almost_equal(
            result["AAPL"].iloc[0], math.log(105.0 / 100.0), decimal=10
        )
        np.testing.assert_almost_equal(
            result["AAPL"].iloc[1], math.log(110.0 / 105.0), decimal=10
        )
        np.testing.assert_almost_equal(
            result["MSFT"].iloc[0], math.log(210.0 / 200.0), decimal=10
        )
        # 200/210 < 1, so log return is negative
        np.testing.assert_almost_equal(
            result["MSFT"].iloc[1], math.log(200.0 / 210.0), decimal=10
        )

    def test_first_row_dropped(self) -> None:
        """First row is always NaN (no P_{t-1}), so output has N-1 rows."""
        n_days = 10
        # Constant 1% daily growth: P_t = 100 * 1.01^t
        prices_list = [100.0 * (1.01**t) for t in range(n_days)]
        prices = _prices_df(
            {"A": prices_list},
            [f"2024-01-{d + 2:02d}" for d in range(n_days)],
        )
        result = compute_returns(prices)
        assert result.shape[0] == n_days - 1

    def test_log_returns_are_time_additive(self) -> None:
        """Key property: sum of daily log returns = total period log return.

        This is WHY we use log returns instead of simple returns.
        100 → 105 → 110.25 → 115.7625
        Total log return = ln(115.7625 / 100) = sum of daily log returns.
        """
        prices = _prices_df(
            {"A": [100.0, 105.0, 110.25, 115.7625]},
            ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
        )
        result = compute_returns(prices)

        daily_sum = result["A"].sum()
        total = math.log(115.7625 / 100.0)
        np.testing.assert_almost_equal(daily_sum, total, decimal=10)


# ---------------------------------------------------------------------------
# Interpolation: gaps ≤ 5 days filled with log-linear
# ---------------------------------------------------------------------------


class TestLogLinearInterpolation:
    """Log-linear interpolation: interpolate on log(price), then exp() back.

    This produces geometric fill — constant daily growth rate — which is
    the correct model for price data (prices grow multiplicatively, not
    additively).

    NOTE: pandas interpolate(limit=5) requires arrays with at least limit+1=6
    elements. All test DataFrames are padded with known prices to satisfy this.
    """

    def test_single_gap_filled(self) -> None:
        """Known, NaN, known in the middle of a longer series.

        Prices around gap: 100, NaN, 121.
        Log-linear fill: geometric mean √(100×121) = 110.
        Log returns across gap: ln(110/100), ln(121/110) — both ≈ 0.09531.
        """
        # Pad with constant prices before/after to satisfy min array size
        prices = _prices_df(
            {"A": [90.0, 95.0, 100.0, None, 121.0, 130.0, 140.0, 150.0]},
            [f"2024-01-{d + 2:02d}" for d in range(8)],
        )
        result = compute_returns(prices)

        # Find the returns around the gap (index 2→3 and 3→4 in prices)
        # After interpolation, price at index 3 = √(100 * 121) = 110
        expected = math.log(110.0 / 100.0)  # ≈ 0.09531
        # The return from day2→day3 (100→110)
        np.testing.assert_almost_equal(result.iloc[2, 0], expected, decimal=5)

    def test_three_consecutive_gaps(self) -> None:
        """100, NaN, NaN, NaN, end_price in the middle of a longer series.

        Total log return across 4 intervals = 0.4, so each daily = 0.1.
        """
        end_price = 100.0 * math.exp(0.4)  # ≈ 149.1825
        prices = _prices_df(
            {"A": [80.0, 90.0, 100.0, None, None, None, end_price, 160.0, 170.0]},
            [f"2024-01-{d + 2:02d}" for d in range(9)],
        )
        result = compute_returns(prices)

        # Returns at indices 2,3,4,5 (covering the 100→...→end_price span)
        # should each be 0.1 (total 0.4 over 4 intervals)
        expected_daily = 0.1
        for i in range(2, 6):
            np.testing.assert_almost_equal(result.iloc[i, 0], expected_daily, decimal=5)

    def test_five_consecutive_gaps_at_limit(self) -> None:
        """Exactly 5 consecutive NaN — this is the fill limit. All should be filled."""
        end_price = 100.0 * math.exp(0.6)  # ≈ 182.21
        # 10 days total: 2 known + 5 NaN + 1 known + 2 known
        prices_list: list[float | None] = [
            80.0,
            100.0,
            None,
            None,
            None,
            None,
            None,
            end_price,
            190.0,
            200.0,
        ]
        prices = _prices_df(
            {"A": prices_list},
            [f"2024-01-{d + 2:02d}" for d in range(10)],
        )
        result = compute_returns(prices)

        # 6 intervals from 100→end_price, total log return = 0.6, each = 0.1
        expected_daily = 0.1
        for i in range(1, 7):
            np.testing.assert_almost_equal(result.iloc[i, 0], expected_daily, decimal=4)

    def test_eleven_consecutive_gaps_exceeds_limit(self) -> None:
        """11 consecutive NaN exceeds limit=5 from both directions.

        interpolate(limit=5) fills 5 from the left anchor and 5 from the right
        anchor (limit_direction defaults to 'both'). A gap of 11 leaves at least
        1 unfilled NaN in the middle → that row is dropped by dropna().
        """
        # 14 elements: known + 11×NaN + known + known
        prices_list: list[float | None] = [
            100.0,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            200.0,
            210.0,
        ]
        prices = _prices_df(
            {"A": prices_list},
            [f"2024-01-{d + 2:02d}" for d in range(14)],
        )
        result = compute_returns(prices)

        # Fully filled would give 13 returns. With unfilled NaN, fewer rows.
        assert result.shape[0] < 13


# ---------------------------------------------------------------------------
# Forward fill (trailing NaN)
# ---------------------------------------------------------------------------


class TestForwardFill:
    """interpolate() cannot fill trailing NaN. ffill(limit=2) handles them."""

    def test_trailing_nan_filled_up_to_2(self) -> None:
        """Known prices followed by 2 trailing NaN — ffill carries last price."""
        prices = _prices_df(
            {"A": [90.0, 95.0, 100.0, 105.0, 110.0, 115.0, 120.0, None, None]},
            [f"2024-01-{d + 2:02d}" for d in range(9)],
        )
        result = compute_returns(prices)

        # After ffill(limit=2): last two NaN filled with 120.0
        # Last two log returns should be ln(120/120) = 0.0
        assert result.shape[0] == 8  # 9 prices - 1
        np.testing.assert_almost_equal(result.iloc[-1, 0], 0.0, decimal=10)
        np.testing.assert_almost_equal(result.iloc[-2, 0], 0.0, decimal=10)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_dataframe(self) -> None:
        """Empty input should return empty output without crashing."""
        prices = pd.DataFrame()
        result = compute_returns(prices)
        assert result.empty

    def test_single_row(self) -> None:
        """Single price row → zero log returns (first row always dropped)."""
        prices = _prices_df(
            {"A": [100.0]},
            ["2024-01-02"],
        )
        result = compute_returns(prices)
        assert result.empty

    def test_all_same_price(self) -> None:
        """Constant price → all log returns are exactly 0."""
        prices = _prices_df(
            {"A": [100.0, 100.0, 100.0, 100.0]},
            ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
        )
        result = compute_returns(prices)
        assert result.shape == (3, 1)
        for i in range(3):
            np.testing.assert_almost_equal(result.iloc[i, 0], 0.0, decimal=10)

    def test_result_has_no_nan(self) -> None:
        """After compute_returns, no NaN should remain — they're all dropped."""
        prices = _prices_df(
            {"A": [100.0, 110.0, None, 133.1, 146.41, 155.0, 160.0, 165.0]},
            [f"2024-01-{d + 2:02d}" for d in range(8)],
        )
        result = compute_returns(prices)
        assert not result.isna().any().any()
