"""Tests for risk-service domain modules.

All expected values are hand-computed from mathematical definitions.
No random data, no approximations beyond floating-point arithmetic.
"""

import numpy as np
import pandas as pd
import pytest

from src.domain.drawdown import compute_max_drawdown
from src.domain.internal_beta import (
    compute_correlation_to_portfolio,
    compute_internal_beta,
)
from src.domain.mctr import compute_mctr
from src.domain.sharpe import compute_sharpe
from src.domain.stress import compute_stress
from src.domain.var import compute_cvar, compute_var


def _returns_df(data: dict[str, list[float]]) -> pd.DataFrame:
    n = len(next(iter(data.values())))
    dates = pd.bdate_range("2024-01-02", periods=n)
    return pd.DataFrame(data, index=dates)


# ---------------------------------------------------------------------------
# Sharpe
# ---------------------------------------------------------------------------


class TestSharpe:
    def test_positive_return_positive_sharpe(self) -> None:
        """Positive mean returns with some variance → positive Sharpe."""
        returns = _returns_df({"A": [0.002, 0.001, 0.003, 0.001, 0.002] * 10})
        result = compute_sharpe(returns, {"A": 1.0}, risk_free_rate=0.0)
        assert result["sharpe"] > 0

    def test_zero_return_negative_sharpe_with_rf(self) -> None:
        """Zero mean return with positive risk-free rate → negative Sharpe."""
        returns = _returns_df({"A": [0.01, -0.01] * 25})
        result = compute_sharpe(returns, {"A": 1.0}, risk_free_rate=0.04)
        assert result["sharpe"] < 0

    def test_volatility_positive(self) -> None:
        returns = _returns_df({"A": [0.01, -0.01, 0.02, -0.02] * 10})
        result = compute_sharpe(returns, {"A": 1.0})
        assert result["volatility"] > 0


# ---------------------------------------------------------------------------
# Internal Beta
# ---------------------------------------------------------------------------


class TestInternalBeta:
    def test_identical_series_beta_one(self) -> None:
        """β of a series with itself = Var(X)/Var(X) = 1.0."""
        s = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02] * 5)
        beta = compute_internal_beta(s, s)
        assert beta == pytest.approx(1.0)

    def test_negated_series_beta_negative_one(self) -> None:
        """β of a negated series = -Var(X)/Var(X) = -1.0."""
        s = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02] * 5)
        beta = compute_internal_beta(-s, s)
        assert beta == pytest.approx(-1.0)

    def test_scaled_series_beta_equals_scale(self) -> None:
        """If candidate = 2 × portfolio, β = Cov(2X, X)/Var(X) = 2."""
        s = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02] * 5)
        beta = compute_internal_beta(2 * s, s)
        assert beta == pytest.approx(2.0)

    def test_correlation_identical_is_one(self) -> None:
        s = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02] * 5)
        corr = compute_correlation_to_portfolio(s, s)
        assert corr == pytest.approx(1.0)

    def test_correlation_bounded(self) -> None:
        a = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02] * 5)
        b = pd.Series([0.02, 0.01, -0.01, 0.03, 0.00] * 5)
        corr = compute_correlation_to_portfolio(a, b)
        assert -1.0 <= corr <= 1.0


# ---------------------------------------------------------------------------
# MCTR
# ---------------------------------------------------------------------------


class TestMCTR:
    def test_single_stock_mctr_equals_volatility(self) -> None:
        """With one stock, MCTR = σ (the entire risk is from that one stock)."""
        cov = np.array([[0.04]])  # variance = 0.04, σ = 0.2
        result = compute_mctr({"A": 1.0}, cov, ["A"])
        assert result["A"]["mctr"] == pytest.approx(0.2)
        assert result["A"]["pct_contribution"] == pytest.approx(1.0)

    def test_pct_contributions_sum_to_one(self) -> None:
        """Percentage contributions must sum to 1.0."""
        cov = np.array([[0.04, 0.01], [0.01, 0.09]])
        result = compute_mctr({"A": 0.6, "B": 0.4}, cov, ["A", "B"])
        total = sum(v["pct_contribution"] for v in result.values())
        assert total == pytest.approx(1.0)

    def test_higher_cov_higher_mctr(self) -> None:
        """Stock with higher variance contributes more to risk."""
        cov = np.array([[0.01, 0.005], [0.005, 0.09]])
        result = compute_mctr({"A": 0.5, "B": 0.5}, cov, ["A", "B"])
        assert result["B"]["mctr"] > result["A"]["mctr"]


# ---------------------------------------------------------------------------
# VaR & CVaR
# ---------------------------------------------------------------------------


class TestVaR:
    def test_var_is_negative(self) -> None:
        """VaR should be a negative number (a loss)."""
        returns = pd.Series(
            [
                0.01,
                -0.02,
                0.005,
                -0.03,
                0.01,
                -0.01,
                0.02,
                -0.04,
                0.01,
                0.005,
                -0.015,
                0.01,
                -0.025,
                0.015,
                -0.01,
                0.008,
                -0.035,
                0.012,
                -0.02,
                0.01,
            ]
        )
        var = compute_var(returns, 100000.0)
        assert var < 0

    def test_cvar_worse_than_var(self) -> None:
        """CVaR (expected shortfall) should be worse (more negative) than VaR."""
        returns = pd.Series(
            [
                0.01,
                -0.02,
                0.005,
                -0.03,
                0.01,
                -0.01,
                0.02,
                -0.04,
                0.01,
                0.005,
                -0.015,
                0.01,
                -0.025,
                0.015,
                -0.01,
                0.008,
                -0.035,
                0.012,
                -0.02,
                0.01,
            ]
        )
        var = compute_var(returns, 100000.0)
        cvar = compute_cvar(returns, 100000.0)
        assert cvar <= var

    def test_var_scales_with_portfolio_value(self) -> None:
        """Doubling portfolio value doubles the dollar VaR."""
        returns = pd.Series([-0.01, -0.02, -0.03, 0.01, 0.02] * 10)
        var_small = compute_var(returns, 50000.0)
        var_large = compute_var(returns, 100000.0)
        assert var_large == pytest.approx(2 * var_small)


# ---------------------------------------------------------------------------
# Max Drawdown
# ---------------------------------------------------------------------------


class TestDrawdown:
    def test_no_drawdown_for_constant_returns(self) -> None:
        """Constant positive returns → drawdown ≈ 0."""
        returns = pd.Series([0.001] * 50)
        result = compute_max_drawdown(returns, 100000.0)
        assert result["max_drawdown_pct"] == pytest.approx(0.0, abs=1e-10)

    def test_drawdown_is_negative(self) -> None:
        """Drawdown should be ≤ 0."""
        returns = pd.Series([0.01, -0.05, 0.02, -0.03, 0.01] * 10)
        result = compute_max_drawdown(returns, 100000.0)
        assert result["max_drawdown_pct"] <= 0

    def test_drawdown_dollars_proportional(self) -> None:
        returns = pd.Series([0.01, -0.05, 0.02, -0.03, 0.01] * 10)
        r1 = compute_max_drawdown(returns, 50000.0)
        r2 = compute_max_drawdown(returns, 100000.0)
        assert r2["max_drawdown_dollars"] == pytest.approx(
            2 * r1["max_drawdown_dollars"]
        )


# ---------------------------------------------------------------------------
# Stress Scenarios
# ---------------------------------------------------------------------------


class TestStress:
    def test_returns_both_windows(self) -> None:
        """Should compute results for both 2020_crash and 2022_shock."""
        dates = pd.bdate_range("2019-01-02", "2023-12-31")
        returns = pd.DataFrame(
            {"A": np.random.default_rng(42).normal(0, 0.01, len(dates))},
            index=dates,
        )
        result = compute_stress(returns, {"A": 1.0}, 100000.0)
        assert "2020_crash" in result
        assert "2022_shock" in result
        assert "return_pct" in result["2020_crash"]
        assert "dollars" in result["2020_crash"]

    def test_empty_window_returns_zero(self) -> None:
        """If data doesn't cover the stress window, return 0."""
        dates = pd.bdate_range("2023-01-02", periods=50)
        returns = pd.DataFrame({"A": [0.01] * 50}, index=dates)
        result = compute_stress(returns, {"A": 1.0}, 100000.0)
        assert result["2020_crash"]["return_pct"] == 0.0
