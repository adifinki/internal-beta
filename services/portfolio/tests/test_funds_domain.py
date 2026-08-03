"""Tests for savings-fund derivation: catalog lookup, catalog->API shape, and
amount -> proxy-ticker shares math."""

import pytest

from src.domain.funds import build_catalog_response, compute_derived_holdings, find_track
from src.schemas.funds_schemas import FundRow, FundSelection, FundTrackEntry


def _sample_catalog() -> list[FundTrackEntry]:
    return [
        FundTrackEntry(
            category="pension",
            company_id="acme",
            company_name="Acme",
            track_id="general",
            track_name="General",
            as_of_date="2025-01-01",
            rows=[
                FundRow(label="US equities", pct_of_fund=0.5, proxy_ticker="SPY"),
                FundRow(label="Bonds", pct_of_fund=0.3, proxy_ticker="LQD"),
                FundRow(label="Untradeable local bonds", pct_of_fund=0.2, proxy_ticker=None),
            ],
        ),
    ]


class TestFindTrack:
    def test_finds_existing_track(self) -> None:
        catalog = _sample_catalog()
        track = find_track(catalog, "pension", "acme", "general")
        assert track is not None
        assert track.track_name == "General"

    def test_returns_none_for_unknown_track(self) -> None:
        catalog = _sample_catalog()
        assert find_track(catalog, "pension", "acme", "nonexistent") is None

    def test_returns_none_for_unknown_category(self) -> None:
        catalog = _sample_catalog()
        assert find_track(catalog, "keren_hishtalmut", "acme", "general") is None


class TestBuildCatalogResponse:
    def test_groups_by_category_then_company(self) -> None:
        catalog = _sample_catalog()
        response = build_catalog_response(catalog)

        assert len(response.categories) == 1
        assert response.categories[0].category == "pension"
        assert len(response.categories[0].companies) == 1
        assert response.categories[0].companies[0].company_id == "acme"
        assert len(response.categories[0].companies[0].tracks) == 1
        assert response.categories[0].companies[0].tracks[0].track_id == "general"

    def test_two_tracks_same_company_grouped_together(self) -> None:
        catalog = _sample_catalog()
        catalog.append(
            FundTrackEntry(
                category="pension",
                company_id="acme",
                company_name="Acme",
                track_id="sp500",
                track_name="S&P 500 Track",
                as_of_date="2025-01-01",
                rows=[FundRow(label="US equities", pct_of_fund=1.0, proxy_ticker="SPY")],
            )
        )
        response = build_catalog_response(catalog)

        assert len(response.categories) == 1
        assert len(response.categories[0].companies) == 1
        assert len(response.categories[0].companies[0].tracks) == 2


class TestComputeDerivedHoldings:
    def test_computes_shares_from_amount_and_price(self) -> None:
        catalog = _sample_catalog()
        selections = [FundSelection(category="pension", company_id="acme", track_id="general", amount_usd=1000.0)]
        prices = {"SPY": 500.0, "LQD": 100.0}

        holdings, unmapped = compute_derived_holdings(selections, catalog, prices)

        spy = next(h for h in holdings if h.ticker == "SPY")
        assert spy.shares == pytest.approx(1000.0 * 0.5 / 500.0)  # = 1.0
        lqd = next(h for h in holdings if h.ticker == "LQD")
        assert lqd.shares == pytest.approx(1000.0 * 0.3 / 100.0)  # = 3.0

    def test_unmapped_rows_never_become_holdings(self) -> None:
        catalog = _sample_catalog()
        selections = [FundSelection(category="pension", company_id="acme", track_id="general", amount_usd=1000.0)]
        prices = {"SPY": 500.0, "LQD": 100.0}

        holdings, unmapped = compute_derived_holdings(selections, catalog, prices)

        assert all(h.ticker not in (None, "") for h in holdings)
        assert len(unmapped) == 1
        assert unmapped[0].label == "Untradeable local bonds"
        assert unmapped[0].pct_of_fund == pytest.approx(0.2)

    def test_holding_source_is_tagged(self) -> None:
        catalog = _sample_catalog()
        selections = [FundSelection(category="pension", company_id="acme", track_id="general", amount_usd=1000.0)]
        prices = {"SPY": 500.0, "LQD": 100.0}

        holdings, _ = compute_derived_holdings(selections, catalog, prices)

        spy = next(h for h in holdings if h.ticker == "SPY")
        assert spy.source.category == "pension"
        assert spy.source.company_name == "Acme"
        assert spy.source.track_name == "General"

    def test_missing_price_skips_that_row(self) -> None:
        """If a proxy ticker's price couldn't be fetched, that row is silently
        dropped from holdings — it is NOT added to unmapped (unmapped means
        'no real proxy exists', not 'price fetch failed')."""
        catalog = _sample_catalog()
        selections = [FundSelection(category="pension", company_id="acme", track_id="general", amount_usd=1000.0)]
        prices = {"SPY": 500.0}  # LQD price missing

        holdings, unmapped = compute_derived_holdings(selections, catalog, prices)

        tickers = [h.ticker for h in holdings]
        assert "LQD" not in tickers
        assert "SPY" in tickers
        assert len(unmapped) == 1  # still just the genuinely-unmapped row

    def test_unknown_selection_produces_no_holdings(self) -> None:
        catalog = _sample_catalog()
        selections = [FundSelection(category="pension", company_id="acme", track_id="nonexistent", amount_usd=1000.0)]

        holdings, unmapped = compute_derived_holdings(selections, catalog, {"SPY": 500.0})

        assert holdings == []
        assert unmapped == []

    def test_multiple_selections_are_independent(self) -> None:
        catalog = _sample_catalog()
        catalog.append(
            FundTrackEntry(
                category="keren_hishtalmut",
                company_id="beta",
                company_name="Beta",
                track_id="general",
                track_name="General",
                as_of_date="2025-01-01",
                rows=[FundRow(label="US equities", pct_of_fund=1.0, proxy_ticker="SPY")],
            )
        )
        selections = [
            FundSelection(category="pension", company_id="acme", track_id="general", amount_usd=1000.0),
            FundSelection(category="keren_hishtalmut", company_id="beta", track_id="general", amount_usd=500.0),
        ]
        prices = {"SPY": 500.0, "LQD": 100.0}

        holdings, _ = compute_derived_holdings(selections, catalog, prices)

        spy_holdings = [h for h in holdings if h.ticker == "SPY"]
        assert len(spy_holdings) == 2  # one per selection, NOT pre-summed — the frontend sums by ticker
        assert {h.source.category for h in spy_holdings} == {"pension", "keren_hishtalmut"}
