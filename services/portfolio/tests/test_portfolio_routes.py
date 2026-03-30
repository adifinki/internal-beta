"""Tests for portfolio routes: GET /correlation.

Uses FastAPI TestClient with mocked market-data-client and domain functions.
Verifies HTTP layer: status codes, response shapes, correct delegation.
"""

from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client() -> TestClient:
    """Provide a synchronous test client with mocked app.state."""
    app.state.redis = AsyncMock()
    app.state.market_data_client = AsyncMock()
    return TestClient(app)


def _sample_returns_df() -> pd.DataFrame:
    """Deterministic 5-day, 2-ticker returns DataFrame."""
    return pd.DataFrame(
        {
            "AAPL": [0.01, -0.02, 0.03, 0.01, -0.01],
            "MSFT": [0.02, 0.01, -0.01, 0.03, 0.00],
        },
        index=pd.to_datetime(
            ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06"]
        ),
    )


class TestGetCorrelation:
    @patch("src.routes.portfolio.fetch_returns")
    def test_returns_correlation_matrix(
        self, mock_fetch: AsyncMock, client: TestClient
    ) -> None:
        mock_fetch.return_value = _sample_returns_df()

        resp = client.get(
            "/portfolio/correlation",
            params={"tickers": ["AAPL", "MSFT"], "period": "5y"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "matrix" in data
        assert "tickers" in data

    @patch("src.routes.portfolio.fetch_returns")
    def test_matrix_has_correct_tickers(
        self, mock_fetch: AsyncMock, client: TestClient
    ) -> None:
        mock_fetch.return_value = _sample_returns_df()

        resp = client.get(
            "/portfolio/correlation",
            params={"tickers": ["AAPL", "MSFT"], "period": "5y"},
        )
        data = resp.json()

        assert set(data["tickers"]) == {"AAPL", "MSFT"}
        assert set(data["matrix"].keys()) == {"AAPL", "MSFT"}

    @patch("src.routes.portfolio.fetch_returns")
    def test_diagonal_is_one(self, mock_fetch: AsyncMock, client: TestClient) -> None:
        """Diagonal of correlation matrix (self-correlation) must be 1.0."""
        mock_fetch.return_value = _sample_returns_df()

        resp = client.get(
            "/portfolio/correlation",
            params={"tickers": ["AAPL", "MSFT"], "period": "5y"},
        )
        data = resp.json()

        assert data["matrix"]["AAPL"]["AAPL"] == pytest.approx(1.0)
        assert data["matrix"]["MSFT"]["MSFT"] == pytest.approx(1.0)

    @patch("src.routes.portfolio.fetch_returns")
    def test_matrix_is_symmetric(
        self, mock_fetch: AsyncMock, client: TestClient
    ) -> None:
        """corr(A,B) == corr(B,A)."""
        mock_fetch.return_value = _sample_returns_df()

        resp = client.get(
            "/portfolio/correlation",
            params={"tickers": ["AAPL", "MSFT"], "period": "5y"},
        )
        data = resp.json()

        assert data["matrix"]["AAPL"]["MSFT"] == pytest.approx(
            data["matrix"]["MSFT"]["AAPL"]
        )

    @patch("src.routes.portfolio.fetch_returns")
    def test_values_bounded(self, mock_fetch: AsyncMock, client: TestClient) -> None:
        """All correlation values must be in [-1, 1]."""
        mock_fetch.return_value = _sample_returns_df()

        resp = client.get(
            "/portfolio/correlation",
            params={"tickers": ["AAPL", "MSFT"], "period": "5y"},
        )
        data = resp.json()

        for row_ticker in data["tickers"]:
            for col_ticker in data["tickers"]:
                val = data["matrix"][row_ticker][col_ticker]
                assert -1.0 <= val <= 1.0

    def test_missing_tickers_returns_422(self, client: TestClient) -> None:
        resp = client.get("/portfolio/correlation")
        assert resp.status_code == 422

    @patch("src.routes.portfolio.fetch_returns")
    def test_custom_period_passed_through(
        self, mock_fetch: AsyncMock, client: TestClient
    ) -> None:
        """Period parameter should be forwarded to fetch_returns."""
        mock_fetch.return_value = _sample_returns_df()

        client.get(
            "/portfolio/correlation",
            params={"tickers": ["AAPL"], "period": "1y"},
        )

        call_kwargs = mock_fetch.call_args
        assert call_kwargs.kwargs["period"] == "1y" or call_kwargs.args[2] == "1y"


class TestHealthCheck:
    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
