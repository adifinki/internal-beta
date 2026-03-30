"""Compute optimal number of shares to add for a candidate stock.

Grid-searches candidate weight from 1% to 25% of portfolio value.
For each trial, computes ALL portfolio metrics and scores them with a
weighted composite that balances risk reduction, diversification,
quality, and cost efficiency.

Composite score components:
  - Sharpe improvement (25%): does the candidate improve risk-adjusted return?
  - Volatility reduction (25%): does total portfolio risk decrease?
  - Diversification benefit (20%): internal beta + correlation to portfolio
  - Tail risk improvement (15%): CVaR (expected shortfall) gets better?
  - Quality-valuation fit (15%): candidate quality × GARP score
"""

from typing import Any

import numpy as np
import pandas as pd

from src.domain.internal_beta import (
    compute_correlation_to_portfolio as _correlation_domain,
)
from src.domain.internal_beta import (
    compute_internal_beta as _internal_beta_domain,
)
from src.domain.sharpe import sharpe_from_daily as _sharpe_core
from src.domain.var import compute_cvar as _compute_cvar


def compute_optimal_shares(
    returns: pd.DataFrame,
    base_holdings: dict[str, float],
    prices: dict[str, float],
    candidate_ticker: str,
    candidate_quality: dict[str, Any] | None = None,
    risk_free_rate: float = 0.04,
    weight_grid: list[float] | None = None,
) -> dict[str, object]:
    """Find the candidate allocation that maximises a multi-metric composite score.

    Returns:
        {optimal_shares, optimal_weight, optimal_score, composite_breakdown, all_trials}.
    """
    if weight_grid is None:
        # For concentrated portfolios (≤5 holdings), allow higher allocations
        # since 25% may be suboptimal when positions are already 20-30% each.
        n_holdings = len(base_holdings)
        if n_holdings <= 3:
            weight_grid = [0.01, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
        elif n_holdings <= 5:
            weight_grid = [0.01, 0.03, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
        else:
            weight_grid = [0.01, 0.03, 0.05, 0.10, 0.15, 0.20, 0.25]

    empty_result: dict[str, object] = {
        "optimal_shares": 1.0,
        "optimal_weight": 0.01,
        "optimal_score": 0.0,
        "reasoning": "Insufficient data — defaulting to minimum allocation.",
        "composite_breakdown": {},
        "all_trials": [],
    }

    base_value = sum(base_holdings[t] * prices[t] for t in base_holdings if t in prices)
    if base_value <= 0 or candidate_ticker not in returns.columns:
        return empty_result

    cand_price = prices.get(candidate_ticker, 0)
    if cand_price <= 0:
        return empty_result

    base_tickers = [t for t in base_holdings if t in prices and t in returns.columns]
    all_tickers = list(dict.fromkeys(base_tickers + [candidate_ticker]))

    # Compute baseline metrics (before adding candidate)
    base_weights = _compute_weights(base_holdings, prices, base_tickers)
    base_daily = _portfolio_daily(returns, base_weights, base_tickers)
    base_sharpe = _sharpe(base_daily, risk_free_rate)
    base_vol = _annual_vol(base_daily)
    base_cvar = _compute_cvar(base_daily, base_value)

    # Quality score of the candidate (0-100)
    cand_quality = 50.0  # neutral default
    cand_garp = 50.0
    if candidate_quality:
        cand_quality = float(candidate_quality.get("quality_score", 50) or 50)
        cand_garp = float(candidate_quality.get("garp_score", 50) or 50)

    trials: list[dict[str, object]] = []
    best_score = -float("inf")
    best_weight = weight_grid[0]
    best_shares = 1.0
    best_breakdown: dict[str, float] = {}
    best_reasoning = ""

    for target_w in weight_grid:
        cand_value = base_value * target_w / (1.0 - target_w)
        cand_shares = cand_value / cand_price

        # Build combined portfolio
        combined = dict(base_holdings)
        combined[candidate_ticker] = combined.get(candidate_ticker, 0) + cand_shares
        combined_tickers = [
            t for t in all_tickers if t in combined and t in returns.columns
        ]

        weights = _compute_weights(combined, prices, combined_tickers)
        if not weights:
            continue

        daily = _portfolio_daily(returns, weights, combined_tickers)

        # --- Compute all metrics for this trial ---

        # 1. Sharpe improvement
        trial_sharpe = _sharpe(daily, risk_free_rate)
        sharpe_delta = trial_sharpe - base_sharpe
        # Normalise: +0.1 sharpe improvement = score of 1.0
        sharpe_score = min(max(sharpe_delta / 0.1, -1.0), 2.0)

        # 2. Volatility reduction
        trial_vol = _annual_vol(daily)
        vol_delta = base_vol - trial_vol  # positive = improvement
        # Normalise: 1% vol reduction = score of 1.0
        vol_score = min(max(vol_delta / 0.01, -1.0), 2.0)

        # 3. Diversification (internal beta + correlation)
        cand_returns = np.exp(returns[candidate_ticker]) - 1  # log → simple
        int_beta = _internal_beta_domain(cand_returns, base_daily)
        corr = _correlation_domain(cand_returns, base_daily)
        # Lower beta and correlation = better diversification
        # beta=0 → score=1.0, beta=1 → score=0, beta=-0.5 → score=1.5
        beta_score = 1.0 - int_beta
        corr_score = 1.0 - corr
        diversification_score = 0.6 * beta_score + 0.4 * corr_score

        # 4. Tail risk (CVaR improvement)
        trial_cvar = _compute_cvar(daily, base_value + cand_value)
        cvar_delta = trial_cvar - base_cvar  # less negative = improvement
        # Normalise: 1% CVaR improvement relative to portfolio value = score of 1.0
        cvar_score = (
            min(max(cvar_delta / (0.01 * base_value), -1.0), 2.0)
            if base_value > 0
            else 0.0
        )

        # 5. Quality-valuation fit
        # Normalise quality and GARP from 0-100 to 0-1, then combine
        quality_fit = (cand_quality / 100.0) * 0.6 + (cand_garp / 100.0) * 0.4

        # --- Weighted composite ---
        breakdown = {
            "sharpe_improvement": round(sharpe_score, 3),
            "volatility_reduction": round(vol_score, 3),
            "diversification": round(diversification_score, 3),
            "tail_risk": round(cvar_score, 3),
            "quality_fit": round(quality_fit, 3),
        }

        composite = (
            0.25 * sharpe_score
            + 0.25 * vol_score
            + 0.20 * diversification_score
            + 0.15 * cvar_score
            + 0.15 * quality_fit
        )

        trials.append(
            {
                "weight": target_w,
                "shares": round(cand_shares, 2),
                "composite_score": round(composite, 4),
                "sharpe": round(trial_sharpe, 4),
                "volatility": round(trial_vol, 4),
                "internal_beta": round(int_beta, 4),
                "correlation": round(corr, 4),
            }
        )

        if composite > best_score:
            best_score = composite
            best_weight = target_w
            best_shares = round(cand_shares, 2)
            best_breakdown = breakdown
            best_reasoning = _build_reasoning(
                target_w,
                sharpe_delta,
                vol_delta,
                int_beta,
                corr,
                cand_quality,
                cand_garp,
            )

    return {
        "optimal_shares": best_shares,
        "optimal_weight": best_weight,
        "optimal_score": round(best_score, 4),
        "reasoning": best_reasoning,
        "composite_breakdown": best_breakdown,
        "all_trials": trials,
    }


# ---------------------------------------------------------------------------
# Internal helpers — all pure numpy/pandas, no I/O
# ---------------------------------------------------------------------------


def _compute_weights(
    holdings: dict[str, float],
    prices: dict[str, float],
    tickers: list[str],
) -> dict[str, float]:
    values = {
        t: holdings[t] * prices[t] for t in tickers if t in holdings and t in prices
    }
    total = sum(values.values())
    if total <= 0:
        return {}
    return {t: v / total for t, v in values.items()}


def _portfolio_daily(
    returns: pd.DataFrame,
    weights: dict[str, float],
    tickers: list[str],
) -> pd.Series:
    """Portfolio daily simple returns (correct cross-sectional aggregation)."""
    valid = [t for t in tickers if t in weights and t in returns.columns]
    w = np.array([weights[t] for t in valid])
    simple = np.exp(returns[valid].values) - 1
    return pd.Series(simple @ w, index=returns.index)


def _annual_vol(daily_simple: pd.Series) -> float:
    daily_log = np.log1p(daily_simple)
    return float(np.std(daily_log, ddof=1) * np.sqrt(252))


def _sharpe(daily_simple: pd.Series, rf: float) -> float:
    """Delegates to the canonical sharpe_from_daily — one source of truth."""
    sharpe, _, _ = _sharpe_core(daily_simple.values, rf)
    return sharpe


def _build_reasoning(
    weight: float,
    sharpe_delta: float,
    vol_delta: float,
    int_beta: float,
    corr: float,
    quality: float,
    garp: float,
) -> str:
    """Build a plain-English explanation of why this allocation was chosen."""
    parts: list[str] = []

    parts.append(f"{weight * 100:.0f}% allocation chosen because:")

    if sharpe_delta > 0.02:
        parts.append(f"Sharpe ratio improves by {sharpe_delta:+.3f}")
    elif sharpe_delta > 0:
        parts.append(f"Sharpe ratio improves slightly ({sharpe_delta:+.3f})")

    if vol_delta > 0.005:
        parts.append(f"Volatility drops by {vol_delta * 100:.2f}%")

    if int_beta < 0:
        parts.append(
            f"Natural hedge (internal beta {int_beta:.2f} — moves opposite to your portfolio)"
        )
    elif int_beta < 0.5:
        parts.append(f"Strong diversifier (internal beta {int_beta:.2f})")
    elif int_beta < 0.8:
        parts.append(f"Moderate diversifier (internal beta {int_beta:.2f})")
    else:
        parts.append(f"Limited diversification (internal beta {int_beta:.2f})")

    if quality >= 70 and garp >= 60:
        parts.append(
            f"High quality ({quality:.0f}) at a reasonable price (GARP {garp:.0f})"
        )
    elif quality >= 70:
        parts.append(f"High quality business ({quality:.0f})")

    return " ".join(parts)
