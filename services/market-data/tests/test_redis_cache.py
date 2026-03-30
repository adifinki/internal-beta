"""Tests for market-data infrastructure: redis_cache.

Tests cache key generation (pure functions, no Redis needed)
and cache get/set behaviour (mocked Redis).
"""

from unittest.mock import AsyncMock

import pytest

from src.infrastructure.redis_cache import (
    DEFAULT_TTL,
    cache_get,
    cache_set,
    get_info_cache_key,
    get_prices_cache_key,
)
from src.models import Period

# ---------------------------------------------------------------------------
# Cache key generation — pure functions, deterministic
# ---------------------------------------------------------------------------


class TestCacheKeys:
    def test_prices_key_format(self) -> None:
        assert get_prices_cache_key("AAPL", Period.MAX) == "prices:AAPL:5y"

    def test_prices_key_different_periods(self) -> None:
        assert get_prices_cache_key("AAPL", Period.DAY) == "prices:AAPL:1d"
        assert get_prices_cache_key("AAPL", Period.WEEK) == "prices:AAPL:5d"
        assert get_prices_cache_key("AAPL", Period.MONTH) == "prices:AAPL:1mo"
        assert get_prices_cache_key("AAPL", Period.YEAR) == "prices:AAPL:1y"

    def test_prices_key_different_tickers(self) -> None:
        k1 = get_prices_cache_key("AAPL", Period.MAX)
        k2 = get_prices_cache_key("MSFT", Period.MAX)
        assert k1 != k2

    def test_info_key_format(self) -> None:
        assert get_info_cache_key("GOOGL") == "info:GOOGL"


# ---------------------------------------------------------------------------
# Cache get/set — mocked Redis
# ---------------------------------------------------------------------------


class TestCacheOperations:
    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        return AsyncMock()

    async def test_cache_get_returns_value(self, mock_redis: AsyncMock) -> None:
        mock_redis.get.return_value = '{"data": 1}'
        result = await cache_get(mock_redis, "some-key")
        assert result == '{"data": 1}'
        mock_redis.get.assert_awaited_once_with("some-key")

    async def test_cache_get_returns_none_on_miss(self, mock_redis: AsyncMock) -> None:
        mock_redis.get.return_value = None
        result = await cache_get(mock_redis, "missing-key")
        assert result is None

    async def test_cache_set_uses_default_ttl(self, mock_redis: AsyncMock) -> None:
        await cache_set(mock_redis, "key", "value")
        mock_redis.set.assert_awaited_once_with("key", "value", ex=DEFAULT_TTL)

    async def test_cache_set_custom_ttl(self, mock_redis: AsyncMock) -> None:
        await cache_set(mock_redis, "key", "value", ttl=3600)
        mock_redis.set.assert_awaited_once_with("key", "value", ex=3600)

    def test_default_ttl_is_24_hours(self) -> None:
        assert DEFAULT_TTL == 86400
