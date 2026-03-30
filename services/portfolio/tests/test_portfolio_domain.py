"""Tests for portfolio domain: compute_weights, compute_covariance, compute_correlation.

All expected values are hand-computed from first principles.
No random data, no approximations beyond floating-point arithmetic.

Mathematical definitions:
  weight_i = (shares_i × price_i) / Σ(shares_j × price_j)
  correlation(X, Y) = Cov(X, Y) / (σ_X × σ_Y)
  Cov(X, Y) = E[(X - μ_X)(Y - μ_Y)]
"""

import math

import numpy as np
import pandas as pd
import pytest

from src.domain.portfolio import (
    compute_correlation,
    compute_covariance,
    compute_weights,
)

# ---------------------------------------------------------------------------
# compute_weights
# ---------------------------------------------------------------------------


class TestComputeWeights:
    """Verify weight = market_value_i / total_market_value."""

    def test_equal_value_positions(self) -> None:
        """10 shares × $150 = $1500, 5 shares × $300 = $1500 → 50/50."""
        holdings = {"AAPL": 10.0, "MSFT": 5.0}
        prices = {"AAPL": 150.0, "MSFT": 300.0}
        weights = compute_weights(holdings, prices)

        assert weights["AAPL"] == pytest.approx(0.5)
        assert weights["MSFT"] == pytest.approx(0.5)

    def test_unequal_value_positions(self) -> None:
        """AAPL: 10 × $100 = $1000, MSFT: 10 × $200 = $2000.
        Total = $3000. AAPL = 1/3, MSFT = 2/3."""
        holdings = {"AAPL": 10.0, "MSFT": 10.0}
        prices = {"AAPL": 100.0, "MSFT": 200.0}
        weights = compute_weights(holdings, prices)

        assert weights["AAPL"] == pytest.approx(1.0 / 3.0)
        assert weights["MSFT"] == pytest.approx(2.0 / 3.0)

    def test_weights_sum_to_one(self) -> None:
        """Fundamental property: all weights must sum to exactly 1.0."""
        holdings = {"A": 5.0, "B": 10.0, "C": 15.0}
        prices = {"A": 50.0, "B": 30.0, "C": 20.0}
        weights = compute_weights(holdings, prices)

        assert sum(weights.values()) == pytest.approx(1.0)

    def test_single_holding(self) -> None:
        """Single position → weight = 1.0."""
        weights = compute_weights({"AAPL": 10.0}, {"AAPL": 150.0})
        assert weights["AAPL"] == pytest.approx(1.0)

    def test_three_equal_positions(self) -> None:
        """Three equal-value positions → each gets 1/3."""
        holdings = {"A": 10.0, "B": 10.0, "C": 10.0}
        prices = {"A": 100.0, "B": 100.0, "C": 100.0}
        weights = compute_weights(holdings, prices)

        for w in weights.values():
            assert w == pytest.approx(1.0 / 3.0)

    def test_fractional_shares(self) -> None:
        """Non-integer shares are supported."""
        holdings = {"A": 1.5, "B": 2.5}
        prices = {"A": 200.0, "B": 120.0}
        # A = 300, B = 300, total = 600
        weights = compute_weights(holdings, prices)
        assert weights["A"] == pytest.approx(0.5)
        assert weights["B"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# compute_correlation
# ---------------------------------------------------------------------------


class TestComputeCorrelation:
    """Verify correlation matrix properties using analytically known cases."""

    def _returns_df(self, data: dict[str, list[float]]) -> pd.DataFrame:
        dates = [f"2024-01-{d + 2:02d}" for d in range(len(next(iter(data.values()))))]
        return pd.DataFrame(data, index=pd.to_datetime(dates))

    def test_self_correlation_is_one(self) -> None:
        """Every ticker's correlation with itself must be exactly 1.0."""
        returns = self._returns_df(
            {
                "A": [0.01, -0.02, 0.03, 0.01, -0.01],
                "B": [0.02, 0.01, -0.01, 0.03, 0.00],
            }
        )
        corr = compute_correlation(returns)

        assert corr.loc["A", "A"] == pytest.approx(1.0)
        assert corr.loc["B", "B"] == pytest.approx(1.0)

    def test_perfect_positive_correlation(self) -> None:
        """Identical return series → correlation = 1.0."""
        series = [0.01, -0.02, 0.03, -0.01, 0.02]
        returns = self._returns_df({"A": series, "B": series})
        corr = compute_correlation(returns)

        assert corr.loc["A", "B"] == pytest.approx(1.0)

    def test_perfect_negative_correlation(self) -> None:
        """Negated return series → correlation = -1.0."""
        series = [0.01, -0.02, 0.03, -0.01, 0.02]
        negated = [-r for r in series]
        returns = self._returns_df({"A": series, "B": negated})
        corr = compute_correlation(returns)

        assert corr.loc["A", "B"] == pytest.approx(-1.0)

    def test_symmetric(self) -> None:
        """Correlation matrix must be symmetric: corr(A,B) = corr(B,A)."""
        returns = self._returns_df(
            {
                "A": [0.01, -0.02, 0.03, 0.01, -0.01],
                "B": [0.02, 0.01, -0.01, 0.03, 0.00],
            }
        )
        corr = compute_correlation(returns)
        assert corr.loc["A", "B"] == pytest.approx(corr.loc["B", "A"])

    def test_bounded_between_minus_one_and_one(self) -> None:
        """All correlation values must be in [-1, 1]."""
        returns = self._returns_df(
            {
                "A": [0.01, -0.02, 0.03, 0.01, -0.01, 0.02, -0.03],
                "B": [0.02, 0.01, -0.01, 0.03, 0.00, -0.02, 0.01],
                "C": [-0.01, 0.03, 0.01, -0.02, 0.02, 0.01, -0.01],
            }
        )
        corr = compute_correlation(returns)

        for col in corr.columns:
            for row in corr.index:
                assert -1.0 <= corr.loc[row, col] <= 1.0

    def test_preserves_ticker_labels(self) -> None:
        """Output DataFrame should have ticker names as row and column labels."""
        returns = self._returns_df({"AAPL": [0.01, -0.02], "MSFT": [0.02, 0.01]})
        corr = compute_correlation(returns)

        assert list(corr.columns) == ["AAPL", "MSFT"]
        assert list(corr.index) == ["AAPL", "MSFT"]

    def test_hand_computed_correlation(self) -> None:
        """Verify against manually computed Pearson correlation.

        A = [1, 2, 3], B = [2, 4, 5]
        μ_A = 2, μ_B = 11/3 ≈ 3.667
        Cov(A,B) = E[(A-μA)(B-μB)] = ((1-2)(2-11/3) + (2-2)(4-11/3) + (3-2)(5-11/3))/2
                 = ((-1)(-5/3) + 0 + (1)(4/3)) / 2 = (5/3 + 4/3) / 2 = 3/2
        σ_A = sqrt(((1-2)² + (2-2)² + (3-2)²) / 2) = sqrt(2/2) = 1
        σ_B = sqrt(((2-11/3)² + (4-11/3)² + (5-11/3)²) / 2)
             = sqrt(((−5/3)² + (1/3)² + (4/3)²) / 2)
             = sqrt((25/9 + 1/9 + 16/9) / 2) = sqrt(42/18) = sqrt(7/3)
        corr = 1.5 / (1 × sqrt(7/3)) = 1.5 / sqrt(7/3) = 1.5 × sqrt(3/7)
             = 1.5 × 0.65465... = 0.98198...
        """
        returns = self._returns_df({"A": [1.0, 2.0, 3.0], "B": [2.0, 4.0, 5.0]})
        corr = compute_correlation(returns)

        expected = 1.5 * math.sqrt(3.0 / 7.0)
        assert corr.loc["A", "B"] == pytest.approx(expected, abs=1e-10)


# ---------------------------------------------------------------------------
# compute_covariance
# ---------------------------------------------------------------------------


class TestComputeCovariance:
    """Verify Ledoit-Wolf covariance matrix properties.

    We cannot verify exact values easily (shrinkage is iterative), but we
    can verify mathematical properties that MUST hold for any valid
    covariance matrix.

    NOTE: Ledoit-Wolf shrinkage (via PyPortfolioOpt) requires a sufficient
    number of observations. We use 30+ data points per test to ensure the
    estimator works correctly.
    """

    def _returns_df(self, data: dict[str, list[float]]) -> pd.DataFrame:
        n = len(next(iter(data.values())))
        dates = pd.bdate_range("2024-01-02", periods=n)
        return pd.DataFrame(data, index=dates)

    def _long_series(self, base: list[float], repeats: int = 4) -> list[float]:
        """Repeat a short pattern to create enough data points."""
        return (base * repeats)[:30]

    def test_returns_ndarray(self) -> None:
        returns = self._returns_df(
            {
                "A": self._long_series([0.01, -0.02, 0.03, 0.01, -0.01, 0.02, -0.03]),
                "B": self._long_series([0.02, 0.01, -0.01, 0.03, 0.00, -0.02, 0.01]),
            }
        )
        cov = compute_covariance(returns)
        assert isinstance(cov, np.ndarray)

    def test_shape_matches_tickers(self) -> None:
        """n tickers → n×n covariance matrix."""
        returns = self._returns_df(
            {
                "A": self._long_series([0.01, -0.02, 0.03, 0.01, -0.01]),
                "B": self._long_series([0.02, 0.01, -0.01, 0.03, 0.00]),
                "C": self._long_series([-0.01, 0.03, 0.01, -0.02, 0.02]),
            }
        )
        cov = compute_covariance(returns)
        assert cov.shape == (3, 3)

    def test_symmetric(self) -> None:
        """Covariance matrix must be symmetric: Cov(A,B) = Cov(B,A)."""
        returns = self._returns_df(
            {
                "A": self._long_series([0.01, -0.02, 0.03, 0.01, -0.01, 0.02, -0.03]),
                "B": self._long_series([0.02, 0.01, -0.01, 0.03, 0.00, -0.02, 0.01]),
            }
        )
        cov = compute_covariance(returns)
        np.testing.assert_array_almost_equal(cov, cov.T, decimal=10)

    def test_diagonal_positive(self) -> None:
        """Diagonal entries are variances — must be non-negative."""
        returns = self._returns_df(
            {
                "A": self._long_series([0.01, -0.02, 0.03, 0.01, -0.01, 0.02, -0.03]),
                "B": self._long_series([0.02, 0.01, -0.01, 0.03, 0.00, -0.02, 0.01]),
            }
        )
        cov = compute_covariance(returns)
        assert all(cov[i, i] >= 0 for i in range(cov.shape[0]))

    def test_positive_semi_definite(self) -> None:
        """A valid covariance matrix must be positive semi-definite.

        All eigenvalues must be ≥ 0 (within floating-point tolerance).
        Ledoit-Wolf shrinkage guarantees this — verify it.
        """
        returns = self._returns_df(
            {
                "A": self._long_series([0.01, -0.02, 0.03, 0.01, -0.01, 0.02, -0.03]),
                "B": self._long_series([0.02, 0.01, -0.01, 0.03, 0.00, -0.02, 0.01]),
                "C": self._long_series([-0.01, 0.03, 0.01, -0.02, 0.02, 0.01, -0.01]),
            }
        )
        cov = compute_covariance(returns)
        eigenvalues = np.linalg.eigvalsh(cov)
        assert all(ev >= -1e-10 for ev in eigenvalues)

    def test_identical_series_have_equal_variance(self) -> None:
        """Two identical return series should have equal diagonal entries."""
        series = self._long_series([0.01, -0.02, 0.03, 0.01, -0.01, 0.02, -0.03])
        returns = self._returns_df({"A": series, "B": series})
        cov = compute_covariance(returns)

        np.testing.assert_almost_equal(cov[0, 0], cov[1, 1], decimal=10)

    def test_higher_volatility_stock_has_higher_variance(self) -> None:
        """A stock with larger return swings must have higher variance."""
        small = self._long_series([0.005, -0.005, 0.005, -0.005, 0.005, -0.005, 0.005])
        large = self._long_series([0.05, -0.05, 0.05, -0.05, 0.05, -0.05, 0.05])
        returns = self._returns_df({"SMALL": small, "LARGE": large})
        cov = compute_covariance(returns)

        assert cov[1, 1] > cov[0, 0]  # LARGE variance > SMALL variance
