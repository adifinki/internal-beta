from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict

from .routes.screener import router as ScreenerRouter
from .routes.tickers import router as TickersRouter


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://localhost:6379"


settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    app.state.redis = redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )

    yield

    await app.state.redis.aclose()


app = FastAPI(
    title="Market Data Service",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(TickersRouter)
app.include_router(ScreenerRouter)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
