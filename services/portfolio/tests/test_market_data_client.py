"""Tests for portfolio infrastructure: market_data_client.

Tests fetch_returns with mocked httpx.AsyncClient.
Verifies correct HTTP call, response parsing, and DataFrame reconstruction.
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pandas as pd
import pytest

from src.infrastructure.market_data_client import fetch_returns


def _mock_response(json_data: dict) -> MagicMock:  # type: ignore[type-arg]
    """Create a mock httpx.Response with .json() returning a plain dict."""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


class TestFetchReturns:
    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        return AsyncMock(spec=httpx.AsyncClient)

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _mock_response(
            {
                "AAPL": {"2024-01-03": 0.01, "2024-01-04": -0.02},
            }
        )

        await fetch_returns(mock_client, tickers=["AAPL"], period="5y")

        mock_client.get.assert_awaited_once_with(
            "/tickers/returns",
            params={"tickers": ["AAPL"], "period": "5y"},
        )

    async def test_returns_dataframe_with_correct_columns(
        self, mock_client: AsyncMock
    ) -> None:
        mock_client.get.return_value = _mock_response(
            {
                "AAPL": {"2024-01-03": 0.01, "2024-01-04": -0.02},
                "MSFT": {"2024-01-03": 0.02, "2024-01-04": 0.01},
            }
        )

        result = await fetch_returns(mock_client, ["AAPL", "MSFT"], "5y")

        assert isinstance(result, pd.DataFrame)
        assert set(result.columns) == {"AAPL", "MSFT"}
        assert result.shape == (2, 2)

    async def test_preserves_exact_return_values(self, mock_client: AsyncMock) -> None:
        """Return values from the API must be preserved exactly."""
        mock_client.get.return_value = _mock_response(
            {
                "AAPL": {"2024-01-03": 0.09531017980432486},
            }
        )

        result = await fetch_returns(mock_client, ["AAPL"], "5y")
        assert result.iloc[0, 0] == pytest.approx(0.09531017980432486, abs=1e-15)

    async def test_raises_on_http_error(self, mock_client: AsyncMock) -> None:
        resp = MagicMock()
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error",
            request=httpx.Request("GET", "http://test"),
            response=httpx.Response(500),
        )
        mock_client.get.return_value = resp

        with pytest.raises(httpx.HTTPStatusError):
            await fetch_returns(mock_client, ["AAPL"], "5y")

    async def test_multiple_tickers_passed_as_list(
        self, mock_client: AsyncMock
    ) -> None:
        mock_client.get.return_value = _mock_response(
            {
                "AAPL": {"2024-01-03": 0.01},
                "MSFT": {"2024-01-03": 0.02},
                "GOOGL": {"2024-01-03": -0.01},
            }
        )

        result = await fetch_returns(mock_client, ["AAPL", "MSFT", "GOOGL"], "1y")
        assert result.shape[1] == 3

        call_kwargs = mock_client.get.call_args
        assert call_kwargs.kwargs["params"]["tickers"] == ["AAPL", "MSFT", "GOOGL"]
        assert call_kwargs.kwargs["params"]["period"] == "1y"
