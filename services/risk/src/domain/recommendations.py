"""Portfolio recommendation engine.

Generates 3-8 ranked, actionable recommendations grounded in:
  - John Bogle: diversification, cost, home country bias, fixed income ballast
  - Warren Buffett: quality businesses, ROIC, moat, thesis integrity, concentration discipline

Pure domain module — no I/O, no FastAPI, no httpx.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_PRIORITY_RANK: dict[str, int] = {"high": 0, "medium": 1, "low": 2}


# ---------------------------------------------------------------------------
# Age / time-horizon profile
# ---------------------------------------------------------------------------


def _age_profile(age: int) -> dict[str, Any]:
    """Return time-horizon context based on investor age.

    Brackets (traditional retirement at 65):
      < 35  — Growth phase: max equity, long runway, vol is friend not foe.
      35–49 — Accumulation: equity-heavy, begin adding defensive exposure.
      50–59 — Pre-retirement: protect capital, bonds 20-30%.
      60+   — Distribution: income + capital preservation.
    """
    horizon = max(0, 65 - age)
    if age < 35:
        return {
            "bracket": "growth",
            "horizon_years": horizon,
            "equity_pct": 95,
            "bond_pct": 5,
            "drawdown_threshold": 0.55,  # raise warning bar — young investors can handle more
            "fixed_income_vol_threshold": 0.40,  # suppress no-bond warning below this vol
            "guidance": (
                f"At {age}, you have ~{horizon} years of compounding ahead. "
                "Time is your greatest asset: a 40% drawdown is painful but fully recoverable "
                "at this stage. Focus on compounding high-quality businesses — "
                "unnecessary ballast slows long-run wealth creation."
            ),
            "priorities": [
                "compound quality",
                "avoid low-quality",
                "ignore short-term noise",
            ],
        }
    elif age < 50:
        return {
            "bracket": "accumulation",
            "horizon_years": horizon,
            "equity_pct": 85,
            "bond_pct": 15,
            "drawdown_threshold": 0.45,
            "fixed_income_vol_threshold": 0.28,
            "guidance": (
                f"At {age}, you have ~{horizon} years to grow and protect. "
                "Stay equity-heavy but begin adding a defensive layer — "
                "a 10-15% bond position reduces drawdowns without meaningfully hurting returns."
            ),
            "priorities": [
                "quality growth",
                "start building ballast",
                "watch sector concentration",
            ],
        }
    elif age < 60:
        return {
            "bracket": "pre_retirement",
            "horizon_years": horizon,
            "equity_pct": 70,
            "bond_pct": 30,
            "drawdown_threshold": 0.35,
            "fixed_income_vol_threshold": 0.20,
            "guidance": (
                f"At {age}, capital protection becomes as important as growth. "
                "Drawdowns take longer to recover and reduce the runway for compounding. "
                "Target 20-30% defensive allocation (bonds, cash equivalents)."
            ),
            "priorities": ["protect capital", "income generation", "reduce vol"],
        }
    else:
        return {
            "bracket": "distribution",
            "horizon_years": horizon,
            "equity_pct": 50,
            "bond_pct": 50,
            "drawdown_threshold": 0.25,
            "fixed_income_vol_threshold": 0.15,
            "guidance": (
                f"At {age}, preservation and income are the primary objectives. "
                "A large drawdown at this stage may not be recoverable in your timeframe. "
                "Target 40-50% defensive assets and prioritise dividend quality."
            ),
            "priorities": ["capital preservation", "income", "low volatility"],
        }


# ---------------------------------------------------------------------------
# Recommendation dataclass
# ---------------------------------------------------------------------------


@dataclass
class Recommendation:
    type: str  # "add" | "trim" | "exit" | "rebalance"
    ticker: str | None
    action: str  # e.g. "Trim NVDA from 15% to 8%"
    reason: str  # plain English with specific numbers
    evidence: dict[str, Any]  # the numbers that confirmed it
    priority: str  # "high" | "medium" | "low"


# ---------------------------------------------------------------------------
# generate_exit_trim_recommendations
# ---------------------------------------------------------------------------


def generate_exit_trim_recommendations(
    portfolio_analysis: dict[str, Any],
) -> list[Recommendation]:
    """Generate exit/trim/redundancy recommendations from a portfolio analysis dict.

    Uses:
      portfolio_analysis["mctr"]                      — {ticker: {mctr, pct_contribution}}
      portfolio_analysis["internal_betas"]             — {ticker: float}
      portfolio_analysis["weights"]                    — {ticker: float}
      portfolio_analysis["holdings_quality"]           — list of {ticker, quality_score, garp_score, thesis_health}
      portfolio_analysis["hedging"]["correlation_clusters"] — list of [tickerA, tickerB, corr_float]
    """
    mctr: dict[str, dict[str, Any]] = portfolio_analysis.get("mctr", {})
    internal_betas: dict[str, float] = portfolio_analysis.get("internal_betas", {})
    weights: dict[str, float] = portfolio_analysis.get("weights", {})
    holdings_quality: list[dict[str, Any]] = portfolio_analysis.get(
        "holdings_quality", []
    )
    hedging: dict[str, Any] = portfolio_analysis.get("hedging", {})
    clusters: list[Any] = hedging.get("correlation_clusters", [])

    quality_by_ticker: dict[str, dict[str, Any]] = {
        q["ticker"]: q for q in holdings_quality if "ticker" in q
    }

    n = len(weights)
    even_weight = 1.0 / n if n > 0 else 0.0

    recs: list[Recommendation] = []
    seen: set[str] = set()

    # Rule 1 — EXIT: broken thesis AND (pct_contribution > 25% OR internal_beta > 1.3 OR weight > 3x even)
    for ticker, quality in quality_by_ticker.items():
        thesis = quality.get("thesis_health") or {}
        if str(thesis.get("status", "")).lower() != "broken":
            continue
        pct_contrib = float(mctr.get(ticker, {}).get("pct_contribution", 0.0))
        beta = float(internal_betas.get(ticker, 1.0))
        w = float(weights.get(ticker, 0.0))
        qualifies = (
            pct_contrib > 0.25
            or beta > 1.3
            or (even_weight > 0 and w > 3 * even_weight)
        )
        if not qualifies:
            continue
        flags: list[str] = list(thesis.get("flags", []) or [])
        reason_parts: list[str] = []
        if pct_contrib > 0.25:
            reason_parts.append(
                f"contributes {pct_contrib * 100:.1f}% of portfolio risk"
            )
        if beta > 1.3:
            reason_parts.append(f"internal beta {beta:.2f}")
        if even_weight > 0 and w > 3 * even_weight:
            reason_parts.append(
                f"weight {w * 100:.1f}% vs {even_weight * 100:.1f}% even"
            )
        reason_str = "; ".join(reason_parts)
        flags_str = "; ".join(flags[:3]) if flags else "deteriorating fundamentals"
        recs.append(
            Recommendation(
                type="exit",
                ticker=ticker,
                action=f"Exit {ticker} — broken thesis with {reason_str}",
                reason=f"Thesis broken ({flags_str}). {reason_str.capitalize()}.",
                evidence={
                    "pct_contribution": pct_contrib,
                    "internal_beta": beta,
                    "weight": w,
                    "quality_score": float(quality.get("quality_score") or 0),
                    "thesis_flags": flags,
                },
                priority="high",
            )
        )
        seen.add(ticker)

    # Rule 2 — TRIM critical: pct_contribution > 40% (any quality)
    for ticker, m in mctr.items():
        if ticker in seen:
            continue
        pct_contrib = float(m.get("pct_contribution", 0.0))
        if pct_contrib <= 0.40:
            continue
        w = float(weights.get(ticker, 0.0))
        recs.append(
            Recommendation(
                type="trim",
                ticker=ticker,
                action=f"Trim {ticker} — contributes {pct_contrib * 100:.1f}% of portfolio risk",
                reason=(
                    f"{ticker} contributes {pct_contrib * 100:.1f}% of total portfolio volatility "
                    f"despite being only {w * 100:.1f}% by weight."
                ),
                evidence={
                    "pct_contribution": pct_contrib,
                    "weight": w,
                    "quality_score": float(
                        quality_by_ticker.get(ticker, {}).get("quality_score") or 0
                    ),
                },
                priority="high",
            )
        )
        seen.add(ticker)

    # Rule 3 — TRIM alert: pct_contribution > 25% AND quality_score < 55
    for ticker, m in mctr.items():
        if ticker in seen:
            continue
        pct_contrib = float(m.get("pct_contribution", 0.0))
        if pct_contrib <= 0.25:
            continue
        qs = float(quality_by_ticker.get(ticker, {}).get("quality_score") or 0)
        if qs >= 55:
            continue
        w = float(weights.get(ticker, 0.0))
        recs.append(
            Recommendation(
                type="trim",
                ticker=ticker,
                action=f"Trim {ticker} — high risk contribution with below-average quality",
                reason=(
                    f"{ticker} contributes {pct_contrib * 100:.1f}% of portfolio risk "
                    f"but has a quality score of only {qs:.0f}/100."
                ),
                evidence={
                    "pct_contribution": pct_contrib,
                    "weight": w,
                    "quality_score": qs,
                },
                priority="medium",
            )
        )
        seen.add(ticker)

    # Rule 4 — TRIM overweight: weight > 2.5x even_weight AND quality_score < 60
    if even_weight > 0:
        for ticker, w in weights.items():
            if ticker in seen:
                continue
            if w <= 2.5 * even_weight:
                continue
            qs = float(quality_by_ticker.get(ticker, {}).get("quality_score") or 0)
            if qs >= 60:
                continue
            pct_contrib = float(mctr.get(ticker, {}).get("pct_contribution", 0.0))
            recs.append(
                Recommendation(
                    type="trim",
                    ticker=ticker,
                    action=f"Trim {ticker} — overweight relative to quality",
                    reason=(
                        f"{ticker} is {w * 100:.1f}% of the portfolio "
                        f"({w / even_weight:.1f}x even weight) but quality score is only {qs:.0f}/100."
                    ),
                    evidence={
                        "weight": w,
                        "even_weight": even_weight,
                        "quality_score": qs,
                        "pct_contribution": pct_contrib,
                    },
                    priority="medium",
                )
            )
            seen.add(ticker)

    # Rule 5 — REDUNDANT: same correlation cluster, lower quality of pair
    for entry in clusters:
        if len(entry) < 3:
            continue
        t1, t2, corr = str(entry[0]), str(entry[1]), float(entry[2])
        if corr < 0.75:
            continue
        qs1 = float(quality_by_ticker.get(t1, {}).get("quality_score") or 0)
        qs2 = float(quality_by_ticker.get(t2, {}).get("quality_score") or 0)
        # Lower quality of the pair gets the recommendation
        weaker, peer = (t1, t2) if qs1 <= qs2 else (t2, t1)
        if weaker in seen:
            continue
        w_weak = float(weights.get(weaker, 0.0))
        pct_contrib = float(mctr.get(weaker, {}).get("pct_contribution", 0.0))
        recs.append(
            Recommendation(
                type="trim",
                ticker=weaker,
                action=f"Consider reducing {weaker} — moves with {peer} (corr {corr:.2f})",
                reason=(
                    f"{weaker} and {peer} have a correlation of {corr:.2f}. "
                    f"{weaker} has lower quality ({min(qs1, qs2):.0f} vs {max(qs1, qs2):.0f}), "
                    f"making it the redundant holding."
                ),
                evidence={
                    "correlation": corr,
                    "peer": peer,
                    "quality_score": float(min(qs1, qs2)),
                    "peer_quality_score": float(max(qs1, qs2)),
                    "weight": w_weak,
                    "pct_contribution": pct_contrib,
                },
                priority="low",
            )
        )
        seen.add(weaker)

    recs.sort(key=lambda r: _PRIORITY_RANK.get(r.priority, 2))
    return recs


# ---------------------------------------------------------------------------
# generate_rebalance_recommendation
# ---------------------------------------------------------------------------


def generate_rebalance_recommendation(
    optimize_result: dict[str, Any],
    current_vol: float,
) -> Recommendation | None:
    """Return a rebalance recommendation if min-variance reduces vol by > 2%.

    Args:
        optimize_result: result dict from POST /portfolio/optimize, containing
            "annual_volatility" and "rebalancing_trades".
        current_vol: current annualised portfolio volatility (fraction, e.g. 0.18).

    Returns:
        A Recommendation or None if the improvement is below the 2% threshold.
    """
    optimised_vol = float(optimize_result.get("annual_volatility", current_vol))
    if current_vol - optimised_vol <= 0.02:
        return None

    # optimization.py returns rebalancing_trades as dict[str, float] (ticker → delta_shares)
    raw_trades = optimize_result.get("rebalancing_trades") or {}
    if isinstance(raw_trades, dict):
        trades_list: list[dict[str, Any]] = [
            {"ticker": t, "delta_shares": round(d, 2)}
            for t, d in raw_trades.items()
            if abs(d) > 0.01
        ]
    else:
        trades_list = list(raw_trades)
    top_trades = sorted(
        trades_list, key=lambda t: abs(float(t.get("delta_shares", 0))), reverse=True
    )[:3]

    return Recommendation(
        type="rebalance",
        ticker=None,
        action=(
            f"Rebalance portfolio — reduces volatility from "
            f"{current_vol * 100:.1f}% to {optimised_vol * 100:.1f}%"
        ),
        reason=(
            f"Min-variance rebalancing would reduce annualised volatility by "
            f"{(current_vol - optimised_vol) * 100:.1f} percentage points "
            f"without changing which stocks you hold."
        ),
        evidence={
            "current_vol": current_vol,
            "optimised_vol": optimised_vol,
            "vol_reduction": current_vol - optimised_vol,
            "top_trades": top_trades,
        },
        priority="medium",
    )


_MAX_RECOMMENDATIONS = 8


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def generate_recommendations(
    weights: dict[str, float],
    risk: dict[str, float],
    mctr: dict[str, dict[str, float]],
    internal_betas: dict[str, float],
    hedging: dict[str, Any],
    holdings_quality: list[dict[str, Any]],
    concentration: dict[str, Any],
    stress: dict[str, Any],
    portfolio_value: float,
    age: int = 27,
) -> list[dict[str, Any]]:
    """Return up to 8 ranked recommendations for the portfolio.

    Each recommendation has: priority, category, title, body, action, principle.
    """
    quality_by_ticker: dict[str, dict[str, Any]] = {
        q["ticker"]: q for q in holdings_quality if "ticker" in q
    }
    profile = _age_profile(age)

    rules = [
        _rule_age_horizon,
        _rule_single_position_concentration,
        _rule_mctr_dominance,
        _rule_uncompensated_risk,
        _rule_correlation_cluster,
        _rule_broken_thesis,
        _rule_sector_concentration,
        _rule_home_country_bias,
        _rule_no_fixed_income,
        _rule_natural_hedge,
        _rule_max_drawdown,
        _rule_star_holdings,
        _rule_quality_diversifier,
    ]

    results: list[dict[str, Any]] = []
    featured: set[str] = set()  # tickers already in a recommendation

    for rule in rules:
        rec = rule(
            weights,
            risk,
            mctr,
            internal_betas,
            hedging,
            quality_by_ticker,
            concentration,
            stress,
            portfolio_value,
            featured,
            profile,
        )
        if rec is not None:
            results.append(rec)

    results.sort(key=lambda r: _PRIORITY_RANK.get(str(r.get("priority", "low")), 2))

    # Convert from internal format to the frontend-expected format:
    # {type, ticker, action, reason, evidence, priority}
    _TYPE_FROM_CATEGORY: dict[str, str] = {
        "concentration": "trim",
        "risk": "rebalance",
        "diversification": "rebalance",
        "quality": "add",
        "valuation": "add",
        "horizon": "context",
        "gap": "context",
    }

    def _convert(r: dict[str, Any]) -> dict[str, Any]:
        cat = str(r.get("category", "risk"))
        title = str(r.get("title", ""))
        body = str(r.get("body", ""))
        action_text = str(r.get("action", ""))
        principle = str(r.get("principle", ""))
        # Infer ticker from title (e.g. "NVDA drives 38% of risk")
        ticker: str | None = None
        for word in title.split():
            clean = word.strip(".,:'")
            if clean.isupper() and 2 <= len(clean) <= 6 and clean.isalpha():
                ticker = clean
                break
        # For "trim" type, extract ticker from action
        inferred_type = _TYPE_FROM_CATEGORY.get(cat, "rebalance")
        if "trim" in title.lower() or "trim" in action_text.lower():
            inferred_type = "trim"
        elif "exit" in title.lower() or "broken" in title.lower():
            inferred_type = "exit"
        elif "add" in title.lower() or "consider" in title.lower():
            inferred_type = "add"

        # Build evidence from the rule's supporting metrics.
        # Extract numeric facts that the rule computed so the frontend can
        # display them in the expandable evidence panel.
        evidence: dict[str, Any] = {}

        if ticker:
            w = weights.get(ticker)
            if w is not None:
                evidence["weight"] = w
            ib = internal_betas.get(ticker)
            if ib is not None:
                evidence["internal_beta"] = ib
            mctr_entry = mctr.get(ticker, {})
            pct_c = mctr_entry.get("pct_contribution")
            if pct_c is not None:
                evidence["pct_contribution"] = float(pct_c)
            q = quality_by_ticker.get(ticker, {})
            qs = q.get("quality_score")
            if qs is not None:
                evidence["quality_score"] = float(qs)
            gs = q.get("garp_score")
            if gs is not None:
                evidence["garp_score"] = float(gs)

        # Portfolio-level metrics for non-ticker rules
        if cat == "risk":
            sharpe = risk.get("sharpe")
            if sharpe is not None:
                evidence["sharpe"] = float(sharpe)
            vol = risk.get("volatility")
            if vol is not None:
                evidence["volatility"] = float(vol)
            dd = risk.get("max_drawdown_pct")
            if dd is not None:
                evidence["max_drawdown"] = float(dd)
        if cat == "concentration":
            sectors_data: dict[str, float] = concentration.get("sectors", {})
            if sectors_data:
                top_sector = max(sectors_data, key=lambda s: float(sectors_data[s]))
                evidence["sector_weight"] = float(sectors_data[top_sector])
            hhi = concentration.get("hhi")
            if hhi is not None:
                evidence["hhi"] = float(hhi)
        if cat == "diversification":
            hhi = concentration.get("hhi")
            if hhi is not None:
                evidence["hhi"] = float(hhi)
            num = len(weights)
            if num > 0:
                evidence["num_holdings"] = num
            beta = risk.get("portfolio_beta")
            if beta is not None:
                evidence["portfolio_beta"] = float(beta)

        evidence["action_detail"] = action_text
        evidence["principle"] = principle

        return {
            "type": inferred_type,
            "ticker": ticker,
            "action": title,
            "reason": body,
            "evidence": evidence,
            "priority": r.get("priority", "medium"),
        }

    return [_convert(r) for r in results[:_MAX_RECOMMENDATIONS]]


# ---------------------------------------------------------------------------
# Rule 0 — Age / time-horizon context
# ---------------------------------------------------------------------------


def _rule_age_horizon(
    weights: dict[str, float],
    risk: dict[str, float],
    mctr: dict[str, dict[str, float]],
    internal_betas: dict[str, float],
    hedging: dict[str, Any],
    quality_by_ticker: dict[str, dict[str, Any]],
    concentration: dict[str, Any],
    stress: dict[str, Any],
    portfolio_value: float,
    featured: set[str],
    profile: dict[str, Any],
) -> dict[str, Any] | None:
    """Surface time-horizon context once per analysis."""
    bracket = str(profile.get("bracket", "growth"))
    horizon = int(profile.get("horizon_years", 38))
    equity_pct = int(profile.get("equity_pct", 95))
    bond_pct = int(profile.get("bond_pct", 5))
    guidance = str(profile.get("guidance", ""))
    priorities: list[str] = list(profile.get("priorities", []))

    bracket_labels = {
        "growth": "Growth phase",
        "accumulation": "Accumulation phase",
        "pre_retirement": "Pre-retirement phase",
        "distribution": "Distribution phase",
    }
    label = bracket_labels.get(bracket, "Growth phase")
    priorities_str = " | ".join(priorities) if priorities else ""

    return {
        "priority": "low",
        "category": "horizon",
        "title": f"{label}: ~{horizon}-year investment runway",
        "body": guidance,
        "action": (
            f"Target allocation for your stage: ~{equity_pct}% equities, ~{bond_pct}% bonds/defensive. "
            f"Key priorities: {priorities_str}."
        ),
        "principle": (
            "Bogle: the single most important factor in portfolio construction is time horizon. "
            "Strategy at 27 should look nothing like strategy at 60."
        ),
    }


# ---------------------------------------------------------------------------
# Rule 1 — Single position > 25%
# ---------------------------------------------------------------------------


def _rule_single_position_concentration(
    weights: dict[str, float],
    risk: dict[str, float],
    mctr: dict[str, dict[str, float]],
    internal_betas: dict[str, float],
    hedging: dict[str, Any],
    quality_by_ticker: dict[str, dict[str, Any]],
    concentration: dict[str, Any],
    stress: dict[str, Any],
    portfolio_value: float,
    featured: set[str],
    profile: dict[str, Any],
) -> dict[str, Any] | None:
    if not weights:
        return None
    ticker = max(weights, key=lambda t: weights[t])
    w = weights[ticker]
    if w <= 0.25:
        return None
    wp = w * 100
    dv = w * portfolio_value
    featured.add(ticker)
    return {
        "priority": "high" if wp > 35 else "medium",
        "category": "concentration",
        "title": f"{ticker} is {wp:.1f}% of your portfolio",
        "body": (
            f"{ticker} represents {wp:.1f}% of your holdings (${dv:,.0f}). "
            f"A single bad earnings report, regulatory action, or sector rotation "
            f"could inflict outsized damage. No single position should threaten the portfolio."
        ),
        "action": f"Trim {ticker} to below 20% and redeploy into lower-correlated holdings.",
        "principle": (
            "Buffett: never hold a position so large it threatens you. "
            "Bogle: diversification is the only free lunch in investing."
        ),
    }


# ---------------------------------------------------------------------------
# Rule 2 — One ticker > 40% MCTR
# ---------------------------------------------------------------------------


def _rule_mctr_dominance(
    weights: dict[str, float],
    risk: dict[str, float],
    mctr: dict[str, dict[str, float]],
    internal_betas: dict[str, float],
    hedging: dict[str, Any],
    quality_by_ticker: dict[str, dict[str, Any]],
    concentration: dict[str, Any],
    stress: dict[str, Any],
    portfolio_value: float,
    featured: set[str],
    profile: dict[str, Any],
) -> dict[str, Any] | None:
    if not mctr:
        return None
    ticker = max(mctr, key=lambda t: float(mctr[t].get("pct_contribution", 0.0)))
    pct = float(mctr[ticker].get("pct_contribution", 0.0))
    if pct <= 0.40:
        return None
    rp = pct * 100
    wp = weights.get(ticker, 0.0) * 100
    featured.add(ticker)
    return {
        "priority": "high" if rp > 50 else "medium",
        "category": "risk",
        "title": f"{ticker} drives {rp:.0f}% of your total portfolio risk",
        "body": (
            f"{ticker} is only {wp:.1f}% of your portfolio by value but contributes "
            f"{rp:.0f}% of total volatility. A volatile position can dominate risk "
            f"even when small — your portfolio's fate is tied to one stock."
        ),
        "action": (
            f"Trim {ticker} or add lower-beta positions to bring its risk "
            f"contribution below 30%."
        ),
        "principle": (
            "MCTR measures actual risk added, not just position size. "
            "Buffett: know what you own and why."
        ),
    }


# ---------------------------------------------------------------------------
# Rule 3 — Sharpe < 0.5 with vol > 20%
# ---------------------------------------------------------------------------


def _rule_uncompensated_risk(
    weights: dict[str, float],
    risk: dict[str, float],
    mctr: dict[str, dict[str, float]],
    internal_betas: dict[str, float],
    hedging: dict[str, Any],
    quality_by_ticker: dict[str, dict[str, Any]],
    concentration: dict[str, Any],
    stress: dict[str, Any],
    portfolio_value: float,
    featured: set[str],
    profile: dict[str, Any],
) -> dict[str, Any] | None:
    sharpe = float(risk.get("sharpe", 0.0))
    vol = float(risk.get("volatility", 0.0))
    if not (sharpe < 0.5 and vol > 0.20):
        return None
    vp = vol * 100
    rp = float(risk.get("annual_return", 0.0)) * 100
    return {
        "priority": "high",
        "category": "risk",
        "title": f"High volatility ({vp:.1f}%) with poor Sharpe ({sharpe:.2f})",
        "body": (
            f"Your portfolio has {vp:.1f}% annual volatility but only a {sharpe:.2f} "
            f"Sharpe ratio (historical return: {rp:.1f}%). You are taking significant "
            f"risk without being adequately compensated."
        ),
        "action": (
            "Identify your highest-MCTR holdings and review whether their return "
            "justifies the risk they add. Trim volatile low-quality positions."
        ),
        "principle": (
            "Bogle: uncompensated risk is risk you could eliminate through diversification. "
            "A Sharpe below 0.5 means the portfolio is inefficiently constructed."
        ),
    }


# ---------------------------------------------------------------------------
# Rule 4 — Correlation cluster of 3+ stocks
# ---------------------------------------------------------------------------


def _rule_correlation_cluster(
    weights: dict[str, float],
    risk: dict[str, float],
    mctr: dict[str, dict[str, float]],
    internal_betas: dict[str, float],
    hedging: dict[str, Any],
    quality_by_ticker: dict[str, dict[str, Any]],
    concentration: dict[str, Any],
    stress: dict[str, Any],
    portfolio_value: float,
    featured: set[str],
    profile: dict[str, Any],
) -> dict[str, Any] | None:
    clusters: list[list[Any]] = hedging.get("correlation_clusters", [])
    if not clusters:
        return None

    adj: dict[str, set[str]] = {}
    edge_corrs: dict[tuple[str, str], float] = {}
    for entry in clusters:
        if len(entry) < 3:
            continue
        t1, t2, corr = str(entry[0]), str(entry[1]), float(entry[2])
        if corr < 0.75:
            continue
        adj.setdefault(t1, set()).add(t2)
        adj.setdefault(t2, set()).add(t1)
        edge_corrs[(min(t1, t2), max(t1, t2))] = corr

    visited: set[str] = set()
    components: list[list[str]] = []
    for node in adj:
        if node in visited:
            continue
        comp: list[str] = []
        q: list[str] = [node]
        while q:
            n = q.pop()
            if n in visited:
                continue
            visited.add(n)
            comp.append(n)
            q.extend(adj.get(n, set()) - visited)
        components.append(comp)

    large = [c for c in components if len(c) >= 3]
    if not large:
        return None

    grp = max(large, key=lambda c: sum(weights.get(t, 0.0) for t in c))
    grp_wp = sum(weights.get(t, 0.0) for t in grp) * 100
    pairs = [
        edge_corrs.get((min(a, b), max(a, b)), 0.0)
        for i, a in enumerate(grp)
        for b in grp[i + 1 :]
    ]
    avg_corr = sum(pairs) / len(pairs) if pairs else 0.0

    return {
        "priority": "medium",
        "category": "diversification",
        "title": f"Redundant cluster: {', '.join(grp)} move together",
        "body": (
            f"{', '.join(grp)} form a high-correlation cluster "
            f"(avg correlation: {avg_corr:.2f}), representing {grp_wp:.1f}% of your portfolio. "
            f"Holding all of them provides no diversification benefit — "
            f"in a downturn, they will all fall together."
        ),
        "action": (
            "Keep your highest-conviction holding in this group; "
            "redeploy the others into uncorrelated sectors or asset classes."
        ),
        "principle": (
            "Bogle: correlation clusters are redundant exposure dressed as diversification. "
            "True diversification requires holdings that move independently."
        ),
    }


# ---------------------------------------------------------------------------
# Rule 5 — Broken thesis + weight > 5%
# ---------------------------------------------------------------------------


def _rule_broken_thesis(
    weights: dict[str, float],
    risk: dict[str, float],
    mctr: dict[str, dict[str, float]],
    internal_betas: dict[str, float],
    hedging: dict[str, Any],
    quality_by_ticker: dict[str, dict[str, Any]],
    concentration: dict[str, Any],
    stress: dict[str, Any],
    portfolio_value: float,
    featured: set[str],
    profile: dict[str, Any],
) -> dict[str, Any] | None:
    broken: list[tuple[str, float, list[str]]] = []
    for ticker, quality in quality_by_ticker.items():
        thesis = quality.get("thesis_health") or {}
        if str(thesis.get("status", "")).lower() != "broken":
            continue
        w = weights.get(ticker, 0.0)
        if w <= 0.05:
            continue
        flags: list[str] = list(thesis.get("flags", []) or [])
        broken.append((ticker, w, flags))

    if not broken:
        return None

    broken.sort(key=lambda x: x[1], reverse=True)
    ticker, w, flags = broken[0]
    wp = w * 100
    dv = w * portfolio_value
    flags_str = "; ".join(flags[:3]) if flags else "deteriorating fundamentals"
    others = [t for t, _, _ in broken[1:3]]
    others_note = f" (Also review: {', '.join(others)}.)" if others else ""
    featured.add(ticker)

    return {
        "priority": "high" if wp > 10 else "medium",
        "category": "quality",
        "title": f"{ticker}'s investment thesis is broken",
        "body": (
            f"{ticker} is {wp:.1f}% of your portfolio (${dv:,.0f}) "
            f"but shows a broken thesis: {flags_str}. "
            f"Holding a failing business hoping it recovers is not investing.{others_note}"
        ),
        "action": (
            f"Review {ticker} against its original thesis. "
            f"If it no longer holds, exit and redeploy into a higher-quality business."
        ),
        "principle": (
            "Buffett: it is far better to own a wonderful business at a fair price "
            "than a fair business at a wonderful price. A broken thesis means "
            "the business is no longer wonderful."
        ),
    }


# ---------------------------------------------------------------------------
# Rule 6 — Single sector > 45%
# ---------------------------------------------------------------------------


def _rule_sector_concentration(
    weights: dict[str, float],
    risk: dict[str, float],
    mctr: dict[str, dict[str, float]],
    internal_betas: dict[str, float],
    hedging: dict[str, Any],
    quality_by_ticker: dict[str, dict[str, Any]],
    concentration: dict[str, Any],
    stress: dict[str, Any],
    portfolio_value: float,
    featured: set[str],
    profile: dict[str, Any],
) -> dict[str, Any] | None:
    sectors: dict[str, float] = concentration.get("sectors", {})
    if not sectors:
        return None
    sector = max(sectors, key=lambda s: float(sectors[s]))
    sw = float(sectors[sector])
    if sw <= 0.45:
        return None
    sp = sw * 100
    sd = sw * portfolio_value
    return {
        "priority": "high" if sp > 60 else "medium",
        "category": "concentration",
        "title": f"{sp:.0f}% of your portfolio is in {sector}",
        "body": (
            f"{sector} represents {sp:.0f}% of your portfolio (${sd:,.0f}). "
            f"A sector-wide shock — regulatory change, rate sensitivity, commodity moves — "
            f"would simultaneously hit all your holdings."
        ),
        "action": (
            f"Reduce {sector} exposure below 40% by trimming or adding positions "
            f"in uncorrelated sectors."
        ),
        "principle": (
            "Bogle: no single sector should dominate a well-diversified portfolio. "
            "Sector concentration is uncompensated risk."
        ),
    }


# ---------------------------------------------------------------------------
# Rule 7 — US > 80% with no international
# ---------------------------------------------------------------------------


def _rule_home_country_bias(
    weights: dict[str, float],
    risk: dict[str, float],
    mctr: dict[str, dict[str, float]],
    internal_betas: dict[str, float],
    hedging: dict[str, Any],
    quality_by_ticker: dict[str, dict[str, Any]],
    concentration: dict[str, Any],
    stress: dict[str, Any],
    portfolio_value: float,
    featured: set[str],
    profile: dict[str, Any],
) -> dict[str, Any] | None:
    countries: dict[str, float] = concentration.get("countries", {})
    us = float(countries.get("United States", 0.0))
    if us <= 0.80:
        return None
    has_intl = any(
        c not in ("United States", "Unknown") and float(countries[c]) > 0.01
        for c in countries
    )
    if has_intl:
        return None
    return {
        "priority": "medium",
        "category": "diversification",
        "title": f"Home country bias: {us * 100:.0f}% in US equities",
        "body": (
            f"{us * 100:.0f}% of your portfolio is in US-domiciled companies. "
            f"The US represents ~60% of global market cap. Overweighting it concentrates "
            f"you in a single regulatory, currency, and economic regime."
        ),
        "action": (
            "Consider adding VXUS (total international) or EFA (developed markets) "
            "at 10-20% of portfolio to reduce home country bias."
        ),
        "principle": (
            "Bogle specifically warned about home country bias. "
            "A globally diversified portfolio captures growth wherever it occurs."
        ),
    }


# ---------------------------------------------------------------------------
# Rule 8 — No fixed income + vol > 25%
# ---------------------------------------------------------------------------


def _rule_no_fixed_income(
    weights: dict[str, float],
    risk: dict[str, float],
    mctr: dict[str, dict[str, float]],
    internal_betas: dict[str, float],
    hedging: dict[str, Any],
    quality_by_ticker: dict[str, dict[str, Any]],
    concentration: dict[str, Any],
    stress: dict[str, Any],
    portfolio_value: float,
    featured: set[str],
    profile: dict[str, Any],
) -> dict[str, Any] | None:
    vol = float(risk.get("volatility", 0.0))
    # Age-adjusted threshold: young investors (growth bracket) have a long runway
    # and do not need bonds as ballast — only surface this above their higher tolerance.
    vol_threshold = float(profile.get("fixed_income_vol_threshold", 0.25))
    if vol <= vol_threshold:
        return None
    sectors: dict[str, float] = concentration.get("sectors", {})
    has_fi = any("fixed income" in s.lower() or "bond" in s.lower() for s in sectors)
    if has_fi:
        return None
    vp = vol * 100
    crash_pct = float((stress.get("2020_crash") or {}).get("return_pct", 0.0)) * 100
    crash_usd = float((stress.get("2020_crash") or {}).get("dollars", 0.0))
    bracket = str(profile.get("bracket", "growth"))
    bond_pct = int(profile.get("bond_pct", 10))
    if bracket == "growth":
        body = (
            f"Your portfolio has {vp:.1f}% annual volatility and zero fixed income. "
            f"At your time horizon, high equity allocation is appropriate — "
            f"but if vol exceeds {vp:.0f}%, consider a small defensive position "
            f"(5% AGG) purely as psychological insurance against panic selling at the bottom."
        )
        action = "Optional: 5% in AGG for drawdown discipline — not for return."
    else:
        body = (
            f"Your portfolio has {vp:.1f}% annual volatility and zero fixed income. "
            f"During the 2020 crash it would have fallen {crash_pct:.1f}% "
            f"(${abs(crash_usd):,.0f}). Bonds act as ballast — they tend to hold value "
            f"or rise when equities fall sharply."
        )
        action = (
            f"Consider allocating {bond_pct}% to AGG (broad bonds) or TIP "
            "(inflation-protected) to reduce drawdown severity."
        )
    return {
        "priority": "medium" if bracket != "growth" else "low",
        "category": "risk",
        "title": f"No fixed income with {vp:.1f}% volatility",
        "body": body,
        "action": action,
        "principle": (
            "Bogle: fixed income is not about return — it is about surviving "
            "downturns long enough to let equities recover."
        ),
    }


# ---------------------------------------------------------------------------
# Rule 9 — Negative internal beta (natural hedge — positive signal)
# ---------------------------------------------------------------------------


def _rule_natural_hedge(
    weights: dict[str, float],
    risk: dict[str, float],
    mctr: dict[str, dict[str, float]],
    internal_betas: dict[str, float],
    hedging: dict[str, Any],
    quality_by_ticker: dict[str, dict[str, Any]],
    concentration: dict[str, Any],
    stress: dict[str, Any],
    portfolio_value: float,
    featured: set[str],
    profile: dict[str, Any],
) -> dict[str, Any] | None:
    neg = [(t, float(b)) for t, b in internal_betas.items() if float(b) < 0.0]
    if not neg:
        return None
    ticker, beta = min(neg, key=lambda x: x[1])
    wp = weights.get(ticker, 0.0) * 100
    return {
        "priority": "low",
        "category": "risk",
        "title": f"{ticker} is a natural hedge — worth holding",
        "body": (
            f"{ticker} has an internal beta of {beta:.2f} against your portfolio — "
            f"it moves opposite when your other holdings fall. Currently {wp:.1f}% "
            f"of your portfolio. Natural hedges are rare and valuable: "
            f"they provide insurance without an options premium."
        ),
        "action": (
            f"Maintain or modestly increase {ticker}'s weight. "
            f"Its negative correlation provides portfolio-level insurance during stress."
        ),
        "principle": (
            "A natural hedge that moves against your portfolio during stress "
            "is more valuable than its standalone return suggests."
        ),
    }


# ---------------------------------------------------------------------------
# Rule 10 — Max drawdown > 40%
# ---------------------------------------------------------------------------


def _rule_max_drawdown(
    weights: dict[str, float],
    risk: dict[str, float],
    mctr: dict[str, dict[str, float]],
    internal_betas: dict[str, float],
    hedging: dict[str, Any],
    quality_by_ticker: dict[str, dict[str, Any]],
    concentration: dict[str, Any],
    stress: dict[str, Any],
    portfolio_value: float,
    featured: set[str],
    profile: dict[str, Any],
) -> dict[str, Any] | None:
    dd = float(risk.get("max_drawdown_pct", 0.0))
    # Age-adjusted threshold: young investors can tolerate larger drawdowns
    dd_threshold = float(profile.get("drawdown_threshold", 0.40))
    if abs(dd) <= dd_threshold:
        return None
    ddp = abs(dd) * 100
    ddd = abs(float(risk.get("max_drawdown_dollars", dd * portfolio_value)))
    rec = int(risk.get("recovery_days", 0))
    crash_pct = float((stress.get("2020_crash") or {}).get("return_pct", 0.0)) * 100
    shock_pct = float((stress.get("2022_shock") or {}).get("return_pct", 0.0)) * 100
    horizon = int(profile.get("horizon_years", 38))
    bracket = str(profile.get("bracket", "growth"))
    if bracket == "growth":
        context = (
            f"With ~{horizon} years ahead, you have time to recover — "
            f"but only if you hold through the drawdown. The real danger is panic selling at the bottom."
        )
        action = (
            "Build conviction in your highest-quality holdings now, "
            "so you can hold through the inevitable drawdowns ahead."
        )
        priority = "medium"
    else:
        context = (
            "A drawdown this large creates real risk you sell at the bottom — "
            "permanently locking in losses."
        )
        action = (
            "Review your highest-MCTR holdings. Consider whether adding fixed income "
            "or defensive positions reduces drawdown to a level you can hold through."
        )
        priority = "high"
    return {
        "priority": priority,
        "category": "risk",
        "title": f"Historical drawdown of -{ddp:.1f}% risks panic selling",
        "body": (
            f"Your portfolio's worst drawdown was -{ddp:.1f}% (${ddd:,.0f}). "
            f"Recovery took {rec} trading days. "
            f"In the 2020 crash: {crash_pct:.1f}%. In 2022: {shock_pct:.1f}%. "
            f"{context}"
        ),
        "action": action,
        "principle": (
            "Buffett: the first rule is never lose money; the second rule is "
            "never forget the first. A portfolio you cannot hold through a downturn "
            "is a portfolio that will hurt you."
        ),
    }


# ---------------------------------------------------------------------------
# Rule 11 — High quality + high GARP (star holdings)
# ---------------------------------------------------------------------------


def _rule_star_holdings(
    weights: dict[str, float],
    risk: dict[str, float],
    mctr: dict[str, dict[str, float]],
    internal_betas: dict[str, float],
    hedging: dict[str, Any],
    quality_by_ticker: dict[str, dict[str, Any]],
    concentration: dict[str, Any],
    stress: dict[str, Any],
    portfolio_value: float,
    featured: set[str],
    profile: dict[str, Any],
) -> dict[str, Any] | None:
    stars = [
        (
            t,
            float(q.get("quality_score") or 0),
            float(q.get("garp_score") or 0),
            weights.get(t, 0.0),
            float(internal_betas.get(t, 1.0)),
            float(mctr.get(t, {}).get("pct_contribution", 0.0)),
        )
        for t, q in quality_by_ticker.items()
        if q.get("type") != "ETF"
        and float(q.get("quality_score") or 0) > 70
        and float(q.get("garp_score") or 0) > 70
        # GATE ON PORTFOLIO MATH: only flag if adding more would actually help.
        # Internal beta < 0.75 means the holding diversifies the portfolio.
        # MCTR contribution < 0.30 means it is not already dominating risk.
        # Weight < 0.20 means there is room to grow without over-concentrating.
        and float(internal_betas.get(t, 1.0)) < 0.75
        and float(mctr.get(t, {}).get("pct_contribution", 0.0)) < 0.30
        and weights.get(t, 0.0) < 0.20
    ]
    if not stars:
        return None
    # Sort by quality + GARP, then prefer lower internal beta (better diversifier)
    stars.sort(key=lambda x: (x[1] + x[2]) - x[4] * 30)
    ticker, qs, gs, w, beta, risk_pct = stars[0]
    wp = w * 100
    featured.add(ticker)
    others = [(t, float(qs2), float(gs2)) for t, qs2, gs2, _, _, _ in stars[1:2]]
    others_note = (
        f" ({others[0][0]} also qualifies: quality {others[0][1]:.0f}, GARP {others[0][2]:.0f}.)"
        if others
        else ""
    )
    return {
        "priority": "medium",
        "category": "quality",
        "title": f"{ticker}: high quality, reasonably priced, and diversifying",
        "body": (
            f"{ticker} scores {qs:.0f}/100 on quality and {gs:.0f}/100 on GARP. "
            f"Its internal beta vs your portfolio is {beta:.2f} — meaning it moves "
            f"somewhat independently and would add quality without amplifying concentration. "
            f"Currently {wp:.1f}% of your portfolio.{others_note}"
        ),
        "action": (
            f"Worth considering whether {ticker}'s weight reflects its quality. "
            f"It earns its place on both fundamentals and diversification."
        ),
        "principle": (
            "Buffett: it is far better to buy a wonderful company at a fair price "
            "than a fair company at a wonderful price."
        ),
    }


# ---------------------------------------------------------------------------
# Rule 12 — High quality + low internal beta (quality diversifier)
# ---------------------------------------------------------------------------


def _rule_quality_diversifier(
    weights: dict[str, float],
    risk: dict[str, float],
    mctr: dict[str, dict[str, float]],
    internal_betas: dict[str, float],
    hedging: dict[str, Any],
    quality_by_ticker: dict[str, dict[str, Any]],
    concentration: dict[str, Any],
    stress: dict[str, Any],
    portfolio_value: float,
    featured: set[str],
    profile: dict[str, Any],
) -> dict[str, Any] | None:
    candidates = [
        (
            t,
            float(q.get("quality_score") or 0),
            float(internal_betas.get(t, 1.0)),
            weights.get(t, 0.0),
        )
        for t, q in quality_by_ticker.items()
        if t not in featured
        and q.get("type") != "ETF"
        and float(q.get("quality_score") or 0) > 70
        and float(internal_betas.get(t, 1.0)) < 0.5
        # Also gate on MCTR and weight — only surface if adding more would not
        # amplify concentration risk
        and float(mctr.get(t, {}).get("pct_contribution", 0.0)) < 0.25
        and weights.get(t, 0.0) < 0.20
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[1], x[2]))
    ticker, qs, beta, w = candidates[0]
    wp = w * 100
    featured.add(ticker)
    return {
        "priority": "low",
        "category": "quality",
        "title": f"{ticker} improves both quality and diversification",
        "body": (
            f"{ticker} scores {qs:.0f}/100 on quality and has an internal beta of {beta:.2f} "
            f"— it moves largely independently of your portfolio. Currently {wp:.1f}% of holdings. "
            f"Positions that improve quality AND reduce correlation are the ideal building blocks."
        ),
        "action": (
            f"Consider increasing {ticker}'s allocation — "
            f"it earns its place on both business quality and portfolio diversification."
        ),
        "principle": (
            "Buffett: wide moat + durable ROIC > 15% defines a wonderful business. "
            "Bogle: true diversification means holdings that move independently."
        ),
    }
