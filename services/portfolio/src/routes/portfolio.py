# GET  /portfolio/correlation — correlation matrix for a set of tickers
# GET  /portfolio/profile    — full portfolio profile (fundamentals, concentration, frontier)
# POST /portfolio/optimize   — min-variance rebalancing

import asyncio
from typing import Any

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query

from src.dependencies import get_market_data_client
from src.domain.concentration import (
    compute_currency_weights,
    compute_geographic_weights,
    compute_hhi,
    compute_sector_weights,
    compute_top_holding_pct,
)
from src.domain.frontier import (
    compute_efficient_frontier,
    compute_individual_positions,
    compute_portfolio_frontier_position,
)
from src.domain.fundamentals import (
    compute_weighted_fundamentals,
    compute_weighted_quality,
)
from src.domain.optimization import optimize_min_variance
from src.domain.portfolio import compute_correlation, compute_weights
from src.infrastructure.market_data_client import (
    fetch_info_batch,
    fetch_quality_batch,
    fetch_returns,
    prices_from_info,
)
from src.schemas.portfolio_schemas import (
    CorrelationResponse,
    Holding,
    OptimizeRequest,
    OptimizeResponse,
)

router = APIRouter(
    prefix="/portfolio",
    tags=["portfolio"],
)


@router.get("/correlation")
async def get_portfolio_correlation(
    tickers: list[str] = Query(
        ..., description="Tickers to include in the correlation matrix"
    ),
    period: str = Query("5y", description="Lookback period (e.g. 1y, 5y)"),
    market_data_client: httpx.AsyncClient = Depends(get_market_data_client),
) -> CorrelationResponse:
    returns = await fetch_returns(market_data_client, tickers=tickers, period=period)

    if returns.empty:
        raise HTTPException(
            status_code=400,
            detail=f"Could not fetch price data for any of: {tickers}"
        )

    excluded_tickers = [t for t in tickers if t not in returns.columns]

    corr_df = compute_correlation(returns)

    # Drop any tickers whose correlation row/col is all NaN (insufficient history).
    valid_cols = [c for c in corr_df.columns if not corr_df[c].isna().all()]
    dropped = [c for c in corr_df.columns if c not in valid_cols]
    excluded_tickers.extend(dropped)
    corr_df = corr_df.loc[valid_cols, valid_cols]

    if corr_df.empty or len(corr_df.columns) < 2:
        raise HTTPException(
            status_code=400,
            detail="Not enough tickers with sufficient price history to compute correlation"
        )

    tickers_ordered = list(corr_df.columns)
    matrix: dict[str, dict[str, float]] = {
        row: {col: float(corr_df.loc[row, col]) for col in tickers_ordered}  # pyright: ignore[reportArgumentType]
        for row in tickers_ordered
    }
    return CorrelationResponse(matrix=matrix, tickers=tickers_ordered, excluded_tickers=excluded_tickers)


@router.post("/profile")
async def get_portfolio_profile(
    holdings: list[Holding] = Body(...),
    period: str = Body("5y"),
    market_data_client: httpx.AsyncClient = Depends(get_market_data_client),
) -> dict[str, Any]:
    """Full portfolio profile: fundamentals, quality, concentration, frontier.

    Calls market-data-service endpoints for all data — no direct yfinance access.
    """
    tickers = list(dict.fromkeys(h.ticker for h in holdings))
    holdings_dict = {h.ticker: h.shares for h in holdings}

    returns, info_by_ticker, quality_by_ticker = await asyncio.gather(
        fetch_returns(market_data_client, tickers, period),
        fetch_info_batch(market_data_client, tickers),
        fetch_quality_batch(market_data_client, tickers),
    )

    # Validate that we have returns data
    if returns.empty:
        raise HTTPException(
            status_code=400,
            detail="Could not fetch returns data for any tickers"
        )

    prices = prices_from_info(tickers, info_by_ticker)

    # Compute weights (only for tickers with known prices)
    valid_tickers = [t for t in tickers if t in prices]
    valid_holdings = {t: holdings_dict[t] for t in valid_tickers}
    weights = compute_weights(valid_holdings, prices)

    # Fundamentals
    fundamentals = compute_weighted_fundamentals(weights, info_by_ticker)
    quality = compute_weighted_quality(weights, quality_by_ticker)

    # Concentration
    sectors = compute_sector_weights(weights, info_by_ticker)
    countries = compute_geographic_weights(weights, info_by_ticker)
    currencies = compute_currency_weights(countries)

    # Frontier (uses returns data)
    frontier_returns = returns[valid_tickers] if len(valid_tickers) >= 2 else returns
    frontier_points = (
        compute_efficient_frontier(frontier_returns) if len(valid_tickers) >= 2 else []
    )
    portfolio_position = (
        compute_portfolio_frontier_position(weights, frontier_returns)
        if len(valid_tickers) >= 2
        else None
    )
    individual_positions = compute_individual_positions(frontier_returns)

    return {
        "fundamentals": {**fundamentals, **quality},
        "holdings_quality": [
            {
                "ticker": t,
                **quality_by_ticker.get(t, {}),
            }
            for t in tickers
        ],
        "concentration": {
            "sectors": sectors,
            "countries": countries,
            "currencies": currencies,
            "hhi": compute_hhi(weights),
            "top_holding_pct": compute_top_holding_pct(weights),
        },
        "frontier": {
            "portfolio_position": portfolio_position,
            "min_variance_point": frontier_points[0] if frontier_points else None,
            "frontier_points": frontier_points,
            "individual_holdings": individual_positions,
        },
        "weights": weights,
    }


@router.post("/optimize")
async def post_optimize(
    request: OptimizeRequest = Body(...),
    market_data_client: httpx.AsyncClient = Depends(get_market_data_client),
) -> OptimizeResponse:
    """Min-variance rebalancing: find weights that minimize portfolio risk.

    Uses only the covariance matrix — no return predictions.
    """
    tickers = list(dict.fromkeys(h.ticker for h in request.holdings))
    holdings_dict = {h.ticker: h.shares for h in request.holdings}

    returns, info_by_ticker = await asyncio.gather(
        fetch_returns(market_data_client, tickers, request.period),
        fetch_info_batch(market_data_client, tickers),
    )

    prices = prices_from_info(tickers, info_by_ticker)

    valid_tickers = [t for t in tickers if t in prices]
    valid_holdings = {t: holdings_dict[t] for t in valid_tickers}
    current_weights = compute_weights(valid_holdings, prices)

    result = optimize_min_variance(
        returns=returns,
        current_weights=current_weights,
        holdings=valid_holdings,
        prices=prices,
        risk_free_rate=request.risk_free_rate,
    )

    return OptimizeResponse(
        optimized_weights=result["optimized_weights"],  # type: ignore[arg-type]
        historical_annual_return=result["historical_annual_return"],  # type: ignore[arg-type]
        annual_volatility=result["annual_volatility"],  # type: ignore[arg-type]
        historical_sharpe=result["historical_sharpe"],  # type: ignore[arg-type]
        current_weights=result["current_weights"],  # type: ignore[arg-type]
        rebalancing_trades=result["rebalancing_trades"],  # type: ignore[arg-type]
    )
