"""Regression guards over the REAL seeded FUND_CATALOG data (not a fixture).

These catch hand-entered-data mistakes: a typo'd category, a duplicate track,
an empty proxy ticker string, or a fund's rows summing to something nonsensical
(missing row, decimal-point slip, etc).
"""

from src.domain.funds_catalog import FUND_CATALOG

ALLOWED_CATEGORIES = {"pension", "kupat_gemel_lehashkaa", "keren_hishtalmut"}


class TestFundCatalogIntegrity:
    def test_categories_are_within_allowed_set(self) -> None:
        categories = {entry.category for entry in FUND_CATALOG}
        assert categories.issubset(ALLOWED_CATEGORIES)

    def test_no_duplicate_tracks(self) -> None:
        keys = [(entry.category, entry.company_id, entry.track_id) for entry in FUND_CATALOG]
        assert len(keys) == len(set(keys)), "duplicate (category, company_id, track_id) triple found in FUND_CATALOG"

    def test_proxy_tickers_are_nonempty_strings(self) -> None:
        for entry in FUND_CATALOG:
            for row in entry.rows:
                if row.proxy_ticker is not None:
                    assert isinstance(row.proxy_ticker, str)
                    assert row.proxy_ticker.strip() != ""

    def test_each_track_pct_sum_is_in_sane_band(self) -> None:
        for entry in FUND_CATALOG:
            total = sum(row.pct_of_fund for row in entry.rows)
            assert 0.8 <= total <= 1.5, (
                f"{entry.company_name} / {entry.track_name} rows sum to {total:.4f}, "
                "outside the sane 0.8-1.5 band - check for a missing row or decimal slip"
            )
