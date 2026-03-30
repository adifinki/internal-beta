import httpx
from fastapi import Request
from redis.asyncio import Redis


async def get_market_data_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.market_data_client  # type: ignore[no-any-return]


async def get_portfolio_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.portfolio_client  # type: ignore[no-any-return]


async def get_redis_client(request: Request) -> Redis:
    return request.app.state.redis  # type: ignore[no-any-return]
