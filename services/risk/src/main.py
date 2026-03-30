from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict
from redis.asyncio import Redis


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    market_data_url: str = "http://localhost:8001"
    portfolio_url: str = "http://localhost:8002"
    redis_url: str = "redis://localhost:6379"


settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    async with (
        httpx.AsyncClient(base_url=settings.market_data_url) as md_client,
        httpx.AsyncClient(base_url=settings.portfolio_url) as pf_client,
    ):
        app.state.market_data_client = md_client
        app.state.portfolio_client = pf_client
        app.state.redis = redis
        yield
    await redis.aclose()


app = FastAPI(title="risk", version="0.1.0", lifespan=lifespan)

from src.routes.risk import router as RiskRouter  # noqa: E402

app.include_router(RiskRouter)


@app.get("/health")
async def get_health_check() -> dict[str, str]:
    return {"status": "ok"}
