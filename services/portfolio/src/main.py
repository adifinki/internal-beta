from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as redis
from fastapi import FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict

from .routes.portfolio import router as PortfolioRouter


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://localhost:6379"
    market_data_url: str = "http://localhost:8001"


settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    app.state.redis = redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )

    # AsyncClient — non-blocking, required inside an async service.
    # A single shared client reuses the underlying connection pool across
    # all requests instead of opening a new TCP connection each time.
    async with httpx.AsyncClient(base_url=settings.market_data_url) as client:
        app.state.market_data_client = client
        yield

    await app.state.redis.aclose()


app = FastAPI(title="portfolio", version="0.1.0", lifespan=lifespan)

app.include_router(PortfolioRouter)


@app.get("/health")
async def get_health_check() -> dict[str, str]:
    return {"status": "ok"}
