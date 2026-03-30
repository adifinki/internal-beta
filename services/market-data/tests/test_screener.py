"""Tests for market-data domain: screener scoring.

All expected values are hand-computed from the scoring thresholds.
"""

import pytest

from src.domain.screener import cheap_quality_score, screen_universe


class TestCheapQualityScore:
    def test_high_quality_low_valuation(self) -> None:
        """Quality 80 + low P/E + low PEG → high score."""
        quality = {"quality_score": 80}
        info = {"forwardPE": 12.0, "trailingPegRatio": 0.7}
        score = cheap_quality_score(quality, info)
        # PE score: <15 → 100. PEG score: 0.5-1.0 → 85.
        # Valuation = 0.6×100 + 0.4×85 = 94.
        # Score = 80 × 94 / 100 = 75.2
        assert score == pytest.approx(75.2)

    def test_high_quality_high_valuation(self) -> None:
        """Quality 80 + high P/E + high PEG → low score."""
        quality = {"quality_score": 80}
        info = {"forwardPE": 45.0, "trailingPegRatio": 3.5}
        score = cheap_quality_score(quality, info)
        # PE score: >40 → 10. PEG score: >3.0 → 10.
        # Valuation = 0.6×10 + 0.4×10 = 10.
        # Score = 80 × 10 / 100 = 8.0
        assert score == pytest.approx(8.0)

    def test_zero_quality_returns_zero(self) -> None:
        quality = {"quality_score": 0}
        info = {"forwardPE": 10.0, "trailingPegRatio": 0.5}
        assert cheap_quality_score(quality, info) == 0.0

    def test_missing_quality_returns_zero(self) -> None:
        assert cheap_quality_score({}, {"forwardPE": 10.0}) == 0.0

    def test_missing_valuation_uses_defaults(self) -> None:
        """Missing P/E and PEG use neutral default scores (50 each)."""
        quality = {"quality_score": 80}
        score = cheap_quality_score(quality, {})
        # Valuation = 0.6×50 + 0.4×50 = 50.
        # Score = 80 × 50 / 100 = 40.0
        assert score == pytest.approx(40.0)

    def test_cheap_beats_expensive(self) -> None:
        """Same quality, cheaper valuation → higher score."""
        quality = {"quality_score": 70}
        cheap = cheap_quality_score(
            quality, {"forwardPE": 12.0, "trailingPegRatio": 0.8}
        )
        expensive = cheap_quality_score(
            quality, {"forwardPE": 40.0, "trailingPegRatio": 2.5}
        )
        assert cheap > expensive


class TestScreenUniverse:
    def _sample_scored(self) -> list[dict]:
        return [
            {"ticker": "A", "quality_score": 80, "cheap_quality_score": 60.0},
            {"ticker": "B", "quality_score": 40, "cheap_quality_score": 30.0},
            {"ticker": "C", "quality_score": 90, "cheap_quality_score": 75.0},
            {"ticker": "D", "quality_score": 60, "cheap_quality_score": 50.0},
            {"ticker": "E", "quality_score": 30, "cheap_quality_score": 10.0},
        ]

    def test_filters_by_min_quality(self) -> None:
        result = screen_universe(self._sample_scored(), min_quality=50, limit=10)
        tickers = [r["ticker"] for r in result]
        assert "B" not in tickers  # quality 40 < 50
        assert "E" not in tickers  # quality 30 < 50

    def test_sorted_by_cheap_quality_descending(self) -> None:
        result = screen_universe(self._sample_scored(), min_quality=50, limit=10)
        scores = [r["cheap_quality_score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_respects_limit(self) -> None:
        result = screen_universe(self._sample_scored(), min_quality=0, limit=2)
        assert len(result) == 2

    def test_top_result_is_highest_score(self) -> None:
        result = screen_universe(self._sample_scored(), min_quality=50, limit=1)
        assert result[0]["ticker"] == "C"  # highest cheap_quality_score = 75

    def test_empty_input(self) -> None:
        assert screen_universe([], min_quality=50, limit=20) == []
