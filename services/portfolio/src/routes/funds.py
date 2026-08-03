# GET  /portfolio/funds/catalog          — company/category/track picker options
# POST /portfolio/funds/derive-holdings  — turn 3 fund selections into proxy holdings

import httpx
from fastapi import APIRouter, Body, Depends

from src.dependencies import get_market_data_client
from src.domain.funds import build_catalog_response, compute_derived_holdings, find_track
from src.domain.funds_catalog import FUND_CATALOG
from src.infrastructure.market_data_client import fetch_info_batch, prices_from_info
from src.schemas.funds_schemas import (
    CatalogResponse,
    DeriveHoldingsRequest,
    DeriveHoldingsResponse,
)

router = APIRouter(
    prefix="/portfolio/funds",
    tags=["funds"],
)


@router.get("/catalog")
async def get_catalog() -> CatalogResponse:
    return build_catalog_response(FUND_CATALOG)


@router.post("/derive-holdings")
async def post_derive_holdings(
    request: DeriveHoldingsRequest = Body(...),
    market_data_client: httpx.AsyncClient = Depends(get_market_data_client),
) -> DeriveHoldingsResponse:
    if not request.selections:
        return DeriveHoldingsResponse(holdings=[], unmapped=[], coverage=[])

    # Only fetch prices for tracks actually resolved by the request's selections,
    # not every proxy ticker in the whole catalog - avoids fetching irrelevant
    # prices for funds the user didn't select.
    resolved_tracks = [
        find_track(FUND_CATALOG, s.category, s.company_id, s.track_id) for s in request.selections
    ]
    proxy_tickers = sorted(
        {
            row.proxy_ticker
            for track in resolved_tracks
            if track is not None
            for row in track.rows
            if row.proxy_ticker is not None
        }
    )
    info_by_ticker = await fetch_info_batch(market_data_client, proxy_tickers)
    prices = prices_from_info(proxy_tickers, info_by_ticker)

    holdings, unmapped, coverage = compute_derived_holdings(request.selections, FUND_CATALOG, prices)
    return DeriveHoldingsResponse(holdings=holdings, unmapped=unmapped, coverage=coverage)
