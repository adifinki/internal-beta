"""Tests for savings-fund routes: GET /portfolio/funds/catalog and
POST /portfolio/funds/derive-holdings.

Uses FastAPI TestClient with a patched FUND_CATALOG so tests don't depend
on the real seeded data changing over time.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.schemas.funds_schemas import FundRow, FundTrackEntry


@pytest.fixture
def client() -> TestClient:
    app.state.redis = AsyncMock()
    app.state.market_data_client = AsyncMock()
    return TestClient(app)


def _test_catalog() -> list[FundTrackEntry]:
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
                FundRow(label="Untradeable bonds", pct_of_fund=0.5, proxy_ticker=None),
            ],
        ),
        FundTrackEntry(
            category="keren_hishtalmut",
            company_id="beta",
            company_name="Beta",
            track_id="general",
            track_name="General",
            as_of_date="2025-01-01",
            rows=[
                FundRow(label="Global bonds", pct_of_fund=1.0, proxy_ticker="LQD"),
            ],
        ),
    ]


class TestGetCatalog:
    @patch("src.routes.funds.FUND_CATALOG", new=_test_catalog())
    def test_returns_categories(self, client: TestClient) -> None:
        resp = client.get("/portfolio/funds/catalog")
        assert resp.status_code == 200

        data = resp.json()
        assert data["categories"][0]["category"] == "pension"
        assert data["categories"][0]["companies"][0]["company_id"] == "acme"


class TestDeriveHoldings:
    @patch("src.routes.funds.FUND_CATALOG", new=_test_catalog())
    @patch("src.routes.funds.fetch_info_batch")
    def test_computes_holdings_for_valid_selection(
        self, mock_fetch: AsyncMock, client: TestClient
    ) -> None:
        mock_fetch.return_value = {"SPY": {"currentPrice": 500.0}}

        resp = client.post(
            "/portfolio/funds/derive-holdings",
            json={
                "selections": [
                    {"category": "pension", "company_id": "acme", "track_id": "general", "amount_usd": 1000.0}
                ]
            },
        )
        assert resp.status_code == 200

        data = resp.json()
        assert len(data["holdings"]) == 1
        assert data["holdings"][0]["ticker"] == "SPY"
        assert data["holdings"][0]["shares"] == pytest.approx(1.0)
        assert len(data["unmapped"]) == 1
        assert data["unmapped"][0]["label"] == "Untradeable bonds"
        assert len(data["coverage"]) == 1
        assert data["coverage"][0]["mapped_pct"] == pytest.approx(0.5)
        assert data["coverage"][0]["total_pct"] == pytest.approx(1.0)
        assert data["coverage"][0]["mapped_amount_usd"] == pytest.approx(500.0)

    @patch("src.routes.funds.FUND_CATALOG", new=_test_catalog())
    def test_empty_selections_returns_empty_response(self, client: TestClient) -> None:
        resp = client.post("/portfolio/funds/derive-holdings", json={"selections": []})
        assert resp.status_code == 200
        assert resp.json() == {"holdings": [], "unmapped": [], "coverage": []}

    @patch("src.routes.funds.FUND_CATALOG", new=_test_catalog())
    @patch("src.routes.funds.fetch_info_batch")
    def test_only_fetches_prices_for_relevant_proxy_tickers(
        self, mock_fetch: AsyncMock, client: TestClient
    ) -> None:
        """The catalog has two tracks with different proxy tickers (SPY, LQD).
        Selecting only the "acme" track should fetch only SPY, not LQD."""
        mock_fetch.return_value = {"SPY": {"currentPrice": 500.0}}

        resp = client.post(
            "/portfolio/funds/derive-holdings",
            json={
                "selections": [
                    {"category": "pension", "company_id": "acme", "track_id": "general", "amount_usd": 1000.0}
                ]
            },
        )
        assert resp.status_code == 200

        called_tickers = mock_fetch.call_args.args[1]
        assert called_tickers == ["SPY"]

    @patch("src.routes.funds.FUND_CATALOG", new=_test_catalog())
    @patch("src.routes.funds.fetch_info_batch")
    def test_zero_amount_returns_422(self, mock_fetch: AsyncMock, client: TestClient) -> None:
        resp = client.post(
            "/portfolio/funds/derive-holdings",
            json={
                "selections": [
                    {"category": "pension", "company_id": "acme", "track_id": "general", "amount_usd": 0}
                ]
            },
        )
        assert resp.status_code == 422
        mock_fetch.assert_not_called()

    @patch("src.routes.funds.FUND_CATALOG", new=_test_catalog())
    @patch("src.routes.funds.fetch_info_batch")
    def test_negative_amount_returns_422(self, mock_fetch: AsyncMock, client: TestClient) -> None:
        resp = client.post(
            "/portfolio/funds/derive-holdings",
            json={
                "selections": [
                    {"category": "pension", "company_id": "acme", "track_id": "general", "amount_usd": -100.0}
                ]
            },
        )
        assert resp.status_code == 422
        mock_fetch.assert_not_called()

    @patch("src.routes.funds.FUND_CATALOG", new=_test_catalog())
    @patch("src.routes.funds.fetch_info_batch")
    def test_infinite_amount_returns_422(self, mock_fetch: AsyncMock, client: TestClient) -> None:
        # httpx's own client-side JSON encoder rejects float("inf") before the
        # request is even sent, so build the body manually with the raw
        # "Infinity" token - Python's json.loads (used server-side) accepts it,
        # which is exactly the case allow_inf_nan=False needs to reject at the
        # pydantic layer instead of it silently reaching the frontend.
        body = (
            '{"selections": [{"category": "pension", "company_id": "acme", '
            '"track_id": "general", "amount_usd": Infinity}]}'
        )
        resp = client.post(
            "/portfolio/funds/derive-holdings",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422
        mock_fetch.assert_not_called()

    @patch("src.routes.funds.FUND_CATALOG", new=_test_catalog())
    @patch("src.routes.funds.fetch_info_batch")
    def test_too_many_selections_returns_422(self, mock_fetch: AsyncMock, client: TestClient) -> None:
        selection = {"category": "pension", "company_id": "acme", "track_id": "general", "amount_usd": 100.0}
        resp = client.post(
            "/portfolio/funds/derive-holdings",
            json={"selections": [selection] * 17},
        )
        assert resp.status_code == 422
        mock_fetch.assert_not_called()

    @patch("src.routes.funds.FUND_CATALOG", new=_test_catalog())
    def test_invalid_category_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/portfolio/funds/derive-holdings",
            json={
                "selections": [
                    {
                        "category": "not_a_real_category",
                        "company_id": "acme",
                        "track_id": "general",
                        "amount_usd": 100.0,
                    }
                ]
            },
        )
        assert resp.status_code == 422
