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

    @patch("src.routes.funds.FUND_CATALOG", new=_test_catalog())
    def test_empty_selections_returns_empty_response(self, client: TestClient) -> None:
        resp = client.post("/portfolio/funds/derive-holdings", json={"selections": []})
        assert resp.status_code == 200
        assert resp.json() == {"holdings": [], "unmapped": []}
