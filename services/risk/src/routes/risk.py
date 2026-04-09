# POST /risk/analyze-portfolio  — Mode 1: full baseline portfolio analysis
# POST /risk/analyze-candidate  — Mode 2a: before/after for adding a ticker
# POST /risk/sector-impact      — Mode 2b: "what if sector X moves Y%?"

import asyncio
import hashlib
import json
import logging
from typing import Any

import httpx
import numpy as np
import pandas as pd
from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from src.dependencies import get_market_data_client, get_redis_client
from src.domain.drawdown import compute_max_drawdown
from src.domain.hedging import compute_correlation_clusters, compute_portfolio_beta
from src.domain.internal_beta import (
    compute_correlation_to_portfolio,
    compute_internal_beta,
)
from src.domain.mctr import compute_mctr
from src.domain.optimal_allocation import compute_optimal_shares
from src.domain.portfolio_math import (
    annualise_cov,
    portfolio_daily_returns,
    portfolio_value,
    portfolio_weights,
    prices_from_info,
)
from src.domain.recommendations import (
    generate_exit_trim_recommendations,
    generate_rebalance_recommendation,
    generate_recommendations,
)
from src.domain.sharpe import compute_sharpe, sortino_from_daily
from src.domain.stress import compute_stress
from src.domain.var import compute_cvar, compute_var
from src.infrastructure.market_data_client import (
    fetch_info_batch,
    fetch_quality_batch,
    fetch_returns,
)
from src.schemas.risk_schemas import (
    AnalyzeCandidateRequest,
    AnalyzePortfolioRequest,
    BatchBetaRequest,
    RecommendationsRequest,
    SectorImpactRequest,
)

logger = logging.getLogger(__name__)

_CACHE_TTL = 1800  # 30 minutes for analysis results

router = APIRouter(
    prefix="/risk",
    tags=["risk"],
)


def _cache_key(prefix: str, request_body: Any) -> str:
    """Deterministic cache key from request payload."""
    raw = json.dumps(request_body.model_dump(), sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"{prefix}:{digest}"


# ---------------------------------------------------------------------------
# Mode 1: POST /risk/analyze-portfolio
# ---------------------------------------------------------------------------


@router.post("/analyze-portfolio", response_model=None)
async def analyze_portfolio(
    request: AnalyzePortfolioRequest = Body(...),
    md_client: httpx.AsyncClient = Depends(get_market_data_client),
    redis: Redis = Depends(get_redis_client),
) -> dict[str, Any] | JSONResponse:
    # Check cache
    cache_key = _cache_key("portfolio", request)
    cached = await redis.get(cache_key)
    if cached is not None:
        return json.loads(cached)

    tickers = list(dict.fromkeys(h.ticker for h in request.portfolio))
    holdings_dict = {h.ticker: h.shares for h in request.portfolio}

    # Fetch data from market-data-service
    # Stress scenarios need data back to 2020, so fetch a longer window for that
    try:
        (
            returns,
            stress_returns,
            info_by_ticker,
            quality_by_ticker,
        ) = await asyncio.gather(
            fetch_returns(md_client, tickers, request.period),
            fetch_returns(md_client, tickers, "10y"),
            fetch_info_batch(md_client, tickers),
            fetch_quality_batch(md_client, tickers),
        )
    except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
        logger.error("Failed to fetch market data for %s: %s", tickers, e)
        return JSONResponse(
            status_code=502,
            content={
                "detail": f"Market data service unavailable — please retry. ({e})"
            },
        )

    prices = prices_from_info(tickers, info_by_ticker)
    valid = [t for t in tickers if t in prices]

    # Validate that we have at least some valid tickers
    if not valid:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "Could not fetch price data for any tickers"
            },
        )

    weights = portfolio_weights({t: holdings_dict[t] for t in valid}, prices)
    port_val = portfolio_value(holdings_dict, prices)
    daily = portfolio_daily_returns(returns, weights)
    cov = annualise_cov(returns, valid)

    risk = compute_sharpe(returns, weights)
    sortino, sortino_reliable = sortino_from_daily(daily.values)
    var_95 = compute_var(daily, port_val)
    cvar_95 = compute_cvar(daily, port_val)
    drawdown = compute_max_drawdown(daily, port_val)
    mctr = compute_mctr(weights, cov, valid)
    stress = compute_stress(stress_returns, weights, port_val)
    beta = compute_portfolio_beta(weights, info_by_ticker)
    clusters = compute_correlation_clusters(returns, valid)

    # Leave-one-out internal beta for each holding:
    # For stock i, compute portfolio returns WITHOUT stock i, then beta of i vs that.
    # This avoids the self-correlation inflation of MCTR-derived beta.
    internal_betas: dict[str, float] = {}
    for ticker in valid:
        other_tickers = [t for t in valid if t != ticker]
        if not other_tickers:
            internal_betas[ticker] = 1.0
            continue
        other_weights = portfolio_weights(
            {t: holdings_dict[t] for t in other_tickers}, prices
        )
        other_daily = portfolio_daily_returns(returns, other_weights)
        # Convert individual ticker log returns to simple for consistency
        # with portfolio_daily_returns (which now returns simple returns)
        ticker_simple = np.exp(returns[ticker]) - 1
        internal_betas[ticker] = round(
            compute_internal_beta(ticker_simple, other_daily), 4
        )

    # Compute concentration inline (sector, country, HHI) for recommendations
    conc_sectors: dict[str, float] = {}
    conc_countries: dict[str, float] = {}
    for t, w in weights.items():
        info = info_by_ticker.get(t, {})
        sector = info.get("sector") or ""
        if not isinstance(sector, str) or not sector:
            qt = info.get("quoteType", "")
            sector = info.get("category") or (
                "Fixed Income"
                if qt in ("ETF", "MUTUALFUND")
                and "bond" in str(info.get("shortName", "")).lower()
                else "Diversified"
            )
        conc_sectors[sector] = conc_sectors.get(sector, 0.0) + w
        country = info.get("country") or (
            "United States" if info.get("fundFamily") else "Unknown"
        )
        if not isinstance(country, str) or not country:
            country = "Unknown"
        conc_countries[country] = conc_countries.get(country, 0.0) + w

    concentration = {
        "sectors": conc_sectors,
        "countries": conc_countries,
        "hhi": sum(v * v for v in weights.values()),
        "top_holding_pct": max(weights.values()) if weights else 0.0,
    }

    holdings_quality_list = [
        {"ticker": t, **quality_by_ticker.get(t, {})} for t in valid
    ]

    risk_full = {
        **risk,
        "sortino": sortino,
        "sortino_reliable": sortino_reliable,
        "var_95": var_95,
        "cvar_95": cvar_95,
        **drawdown,
    }

    recommendations = generate_recommendations(
        weights=weights,
        risk=risk_full,
        mctr=mctr,
        internal_betas=internal_betas,
        hedging={"portfolio_beta": beta, "correlation_clusters": clusters},
        holdings_quality=holdings_quality_list,
        concentration=concentration,
        stress=stress,
        portfolio_value=port_val,
        age=request.age,
    )

    result = {
        "risk": risk_full,
        "mctr": mctr,
        "internal_betas": internal_betas,
        "hedging": {
            "portfolio_beta": beta,
            "correlation_clusters": clusters,
        },
        "stress": stress,
        "holdings_quality": holdings_quality_list,
        "weights": weights,
        "portfolio_value": port_val,
        "skipped_tickers": [t for t in tickers if t not in valid],
        "recommendations": recommendations,
    }

    # Cache for 30 min
    await redis.set(cache_key, json.dumps(result, default=str), ex=_CACHE_TTL)

    return result


# ---------------------------------------------------------------------------
# Mode 2a: POST /risk/analyze-candidate
# ---------------------------------------------------------------------------


@router.post("/analyze-candidate", response_model=None)
async def analyze_candidate(
    request: AnalyzeCandidateRequest = Body(...),
    md_client: httpx.AsyncClient = Depends(get_market_data_client),
    redis: Redis = Depends(get_redis_client),
) -> dict[str, Any] | JSONResponse:
    # Check cache
    cache_key = _cache_key("candidate", request)
    cached = await redis.get(cache_key)
    if cached is not None:
        return json.loads(cached)

    existing_tickers = list(dict.fromkeys(h.ticker for h in request.portfolio))
    cand_ticker = request.candidate.ticker
    all_tickers = list(dict.fromkeys(existing_tickers + [cand_ticker]))

    holdings_dict = {h.ticker: h.shares for h in request.portfolio}

    # Fetch all data from market-data-service
    # Stress scenarios need data back to 2020, so fetch a longer window for that
    try:
        (
            returns,
            stress_returns,
            info_by_ticker,
            quality_by_ticker,
        ) = await asyncio.gather(
            fetch_returns(md_client, all_tickers, request.period),
            fetch_returns(md_client, all_tickers, "10y"),
            fetch_info_batch(md_client, all_tickers),
            fetch_quality_batch(md_client, all_tickers),
        )
    except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
        logger.error("Failed to fetch market data for %s: %s", all_tickers, e)
        return JSONResponse(
            status_code=502,
            content={
                "detail": f"Market data service unavailable — please retry. ({e})"
            },
        )

    prices = prices_from_info(all_tickers, info_by_ticker)

    # --- BASELINE (current portfolio) ---
    valid_base = [t for t in existing_tickers if t in prices]
    base_holdings = {t: holdings_dict[t] for t in valid_base}
    base_weights = portfolio_weights(base_holdings, prices)
    base_val = portfolio_value(base_holdings, prices)
    base_daily = portfolio_daily_returns(returns, base_weights)
    base_risk = compute_sharpe(returns, base_weights)
    base_sortino, base_sortino_reliable = sortino_from_daily(base_daily.values)
    base_var = compute_var(base_daily, base_val)
    base_cvar = compute_cvar(base_daily, base_val)
    base_dd = compute_max_drawdown(base_daily, base_val)
    base_stress = compute_stress(stress_returns, base_weights, base_val)

    # --- OPTIMAL ALLOCATION (multi-metric composite) ---
    optimal = compute_optimal_shares(
        returns=returns,
        base_holdings=base_holdings,
        prices=prices,
        candidate_ticker=cand_ticker,
        candidate_quality=quality_by_ticker.get(cand_ticker),
    )
    effective_shares = request.candidate.shares_to_add or optimal["optimal_shares"]

    # --- WITH CANDIDATE ---
    cand_holdings = dict(base_holdings)
    cand_holdings[cand_ticker] = cand_holdings.get(cand_ticker, 0) + float(
        effective_shares
    )
    valid_cand = [t for t in cand_holdings if t in prices]
    cand_weights = portfolio_weights({t: cand_holdings[t] for t in valid_cand}, prices)
    cand_val = portfolio_value(cand_holdings, prices)
    cand_daily = portfolio_daily_returns(returns, cand_weights)
    cand_cov = annualise_cov(returns, valid_cand)

    cand_risk = compute_sharpe(returns, cand_weights)
    cand_sortino, cand_sortino_reliable = sortino_from_daily(cand_daily.values)
    cand_var = compute_var(cand_daily, cand_val)
    cand_cvar = compute_cvar(cand_daily, cand_val)
    cand_dd = compute_max_drawdown(cand_daily, cand_val)
    cand_stress = compute_stress(stress_returns, cand_weights, cand_val)

    # --- CANDIDATE-SPECIFIC METRICS ---
    # Convert log returns to simple for consistency with portfolio_daily_returns
    cand_returns_simple = (
        np.exp(returns[cand_ticker]) - 1
        if cand_ticker in returns.columns
        else pd.Series(dtype=float)
    )
    int_beta = compute_internal_beta(cand_returns_simple, base_daily)
    corr_to_port = compute_correlation_to_portfolio(cand_returns_simple, base_daily)

    # Correlation to each existing holding — reuse domain function for consistency
    corr_to_each: dict[str, float] = {
        t: compute_correlation_to_portfolio(cand_returns_simple, np.exp(returns[t]) - 1)
        for t in valid_base
        if t != cand_ticker and t in returns.columns
    }

    # MCTR contribution of candidate in the new portfolio
    cand_mctr_all = compute_mctr(cand_weights, cand_cov, valid_cand)
    cand_mctr_contribution = cand_mctr_all.get(cand_ticker, {}).get("mctr", 0.0)

    # --- DELTA ---
    def _delta(base: dict[str, float], cand: dict[str, float]) -> dict[str, float]:
        return {k: cand.get(k, 0) - base.get(k, 0) for k in base}

    base_full = {
        **base_risk,
        "sortino": base_sortino,
        "sortino_reliable": base_sortino_reliable,
        "var_95": base_var,
        "cvar_95": base_cvar,
        **base_dd,
    }
    cand_full = {
        **cand_risk,
        "sortino": cand_sortino,
        "sortino_reliable": cand_sortino_reliable,
        "var_95": cand_var,
        "cvar_95": cand_cvar,
        **cand_dd,
    }

    result = {
        "risk": {
            "baseline": base_full,
            "with_candidate": cand_full,
            "delta": _delta(base_full, cand_full),
        },
        "candidate_metrics": {
            "internal_beta": int_beta,
            "mctr_contribution": cand_mctr_contribution,
            "correlation_to_portfolio": corr_to_port,
            "correlation_to_each": corr_to_each,
        },
        "stress": {
            name: {
                "baseline": base_stress.get(name, {}),
                "with_candidate": cand_stress.get(name, {}),
            }
            for name in ["2020_crash", "2022_shock"]
        },
        "candidate_quality": quality_by_ticker.get(cand_ticker, {}),
        "optimal_allocation": optimal,
        "effective_shares": float(effective_shares),
        "candidate_price": prices.get(cand_ticker, 0),
    }

    # Cache for 30 min
    await redis.set(cache_key, json.dumps(result, default=str), ex=_CACHE_TTL)

    return result


# ---------------------------------------------------------------------------
# POST /risk/recommendations
# ---------------------------------------------------------------------------


@router.post("/recommendations", response_model=None)
async def get_recommendations(
    request: RecommendationsRequest = Body(...),
    md_client: httpx.AsyncClient = Depends(get_market_data_client),
    redis: Redis = Depends(get_redis_client),
) -> dict[str, Any]:
    """Run portfolio analysis and return exit/trim/rebalance recommendations."""
    tickers = list(dict.fromkeys(h.ticker for h in request.portfolio))
    holdings_dict = {h.ticker: h.shares for h in request.portfolio}

    try:
        (
            returns,
            stress_returns,
            info_by_ticker,
            quality_by_ticker,
        ) = await asyncio.gather(
            fetch_returns(md_client, tickers, request.period),
            fetch_returns(md_client, tickers, "10y"),
            fetch_info_batch(md_client, tickers),
            fetch_quality_batch(md_client, tickers),
        )
    except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
        logger.error("Failed to fetch market data for %s: %s", tickers, e)
        return {"recommendations": [], "error": str(e)}

    prices = prices_from_info(tickers, info_by_ticker)
    valid = [t for t in tickers if t in prices]
    weights = portfolio_weights({t: holdings_dict[t] for t in valid}, prices)
    port_val = portfolio_value(holdings_dict, prices)
    daily = portfolio_daily_returns(returns, weights)
    cov = annualise_cov(returns, valid)

    risk = compute_sharpe(returns, weights)
    sortino, sortino_reliable = sortino_from_daily(daily.values)
    var_95 = compute_var(daily, port_val)
    cvar_95 = compute_cvar(daily, port_val)
    drawdown = compute_max_drawdown(daily, port_val)
    mctr = compute_mctr(weights, cov, valid)
    stress = compute_stress(stress_returns, weights, port_val)
    beta = compute_portfolio_beta(weights, info_by_ticker)
    clusters = compute_correlation_clusters(returns, valid)

    internal_betas: dict[str, float] = {}
    for ticker in valid:
        other_tickers = [t for t in valid if t != ticker]
        if not other_tickers:
            internal_betas[ticker] = 1.0
            continue
        other_weights = portfolio_weights(
            {t: holdings_dict[t] for t in other_tickers}, prices
        )
        other_daily = portfolio_daily_returns(returns, other_weights)
        ticker_simple = np.exp(returns[ticker]) - 1
        internal_betas[ticker] = round(
            compute_internal_beta(ticker_simple, other_daily), 4
        )

    holdings_quality_list = [
        {"ticker": t, **quality_by_ticker.get(t, {})} for t in valid
    ]

    risk_full = {
        **risk,
        "sortino": sortino,
        "sortino_reliable": sortino_reliable,
        "var_95": var_95,
        "cvar_95": cvar_95,
        **drawdown,
    }

    hedging_dict: dict[str, Any] = {
        "portfolio_beta": beta,
        "correlation_clusters": clusters,
    }

    portfolio_analysis: dict[str, Any] = {
        "risk": risk_full,
        "mctr": mctr,
        "internal_betas": internal_betas,
        "hedging": hedging_dict,
        "stress": stress,
        "holdings_quality": holdings_quality_list,
        "weights": weights,
        "portfolio_value": port_val,
    }

    recs = generate_exit_trim_recommendations(portfolio_analysis)

    # Optionally fetch optimize result for rebalance recommendation
    if len(valid) >= 2:
        try:
            opt_payload = {
                "portfolio": [
                    {
                        "ticker": h.ticker,
                        "shares": h.shares,
                    }
                    for h in request.portfolio
                    if h.ticker in valid
                ],
                "period": request.period,
            }
            opt_res = await md_client.post(
                "http://portfolio-service:8002/portfolio/optimize",
                json=opt_payload,
                timeout=60.0,
            )
            if opt_res.status_code == 200:
                optimize_result: dict[str, Any] = opt_res.json()
                current_vol = float(risk_full.get("volatility", 0.0))
                rebalance_rec = generate_rebalance_recommendation(
                    optimize_result, current_vol
                )
                if rebalance_rec is not None:
                    recs.append(rebalance_rec)
        except Exception as e:
            logger.warning("Could not fetch optimize result for rebalance rec: %s", e)

    return {
        "recommendations": [rec.__dict__ for rec in recs],
        "portfolio_analysis": portfolio_analysis,
    }


# ---------------------------------------------------------------------------
# Mode 2b: POST /risk/sector-impact
# ---------------------------------------------------------------------------

SECTOR_ETF_MAP: dict[str, str] = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Energy": "XLE",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Industrials": "XLI",
    "Utilities": "XLU",
    "Communication Services": "XLC",
    "Real Estate": "XLRE",
    "Materials": "XLB",
    # Macro factors
    "Interest Rates": "TLT",  # 20+ Year Treasury — rises when rates fall
    "US Dollar": "UUP",  # Dollar index bull fund
    "Gold": "GLD",
}


@router.post("/sector-impact")
async def sector_impact(
    request: SectorImpactRequest = Body(...),
    md_client: httpx.AsyncClient = Depends(get_market_data_client),
) -> dict[str, Any]:
    tickers = list(dict.fromkeys(h.ticker for h in request.portfolio))
    holdings_dict = {h.ticker: h.shares for h in request.portfolio}

    sector_etf = SECTOR_ETF_MAP.get(request.sector)
    all_tickers = tickers + ([sector_etf] if sector_etf else [])

    returns, info_by_ticker = await asyncio.gather(
        fetch_returns(md_client, all_tickers, request.period),
        fetch_info_batch(md_client, tickers),
    )

    prices = prices_from_info(tickers, info_by_ticker)
    valid = [t for t in tickers if t in prices]
    weights = portfolio_weights({t: holdings_dict[t] for t in valid}, prices)
    port_val = portfolio_value(holdings_dict, prices)
    port_daily = portfolio_daily_returns(returns, weights)

    # Portfolio beta to sector ETF
    beta_to_sector = 0.0
    if sector_etf and sector_etf in returns.columns:
        sector_simple = np.exp(returns[sector_etf]) - 1
        beta_to_sector = compute_internal_beta(port_daily, sector_simple)

    # Sector weight in portfolio
    sector_weight = sum(
        weights.get(t, 0)
        for t in valid
        if info_by_ticker.get(t, {}).get("sector") == request.sector
    )

    # Portfolio-level impact uses portfolio beta to the sector ETF directly.
    # This captures ALL cross-sector correlations (e.g. GOOG classified as
    # Communication Services but moving with tech).  Per-holding breakdown
    # below is for display only — it shows which holdings drive the exposure.
    projected_impact = beta_to_sector * request.scenario_move
    dollar_impact = projected_impact * port_val

    # Per-holding breakdown
    affected: list[dict[str, Any]] = []
    unaffected: list[dict[str, Any]] = []
    for t in valid:
        info = info_by_ticker.get(t, {})
        w = weights.get(t, 0)
        if info.get("sector") == request.sector:
            # Individual beta to sector ETF
            t_beta = 0.0
            if sector_etf and sector_etf in returns.columns and t in returns.columns:
                t_simple = np.exp(returns[t]) - 1
                etf_simple = np.exp(returns[sector_etf]) - 1
                t_beta = compute_internal_beta(t_simple, etf_simple)
            t_loss = t_beta * request.scenario_move * w
            affected.append(
                {
                    "ticker": t,
                    "sector": request.sector,
                    "weight": w,
                    "beta_to_sector_etf": t_beta,
                    "projected_loss": t_loss,
                    "projected_loss_dollars": t_loss * port_val,
                }
            )
        else:
            corr = 0.0
            if sector_etf and sector_etf in returns.columns and t in returns.columns:
                t_s = np.exp(returns[t]) - 1
                etf_s = np.exp(returns[sector_etf]) - 1
                corr = compute_correlation_to_portfolio(t_s, etf_s)
            unaffected.append(
                {
                    "ticker": t,
                    "sector": info.get("sector", "Unknown"),
                    "weight": w,
                    "correlation_to_sector": corr,
                }
            )

    return {
        "sector": request.sector,
        "sector_etf": sector_etf,
        "scenario_move": request.scenario_move,
        "portfolio_exposure": {
            "sector_weight": sector_weight,
            "portfolio_beta_to_sector": beta_to_sector,
            "projected_portfolio_impact": projected_impact,
            "projected_dollar_impact": dollar_impact,
        },
        "affected_holdings": affected,
        "unaffected_holdings": unaffected,
    }


# ---------------------------------------------------------------------------
# Batch internal beta: POST /risk/batch-beta
# ---------------------------------------------------------------------------


@router.post("/batch-beta")
async def batch_beta(
    request: BatchBetaRequest = Body(...),
    md_client: httpx.AsyncClient = Depends(get_market_data_client),
) -> dict[str, dict[str, float]]:
    """Compute internal beta + correlation for multiple candidates vs a portfolio.

    Used by the screener to show how each candidate relates to the user's portfolio.
    """
    tickers = list(dict.fromkeys(h.ticker for h in request.portfolio))
    holdings_dict = {h.ticker: h.shares for h in request.portfolio}
    candidates = request.candidates

    # Fetch portfolio returns + info first (these are reliable, already cached)
    portfolio_returns, info_by_ticker = await asyncio.gather(
        fetch_returns(md_client, tickers, request.period),
        fetch_info_batch(md_client, tickers),
    )

    prices = prices_from_info(tickers, info_by_ticker)
    valid = [t for t in tickers if t in prices]
    weights = portfolio_weights({t: holdings_dict[t] for t in valid}, prices)
    port_daily = portfolio_daily_returns(portfolio_returns, weights)

    # Fetch candidate returns in batches of 20 to avoid overwhelming yfinance
    BATCH_SIZE = 20
    all_cand_returns = pd.DataFrame()
    for i in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[i : i + BATCH_SIZE]
        # Include portfolio tickers so the DataFrame aligns on dates
        batch_tickers = list(dict.fromkeys(tickers + batch))
        try:
            batch_returns = await fetch_returns(
                md_client, batch_tickers, request.period
            )
            # Only keep the candidate columns we don't have yet
            new_cols = [
                c
                for c in batch
                if c in batch_returns.columns and c not in all_cand_returns.columns
            ]
            if new_cols:
                if all_cand_returns.empty:
                    all_cand_returns = batch_returns[new_cols]
                else:
                    all_cand_returns = all_cand_returns.join(
                        batch_returns[new_cols], how="outer"
                    )
        except Exception:
            continue

    result: dict[str, dict[str, float]] = {}
    for cand in candidates:
        if cand not in all_cand_returns.columns:
            continue
        cand_simple = np.exp(all_cand_returns[cand]) - 1
        beta = compute_internal_beta(cand_simple, port_daily)
        corr = compute_correlation_to_portfolio(cand_simple, port_daily)
        result[cand] = {
            "internal_beta": round(beta, 4),
            "correlation": round(corr, 4),
        }

    return result
