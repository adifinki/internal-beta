import math
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic_settings import BaseSettings, SettingsConfigDict

from .routes.funds import router as FundsRouter
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
app.include_router(FundsRouter)


def _sanitize_non_finite_floats(value: Any) -> Any:
    """Replace NaN/Infinity floats with their string form.

    FastAPI's default validation error body echoes back the rejected input
    (e.g. under errors[].input). If a client sends amount_usd: Infinity, that
    raw float survives jsonable_encoder untouched and then crashes
    JSONResponse's json.dumps(..., allow_nan=False) with an unhandled
    ValueError (500) instead of returning the intended 422. Sanitizing here
    keeps rejected-but-non-finite values out of the response body entirely.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {k: _sanitize_non_finite_floats(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_non_finite_floats(v) for v in value]
    return value


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_sanitize_non_finite_floats(jsonable_encoder(exc.errors())),
    )


@app.get("/health")
async def get_health_check() -> dict[str, str]:
    return {"status": "ok"}
