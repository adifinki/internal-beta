"""Tests for market-data domain: quality scoring.

All test data represents plausible financial statement values.
Expected scores are computed from the scoring thresholds defined in quality.py.
No random data — every input maps to a deterministic, traceable score.
"""

from typing import Any

import pandas as pd

from src.domain.quality import (
    garp_score,
    moat_rating,
    quality_score,
    thesis_health_check,
)

# ---------------------------------------------------------------------------
# Test fixtures — realistic financial data
# ---------------------------------------------------------------------------


def _financials(
    revenue: list[float],
    gross_profit: list[float],
    operating_income: list[float],
    net_income: list[float],
    tax_rate: list[float],
) -> pd.DataFrame:
    """Build a financials DataFrame matching yfinance .financials shape.

    Columns = dates (most recent first), rows = line items.
    """
    dates = pd.to_datetime([f"202{4 - i}-12-31" for i in range(len(revenue))])
    return pd.DataFrame(
        {
            d: {
                "Total Revenue": revenue[i],
                "Gross Profit": gross_profit[i],
                "Operating Income": operating_income[i],
                "Net Income": net_income[i],
                "Tax Rate For Calcs": tax_rate[i],
            }
            for i, d in enumerate(dates)
        }
    )


def _balance_sheet(invested_capital: list[float]) -> pd.DataFrame:
    """Build a balance sheet DataFrame."""
    dates = pd.to_datetime([f"202{4 - i}-12-31" for i in range(len(invested_capital))])
    return pd.DataFrame(
        {d: {"Invested Capital": invested_capital[i]} for i, d in enumerate(dates)}
    )


def _cashflow(free_cash_flow: list[float]) -> pd.DataFrame:
    """Build a cashflow DataFrame."""
    dates = pd.to_datetime([f"202{4 - i}-12-31" for i in range(len(free_cash_flow))])
    return pd.DataFrame(
        {d: {"Free Cash Flow": free_cash_flow[i]} for i, d in enumerate(dates)}
    )


def _high_quality_info() -> dict[str, Any]:
    """Info dict for a high-quality company (AAPL-like)."""
    return {
        "grossMargins": 0.46,
        "freeCashflow": 100_000_000_000,
        "marketCap": 3_000_000_000_000,
        "debtToEquity": 60.0,
        "revenueGrowth": 0.12,
        "trailingPegRatio": 1.2,
        "earningsGrowth": 0.15,
        "forwardPE": 28.0,
        "currentRatio": 1.1,
    }


def _high_quality_financials() -> pd.DataFrame:
    return _financials(
        revenue=[400e9, 380e9, 365e9, 350e9, 330e9],
        gross_profit=[184e9, 171e9, 160e9, 152e9, 142e9],
        operating_income=[130e9, 120e9, 115e9, 108e9, 100e9],
        net_income=[100e9, 95e9, 90e9, 85e9, 80e9],
        tax_rate=[0.15, 0.15, 0.15, 0.15, 0.15],
    )


def _high_quality_balance_sheet() -> pd.DataFrame:
    return _balance_sheet([500e9, 480e9, 460e9, 440e9, 420e9])


def _high_quality_cashflow() -> pd.DataFrame:
    return _cashflow([110e9, 100e9, 95e9, 90e9, 85e9])


# ---------------------------------------------------------------------------
# Quality Score
# ---------------------------------------------------------------------------


class TestQualityScore:
    def test_high_quality_company(self) -> None:
        """A company with strong fundamentals should score > 60."""
        score = quality_score(
            _high_quality_info(),
            _high_quality_financials(),
            _high_quality_balance_sheet(),
            _high_quality_cashflow(),
        )
        assert score > 60

    def test_score_bounded_0_to_100(self) -> None:
        score = quality_score(
            _high_quality_info(),
            _high_quality_financials(),
            _high_quality_balance_sheet(),
            _high_quality_cashflow(),
        )
        assert 0 <= score <= 100

    def test_empty_info_returns_zero(self) -> None:
        """Missing data should not crash — returns 0."""
        score = quality_score({}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
        assert score == 0

    def test_high_roic_increases_score(self) -> None:
        """Higher ROIC (via higher operating income) should increase the score."""
        low_roic_fin = _financials(
            revenue=[100e9] * 5,
            gross_profit=[40e9] * 5,
            operating_income=[5e9] * 5,  # low operating income → low ROIC
            net_income=[4e9] * 5,
            tax_rate=[0.15] * 5,
        )
        high_roic_fin = _financials(
            revenue=[100e9] * 5,
            gross_profit=[40e9] * 5,
            operating_income=[30e9] * 5,  # high operating income → high ROIC
            net_income=[25e9] * 5,
            tax_rate=[0.15] * 5,
        )
        bs = _balance_sheet([100e9] * 5)
        cf = _high_quality_cashflow()
        info = _high_quality_info()

        score_low = quality_score(info, low_roic_fin, bs, cf)
        score_high = quality_score(info, high_roic_fin, bs, cf)

        assert score_high > score_low


# ---------------------------------------------------------------------------
# GARP Score
# ---------------------------------------------------------------------------


class TestGarpScore:
    def test_attractive_garp(self) -> None:
        """Low PEG + high growth + low forward P/E → high GARP score."""
        info: dict[str, Any] = {
            "trailingPegRatio": 0.8,
            "earningsGrowth": 0.20,
            "revenueGrowth": 0.15,
            "forwardPE": 16.0,
        }
        score = garp_score(info)
        assert score > 70

    def test_expensive_garp(self) -> None:
        """High PEG + low growth + high forward P/E → low GARP score."""
        info: dict[str, Any] = {
            "trailingPegRatio": 3.5,
            "earningsGrowth": 0.02,
            "revenueGrowth": 0.01,
            "forwardPE": 45.0,
        }
        score = garp_score(info)
        assert score < 20

    def test_score_bounded(self) -> None:
        score = garp_score(_high_quality_info())
        assert 0 <= score <= 100

    def test_empty_info(self) -> None:
        assert garp_score({}) == 0

    def test_negative_peg_ignored(self) -> None:
        """Negative PEG (negative earnings growth) should not contribute points."""
        info: dict[str, Any] = {
            "trailingPegRatio": -1.5,
            "earningsGrowth": -0.10,
            "revenueGrowth": -0.05,
            "forwardPE": 40.0,
        }
        assert garp_score(info) < 10


# ---------------------------------------------------------------------------
# Moat Rating
# ---------------------------------------------------------------------------


class TestMoatRating:
    def test_wide_moat(self) -> None:
        """Sustained high ROIC (>20% avg, >12% min) → Wide moat."""
        # ROIC = operating_income * (1 - tax) / invested_capital
        # = 30e9 * 0.85 / 100e9 = 25.5% for each year
        fin = _financials(
            revenue=[100e9] * 5,
            gross_profit=[60e9] * 5,
            operating_income=[30e9] * 5,
            net_income=[25e9] * 5,
            tax_rate=[0.15] * 5,
        )
        bs = _balance_sheet([100e9] * 5)
        assert moat_rating(fin, bs) == "Wide"

    def test_narrow_moat(self) -> None:
        """Moderate ROIC (>12% avg, >6% min) → Narrow moat."""
        # ROIC = 15e9 * 0.85 / 100e9 = 12.75%
        fin = _financials(
            revenue=[100e9] * 5,
            gross_profit=[40e9] * 5,
            operating_income=[15e9] * 5,
            net_income=[12e9] * 5,
            tax_rate=[0.15] * 5,
        )
        bs = _balance_sheet([100e9] * 5)
        assert moat_rating(fin, bs) == "Narrow"

    def test_no_moat(self) -> None:
        """Low ROIC → No moat."""
        # ROIC = 5e9 * 0.85 / 100e9 = 4.25%
        fin = _financials(
            revenue=[100e9] * 5,
            gross_profit=[20e9] * 5,
            operating_income=[5e9] * 5,
            net_income=[3e9] * 5,
            tax_rate=[0.15] * 5,
        )
        bs = _balance_sheet([100e9] * 5)
        assert moat_rating(fin, bs) == "None"

    def test_insufficient_data(self) -> None:
        """Less than 3 years of data → None."""
        assert moat_rating(pd.DataFrame(), pd.DataFrame()) == "None"


# ---------------------------------------------------------------------------
# Thesis Health Check
# ---------------------------------------------------------------------------


class TestThesisHealthCheck:
    def test_strong_thesis(self) -> None:
        """All metrics healthy → status = Strong, no flags."""
        result = thesis_health_check(
            _high_quality_info(),
            _high_quality_financials(),
            _high_quality_balance_sheet(),
            _high_quality_cashflow(),
        )
        assert result["status"] == "Strong"
        assert len(result["flags"]) == 0

    def test_has_required_sections(self) -> None:
        result = thesis_health_check(
            _high_quality_info(),
            _high_quality_financials(),
            _high_quality_balance_sheet(),
            _high_quality_cashflow(),
        )
        assert "revenue" in result
        assert "earnings" in result
        assert "roic" in result
        assert "fcf" in result
        assert "balance" in result
        assert "status" in result
        assert "flags" in result

    def test_high_debt_flagged(self) -> None:
        """Debt/equity > 200% should produce a flag."""
        info = _high_quality_info()
        info["debtToEquity"] = 250.0
        result = thesis_health_check(
            info,
            _high_quality_financials(),
            _high_quality_balance_sheet(),
            _high_quality_cashflow(),
        )
        assert any("debt" in f.lower() for f in result["flags"])

    def test_empty_data_does_not_crash(self) -> None:
        result = thesis_health_check({}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
        assert "status" in result
