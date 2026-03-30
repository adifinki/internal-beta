"""Tests for portfolio domain: concentration analysis.

All expected values are hand-computed.
HHI = Σ(w_i²), sector/geo weights = Σ(weight per category).
"""

import pytest

from src.domain.concentration import (
    compute_currency_weights,
    compute_geographic_weights,
    compute_hhi,
    compute_sector_weights,
    compute_top_holding_pct,
)


class TestSectorWeights:
    def test_single_sector(self) -> None:
        weights = {"AAPL": 0.5, "MSFT": 0.5}
        info = {
            "AAPL": {"sector": "Technology"},
            "MSFT": {"sector": "Technology"},
        }
        result = compute_sector_weights(weights, info)
        assert result == {"Technology": pytest.approx(1.0)}

    def test_two_sectors(self) -> None:
        weights = {"AAPL": 0.6, "JNJ": 0.4}
        info = {
            "AAPL": {"sector": "Technology"},
            "JNJ": {"sector": "Healthcare"},
        }
        result = compute_sector_weights(weights, info)
        assert result["Technology"] == pytest.approx(0.6)
        assert result["Healthcare"] == pytest.approx(0.4)

    def test_missing_sector_uses_unknown(self) -> None:
        weights = {"A": 1.0}
        result = compute_sector_weights(weights, {})
        assert "Unknown" in result


class TestGeographicWeights:
    def test_all_us(self) -> None:
        weights = {"A": 0.5, "B": 0.5}
        info = {
            "A": {"country": "United States"},
            "B": {"country": "United States"},
        }
        result = compute_geographic_weights(weights, info)
        assert result == {"United States": pytest.approx(1.0)}

    def test_mixed_countries(self) -> None:
        weights = {"A": 0.7, "B": 0.3}
        info = {
            "A": {"country": "United States"},
            "B": {"country": "Switzerland"},
        }
        result = compute_geographic_weights(weights, info)
        assert result["United States"] == pytest.approx(0.7)
        assert result["Switzerland"] == pytest.approx(0.3)


class TestCurrencyWeights:
    def test_us_maps_to_usd(self) -> None:
        geo = {"United States": 1.0}
        result = compute_currency_weights(geo)
        assert result == {"USD": pytest.approx(1.0)}

    def test_mixed_currencies(self) -> None:
        geo = {"United States": 0.6, "Switzerland": 0.2, "Japan": 0.2}
        result = compute_currency_weights(geo)
        assert result["USD"] == pytest.approx(0.6)
        assert result["CHF"] == pytest.approx(0.2)
        assert result["JPY"] == pytest.approx(0.2)

    def test_unknown_country_maps_to_other(self) -> None:
        geo = {"Narnia": 1.0}
        result = compute_currency_weights(geo)
        assert result == {"OTHER": pytest.approx(1.0)}


class TestHHI:
    def test_single_stock(self) -> None:
        """Single stock: HHI = 1² = 1.0."""
        assert compute_hhi({"A": 1.0}) == pytest.approx(1.0)

    def test_equal_two_stocks(self) -> None:
        """50/50: HHI = 0.5² + 0.5² = 0.5."""
        assert compute_hhi({"A": 0.5, "B": 0.5}) == pytest.approx(0.5)

    def test_equal_four_stocks(self) -> None:
        """25/25/25/25: HHI = 4 × 0.25² = 0.25."""
        w = {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25}
        assert compute_hhi(w) == pytest.approx(0.25)

    def test_concentrated(self) -> None:
        """90/10: HHI = 0.81 + 0.01 = 0.82."""
        assert compute_hhi({"A": 0.9, "B": 0.1}) == pytest.approx(0.82)


class TestTopHoldingPct:
    def test_equal_weights(self) -> None:
        assert compute_top_holding_pct({"A": 0.5, "B": 0.5}) == pytest.approx(0.5)

    def test_one_dominant(self) -> None:
        assert compute_top_holding_pct({"A": 0.8, "B": 0.2}) == pytest.approx(0.8)

    def test_empty(self) -> None:
        assert compute_top_holding_pct({}) == 0.0
