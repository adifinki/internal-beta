"""Tests for portfolio domain: fundamentals aggregation.

All expected values are hand-computed from the weighting formula:
  weighted_metric = Σ(weight_i × metric_i)
"""

import pytest

from src.domain.fundamentals import (
    compute_weighted_fundamentals,
    compute_weighted_quality,
)


class TestWeightedFundamentals:
    def test_equal_weights_averages_values(self) -> None:
        """50/50 portfolio: weighted P/E = average of both P/E values."""
        weights = {"AAPL": 0.5, "MSFT": 0.5}
        info = {
            "AAPL": {
                "trailingPE": 30.0,
                "priceToBook": 10.0,
                "dividendYield": 0.01,
                "revenueGrowth": 0.10,
                "earningsGrowth": 0.15,
                "freeCashflow": 100e9,
                "marketCap": 3000e9,
            },
            "MSFT": {
                "trailingPE": 34.0,
                "priceToBook": 12.0,
                "dividendYield": 0.008,
                "revenueGrowth": 0.14,
                "earningsGrowth": 0.20,
                "freeCashflow": 70e9,
                "marketCap": 2800e9,
            },
        }
        result = compute_weighted_fundamentals(weights, info)

        # P/E: (0.5 × 30 + 0.5 × 34) = 32.0
        assert result["weighted_pe"] == pytest.approx(32.0)
        # P/B: (0.5 × 10 + 0.5 × 12) = 11.0
        assert result["weighted_pb"] == pytest.approx(11.0)

    def test_unequal_weights(self) -> None:
        """75/25 split: weighted P/E = 0.75 × 20 + 0.25 × 40 = 25.0."""
        weights = {"A": 0.75, "B": 0.25}
        info = {
            "A": {"trailingPE": 20.0},
            "B": {"trailingPE": 40.0},
        }
        result = compute_weighted_fundamentals(weights, info)
        assert result["weighted_pe"] == pytest.approx(25.0)

    def test_missing_data_skipped(self) -> None:
        """Ticker with missing P/E should be excluded, not crash."""
        weights = {"A": 0.5, "B": 0.5}
        info = {
            "A": {"trailingPE": 20.0},
            "B": {},  # no P/E data
        }
        result = compute_weighted_fundamentals(weights, info)
        # Only A contributes, so result = 20.0 (renormalized)
        assert result["weighted_pe"] == pytest.approx(20.0)

    def test_fcf_yield_computed_correctly(self) -> None:
        """FCF yield = weighted average of (FCF / marketCap) per ticker."""
        weights = {"A": 0.5, "B": 0.5}
        info = {
            "A": {"freeCashflow": 10e9, "marketCap": 200e9},  # 5%
            "B": {"freeCashflow": 6e9, "marketCap": 200e9},  # 3%
        }
        result = compute_weighted_fundamentals(weights, info)
        # (0.5 × 0.05 + 0.5 × 0.03) = 0.04
        assert result["weighted_fcf_yield"] == pytest.approx(0.04)

    def test_all_missing_returns_none(self) -> None:
        result = compute_weighted_fundamentals({"A": 1.0}, {})
        assert result["weighted_pe"] is None


class TestWeightedQuality:
    def test_equal_weights(self) -> None:
        weights = {"A": 0.5, "B": 0.5}
        quality = {
            "A": {"quality_score": 80, "garp_score": 60},
            "B": {"quality_score": 90, "garp_score": 70},
        }
        result = compute_weighted_quality(weights, quality)
        assert result["portfolio_quality_score"] == pytest.approx(85.0)
        assert result["portfolio_garp_score"] == pytest.approx(65.0)

    def test_weighted_by_position_size(self) -> None:
        """80% in high-quality, 20% in low-quality."""
        weights = {"HIGH": 0.8, "LOW": 0.2}
        quality = {
            "HIGH": {"quality_score": 90, "garp_score": 80},
            "LOW": {"quality_score": 40, "garp_score": 30},
        }
        result = compute_weighted_quality(weights, quality)
        # 0.8 × 90 + 0.2 × 40 = 80
        assert result["portfolio_quality_score"] == pytest.approx(80.0)
        # 0.8 × 80 + 0.2 × 30 = 70
        assert result["portfolio_garp_score"] == pytest.approx(70.0)
