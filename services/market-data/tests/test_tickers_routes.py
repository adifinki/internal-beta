"""Tests for market-data routes: tickers.py.

Uses FastAPI TestClient with mocked yfinance adapter and Redis.
Verifies HTTP layer behaviour: status codes, response shapes, cache interactions.
"""

from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client() -> TestClient:
    """Provide a synchronous test client with mocked app.state."""
    # Mock Redis in app.state
    app.state.redis = AsyncMock()
    app.state.redis.get = AsyncMock(return_value=None)  # all cache misses
    app.state.redis.set = AsyncMock()
    return TestClient(app)


def _sample_prices_df() -> pd.DataFrame:
    """Deterministic 3-day price DataFrame matching yfinance .history() shape."""
    return pd.DataFrame(
        {
            "Open": [150.0, 152.0, 151.0],
            "High": [153.0, 154.0, 155.0],
            "Low": [149.0, 151.0, 150.0],
            "Close": [152.0, 153.0, 154.0],
            "Volume": [1000000, 1100000, 1050000],
            "Dividends": [0.0, 0.0, 0.0],
            "Stock Splits": [0.0, 0.0, 0.0],
        },
        index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
    )


# ---------------------------------------------------------------------------
# GET /tickers/prices
# ---------------------------------------------------------------------------


class TestGetPrices:
    @patch("src.routes.tickers.fetch_prices_batch")
    def test_returns_prices_for_single_ticker(
        self, mock_fetch: AsyncMock, client: TestClient
    ) -> None:
        mock_fetch.return_value = {"AAPL": _sample_prices_df()}

        resp = client.get(
            "/tickers/prices", params={"tickers": ["AAPL"], "period": "5y"}
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "AAPL" in data
        assert len(data["AAPL"]) == 3
        # Price model fields serialized via FastAPI — check data is present
        first = data["AAPL"][0]
        # FastAPI may serialize with aliases (Title Case) or field names (snake_case)
        has_close = "close" in first or "Close" in first
        assert has_close
        close_val = first.get("close", first.get("Close"))
        assert close_val == 152.0

    @patch("src.routes.tickers.fetch_prices_batch")
    def test_returns_multiple_tickers(
        self, mock_fetch: AsyncMock, client: TestClient
    ) -> None:
        mock_fetch.return_value = {
            "AAPL": _sample_prices_df(),
            "MSFT": _sample_prices_df(),
        }

        resp = client.get(
            "/tickers/prices", params={"tickers": ["AAPL", "MSFT"], "period": "5y"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "AAPL" in data
        assert "MSFT" in data

    def test_missing_tickers_param_returns_422(self, client: TestClient) -> None:
        resp = client.get("/tickers/prices", params={"period": "5y"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /tickers/returns
# ---------------------------------------------------------------------------


class TestGetReturns:
    @patch("src.routes.tickers.fetch_prices_batch")
    def test_returns_log_returns_matrix(
        self, mock_fetch: AsyncMock, client: TestClient
    ) -> None:
        mock_fetch.return_value = {"AAPL": _sample_prices_df()}

        resp = client.get(
            "/tickers/returns", params={"tickers": ["AAPL"], "period": "5y"}
        )
        assert resp.status_code == 200

        data = resp.json()
        # Shape: {ticker: {date_iso: return_value}}
        assert "AAPL" in data
        assert isinstance(data["AAPL"], dict)
        # Should have 2 returns (3 prices - 1)
        assert len(data["AAPL"]) == 2

    @patch("src.routes.tickers.fetch_prices_batch")
    def test_returns_values_are_floats(
        self, mock_fetch: AsyncMock, client: TestClient
    ) -> None:
        mock_fetch.return_value = {"AAPL": _sample_prices_df()}

        resp = client.get(
            "/tickers/returns", params={"tickers": ["AAPL"], "period": "5y"}
        )
        data = resp.json()
        for _date_key, value in data["AAPL"].items():
            assert isinstance(value, float)


# ---------------------------------------------------------------------------
# GET /tickers/{ticker}/info
# ---------------------------------------------------------------------------


class TestGetInfo:
    @patch("src.routes.tickers.fetch_ticker_info")
    def test_returns_ticker_info(
        self, mock_fetch: AsyncMock, client: TestClient
    ) -> None:
        mock_fetch.return_value = {
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "country": "United States",
            "marketCap": 3000000000000,
        }

        resp = client.get("/tickers/AAPL/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sector"] == "Technology"
        assert data["marketCap"] == 3000000000000

    @patch("src.routes.tickers.fetch_ticker_info")
    def test_caches_result(self, mock_fetch: AsyncMock, client: TestClient) -> None:
        mock_fetch.return_value = {"sector": "Technology"}

        client.get("/tickers/AAPL/info")
        # Verify cache_set was called
        app.state.redis.set.assert_awaited()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
