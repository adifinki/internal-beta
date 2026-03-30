"""Quality scoring, GARP scoring, thesis health check, and moat approximation.

All functions are pure computation — no I/O, no yfinance, no Redis.
Input is pre-fetched data from ticker.info, ticker.financials,
ticker.balance_sheet, and ticker.cashflow.

Financial model references:
  - ROIC: Damodaran, "Return on Invested Capital"
  - PEG: Peter Lynch, "One Up on Wall Street" (1989)
  - Moat: Morningstar Economic Moat methodology (quantitative proxy)
  - Thesis health: multi-factor consistency check across 5yr financials
"""

from typing import Any

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# ETF detection
# ---------------------------------------------------------------------------


def is_etf(info: dict[str, Any] | None) -> bool:
    """Detect if a ticker is an ETF/fund rather than an individual stock."""
    if not info:
        return False
    quote_type = info.get("quoteType", "")
    return quote_type in ("ETF", "MUTUALFUND")


# ---------------------------------------------------------------------------
# Quality Score (0–100)
# ---------------------------------------------------------------------------


def quality_score(
    info: dict[str, Any] | None,
    financials: pd.DataFrame,
    balance_sheet: pd.DataFrame,
    cashflow: pd.DataFrame,
) -> int:
    """Weighted composite quality score.

    For ETFs: simplified score based on available fund-level metrics
    (P/E, yield, expense ratio, 5yr return, beta, total assets).

    For stocks: full score from ROIC, margins, FCF, earnings, debt, growth.

    Components for stocks (max weights):
      ROIC (25%), Gross margin level + stability (25%), FCF yield (15%),
      Earnings consistency (15%), Debt health (10%), Revenue growth (10%).

    MISSING DATA: Only components with available data contribute to the
    max_total denominator. A company with 4 of 6 fields scoring perfectly
    gets 100, not 67. This avoids penalizing non-US stocks and ADRs with
    incomplete yfinance coverage.
    """
    if not info:
        return 0
    if is_etf(info):
        return _etf_quality_score(info)

    # If financial statements are unavailable (holding companies, foreign stocks
    # with limited yfinance coverage), fall back to info-only scoring.
    has_financials = (
        not financials.empty
        and "Operating Income" in financials.index
        and "Total Revenue" in financials.index
    )
    if not has_financials:
        return _info_only_quality_score(info)

    total = 0
    max_total = 0

    # 1. ROIC (25 points)
    roic = _compute_roic(financials, balance_sheet)
    if roic is not None:
        max_total += 25
        if roic > 0.25:
            total += 25
        elif roic > 0.15:
            total += 20
        elif roic > 0.10:
            total += 15
        elif roic > 0.05:
            total += 8

    # 2. Gross margin level + stability (15 + 10 points)
    gm_level = _safe_float(info, "grossMargins")
    gm_stability = _gross_margin_stability(financials)

    if gm_level is not None:
        max_total += 15
        # Level component (15 points)
        if gm_level > 0.60:
            total += 15
        elif gm_level > 0.40:
            total += 12
        elif gm_level > 0.25:
            total += 8
        elif gm_level > 0.15:
            total += 4

    if gm_stability is not None:
        max_total += 10
        # Stability component (10 points) — lower stdev = more stable
        if gm_stability < 0.02:
            total += 10
        elif gm_stability < 0.05:
            total += 7
        elif gm_stability < 0.10:
            total += 3

    # 3. FCF yield (15 points)
    fcf = _safe_float(info, "freeCashflow")
    mcap = _safe_float(info, "marketCap")
    if fcf is not None and mcap is not None and mcap > 0 and fcf > 0:
        max_total += 15
        fcf_yield = fcf / mcap
        if fcf_yield > 0.08:
            total += 15
        elif fcf_yield > 0.05:
            total += 12
        elif fcf_yield > 0.03:
            total += 8
        elif fcf_yield > 0.01:
            total += 4

    # 4. Earnings consistency (15 points)
    earnings_cv = _earnings_consistency(financials)
    if earnings_cv is not None:
        max_total += 15
        all_positive = earnings_cv["all_positive"]
        cv = earnings_cv["cv"]
        if all_positive and cv < 0.10:
            total += 15
        elif all_positive and cv < 0.20:
            total += 12
        elif all_positive and cv < 0.30:
            total += 8
        elif all_positive:
            total += 4

    # 5. Debt health (10 points)
    dte = _safe_float(info, "debtToEquity")
    if dte is not None:
        max_total += 10
        if dte < 30:
            total += 10
        elif dte < 75:
            total += 8
        elif dte < 150:
            total += 5
        elif dte < 300:
            total += 2

    # 6. Revenue growth (10 points)
    rg = _safe_float(info, "revenueGrowth")
    if rg is not None:
        max_total += 10
        if rg > 0.15:
            total += 10
        elif rg > 0.08:
            total += 7
        elif rg > 0.03:
            total += 4
        elif rg > 0:
            total += 2

    return round(100 * total / max_total) if max_total > 0 else 0


# ---------------------------------------------------------------------------
# GARP Score (0–100)
# ---------------------------------------------------------------------------


def garp_score(info: dict[str, Any] | None) -> int:
    """Growth At a Reasonable Price score.

    For ETFs: simplified score from P/E and yield (ETFs don't have PEG or earnings growth).
    For stocks: PEG ratio (40%), Earnings growth rate (25%),
      Revenue growth rate (15%), Forward P/E (20%).
    """
    if not info:
        return 0
    if is_etf(info):
        return _etf_garp_score(info)

    total = 0
    max_total = 0

    # 1. PEG ratio (40 points) — lower is more attractive
    peg = _safe_float(info, "trailingPegRatio")
    if peg is not None and peg > 0:
        max_total += 40
        if peg < 0.5:
            total += 40
        elif peg < 1.0:
            total += 35
        elif peg < 1.5:
            total += 25
        elif peg < 2.0:
            total += 15
        elif peg < 3.0:
            total += 5

    # 2. Earnings growth rate (25 points)
    eg = _safe_float(info, "earningsGrowth")
    if eg is not None and eg > 0:
        max_total += 25
        if eg > 0.25:
            total += 25
        elif eg > 0.15:
            total += 20
        elif eg > 0.10:
            total += 15
        elif eg > 0.05:
            total += 10

    # 3. Revenue growth rate (15 points)
    rg = _safe_float(info, "revenueGrowth")
    if rg is not None and rg > 0:
        max_total += 15
        if rg > 0.20:
            total += 15
        elif rg > 0.10:
            total += 12
        elif rg > 0.05:
            total += 8

    # 4. Forward P/E (20 points) — lower is more attractive
    fpe = _safe_float(info, "forwardPE")
    if fpe is not None and fpe > 0:
        max_total += 20
        if fpe < 15:
            total += 20
        elif fpe < 20:
            total += 15
        elif fpe < 25:
            total += 10
        elif fpe < 35:
            total += 5

    return round(100 * total / max_total) if max_total > 0 else 0


# ---------------------------------------------------------------------------
# Thesis Health Check
# ---------------------------------------------------------------------------


def thesis_health_check(
    info: dict[str, Any] | None,
    financials: pd.DataFrame,
    balance_sheet: pd.DataFrame,
    cashflow: pd.DataFrame,
) -> dict[str, Any]:
    """Per-ticker assessment of whether the compounding thesis remains valid."""
    if not info:
        return {"status": "No data", "flags": ["ticker info unavailable"]}
    if is_etf(info):
        return _etf_thesis_health(info)

    revenue = _revenue_analysis(financials)
    earnings = _earnings_analysis(financials)
    roic_data = _roic_analysis(financials, balance_sheet)
    fcf_data = _fcf_analysis(info, financials, cashflow)
    balance = _balance_sheet_analysis(info)

    flags: list[str] = []

    # Determine overall status
    if revenue and not revenue["all_positive"]:
        flags.append("revenue declined in at least one year")
    if revenue and not revenue.get("accelerating", False):
        flags.append("revenue growth decelerating")
    if roic_data and roic_data["current"] is not None and roic_data["current"] < 0.10:
        flags.append("ROIC below 10%")
    if roic_data and not roic_data.get("stable", True):
        flags.append("ROIC unstable (CV > 0.20)")
    if (
        fcf_data
        and fcf_data.get("conversion") is not None
        and fcf_data["conversion"] < 0.5
    ):
        flags.append("low FCF conversion ratio")
    if (
        balance
        and balance.get("debt_to_equity") is not None
        and balance["debt_to_equity"] > 200
    ):
        flags.append("high debt/equity > 200%")

    if len(flags) == 0:
        status = "Strong"
    elif len(flags) <= 1:
        status = "Monitor"
    elif len(flags) <= 2:
        status = "Review"
    else:
        status = "Broken"

    return {
        "status": status,
        "revenue": revenue,
        "earnings": earnings,
        "roic": roic_data,
        "fcf": fcf_data,
        "balance": balance,
        "flags": flags,
    }


# ---------------------------------------------------------------------------
# Moat Approximation
# ---------------------------------------------------------------------------


def moat_rating(
    financials: pd.DataFrame,
    balance_sheet: pd.DataFrame,
) -> str:
    """Approximate moat from ROIC history (5yr).

    Wide:   avg ROIC > 20%, min > 12%, all years > 10%
    Narrow: avg ROIC > 12%, min > 6%
    None:   anything else

    Wide moat requires all years > 10% (sustained excellence).
    Narrow moat only requires min > 6% — a company with avg 15% and one
    dip to 8% is still a narrow-moat business, not "no moat."
    """
    roics = _compute_roic_history(financials, balance_sheet)
    if not roics or len(roics) < 3:
        return "None"

    avg = float(np.mean(roics))
    min_val = float(np.min(roics))
    all_above_10 = all(r > 0.10 for r in roics)

    if avg > 0.20 and min_val > 0.12 and all_above_10:
        return "Wide"
    elif avg > 0.12 and min_val > 0.06:
        return "Narrow"
    return "None"


# ---------------------------------------------------------------------------
# Internal helpers — all pure computation
# ---------------------------------------------------------------------------


def _safe_float(d: dict[str, Any], key: str) -> float | None:
    """Extract a float from a dict, returning None if missing or not numeric."""
    val = d.get(key)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _compute_roic(
    financials: pd.DataFrame, balance_sheet: pd.DataFrame
) -> float | None:
    """ROIC = NOPAT / Invested Capital (most recent year)."""
    try:
        op_income = float(financials.loc["Operating Income"].iloc[0])
        tax_rate = float(financials.loc["Tax Rate For Calcs"].iloc[0])
        invested_cap = float(balance_sheet.loc["Invested Capital"].iloc[0])
        if invested_cap <= 0:
            return None
        nopat = op_income * (1.0 - tax_rate)
        return nopat / invested_cap
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _compute_roic_history(
    financials: pd.DataFrame, balance_sheet: pd.DataFrame
) -> list[float]:
    """Compute ROIC for each available year."""
    roics: list[float] = []
    for i in range(min(len(financials.columns), len(balance_sheet.columns))):
        try:
            op_income = float(financials.loc["Operating Income"].iloc[i])
            tax_rate = float(financials.loc["Tax Rate For Calcs"].iloc[i])
            invested_cap = float(balance_sheet.loc["Invested Capital"].iloc[i])
            if invested_cap > 0:
                nopat = op_income * (1.0 - tax_rate)
                roics.append(nopat / invested_cap)
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return roics


def _gross_margin_stability(financials: pd.DataFrame) -> float | None:
    """Standard deviation of gross margins over available years."""
    margins: list[float] = []
    for col in financials.columns:
        try:
            gp = float(financials.loc["Gross Profit", col])
            rev = float(financials.loc["Total Revenue", col])
            if rev > 0:
                margins.append(gp / rev)
        except (KeyError, TypeError, ValueError):
            continue
    if len(margins) < 3:
        return None
    return float(np.std(margins, ddof=1))


def _earnings_consistency(financials: pd.DataFrame) -> dict[str, Any] | None:
    """Coefficient of variation of net income over available years."""
    net_incomes: list[float] = []
    for col in financials.columns:
        try:
            ni = float(financials.loc["Net Income", col])
            net_incomes.append(ni)
        except (KeyError, TypeError, ValueError):
            continue
    if len(net_incomes) < 3:
        return None
    mean = float(np.mean(net_incomes))
    if mean <= 0:
        return {"cv": float("inf"), "all_positive": False}
    return {
        "cv": float(np.std(net_incomes, ddof=1) / mean),
        "all_positive": all(ni > 0 for ni in net_incomes),
    }


def _revenue_analysis(financials: pd.DataFrame) -> dict[str, Any] | None:
    """Analyse revenue trajectory over 5 years."""
    revenues: list[float] = []
    for col in sorted(financials.columns):  # oldest first
        try:
            revenues.append(float(financials.loc["Total Revenue", col]))
        except (KeyError, TypeError, ValueError):
            continue
    if len(revenues) < 3:
        return None

    yoy = [
        (revenues[i] - revenues[i - 1]) / abs(revenues[i - 1])
        for i in range(1, len(revenues))
        if revenues[i - 1] != 0
    ]
    if not yoy:
        return None

    n = len(revenues)
    cagr = (
        (revenues[-1] / revenues[0]) ** (1.0 / (n - 1)) - 1.0
        if revenues[0] > 0
        else None
    )

    # Acceleration: rather than comparing exactly 2 years (noisy), check if
    # the latest YoY growth is at least 80% of the prior year's rate. This
    # tolerates minor deceleration from a high base (e.g. 30% → 25%) without
    # triggering a false "decelerating" flag that would alarm investors.
    accelerating = False
    if len(yoy) >= 2 and yoy[-2] > 0:
        # Truly accelerating, or decelerating by less than 20% of prior rate
        accelerating = yoy[-1] >= yoy[-2] * 0.8

    return {
        "cagr_5yr": cagr,
        "all_positive": all(g > 0 for g in yoy),
        "accelerating": accelerating,
        "latest_yoy": yoy[-1] if yoy else None,
    }


def _earnings_analysis(financials: pd.DataFrame) -> dict[str, Any] | None:
    """Analyse earnings trajectory."""
    net_incomes: list[float] = []
    revenues: list[float] = []
    for col in sorted(financials.columns):
        try:
            net_incomes.append(float(financials.loc["Net Income", col]))
            revenues.append(float(financials.loc["Total Revenue", col]))
        except (KeyError, TypeError, ValueError):
            continue
    if len(net_incomes) < 3:
        return None

    n = len(net_incomes)
    cagr = None
    if net_incomes[0] > 0 and net_incomes[-1] > 0:
        cagr = (net_incomes[-1] / net_incomes[0]) ** (1.0 / (n - 1)) - 1.0

    # Margin expansion: is earnings growing faster than revenue?
    margin_expanding = False
    if len(revenues) >= 2 and revenues[-2] > 0 and revenues[-1] > 0:
        prev_margin = net_incomes[-2] / revenues[-2]
        curr_margin = net_incomes[-1] / revenues[-1]
        margin_expanding = curr_margin > prev_margin

    return {
        "cagr_5yr": cagr,
        "all_positive": all(ni > 0 for ni in net_incomes),
        "margin_expanding": margin_expanding,
    }


def _roic_analysis(
    financials: pd.DataFrame, balance_sheet: pd.DataFrame
) -> dict[str, Any] | None:
    """ROIC trajectory analysis."""
    roics = _compute_roic_history(financials, balance_sheet)
    if not roics:
        return None

    current = roics[0]  # most recent year
    avg = float(np.mean(roics))
    stable = bool(np.std(roics, ddof=1) / avg < 0.20) if avg > 0 else False

    return {
        "current": current,
        "avg_5yr": avg,
        "stable": stable,
        "moat": moat_rating(financials, balance_sheet),
    }


def _fcf_analysis(
    info: dict[str, Any],
    financials: pd.DataFrame,
    cashflow: pd.DataFrame,
) -> dict[str, Any] | None:
    """Free cash flow analysis."""
    fcf = _safe_float(info, "freeCashflow")
    mcap = _safe_float(info, "marketCap")
    fcf_yield = (fcf / mcap) if (fcf and mcap and mcap > 0) else None

    # FCF conversion: FCF / Net Income
    conversion = None
    try:
        latest_fcf = float(cashflow.loc["Free Cash Flow"].iloc[0])
        latest_ni = float(financials.loc["Net Income"].iloc[0])
        if latest_ni > 0:
            conversion = latest_fcf / latest_ni
    except (KeyError, IndexError, TypeError, ValueError):
        pass

    # Is FCF growing?
    growing = False
    try:
        fcf_values = [
            float(cashflow.loc["Free Cash Flow", col])
            for col in sorted(cashflow.columns)
        ]
        if len(fcf_values) >= 2:
            growing = fcf_values[-1] > fcf_values[0]
    except (KeyError, TypeError, ValueError):
        pass

    return {
        "yield": fcf_yield,
        "conversion": conversion,
        "growing": growing,
    }


def _balance_sheet_analysis(info: dict[str, Any]) -> dict[str, Any] | None:
    """Balance sheet health metrics from ticker.info."""
    dte = _safe_float(info, "debtToEquity")
    current_ratio = _safe_float(info, "currentRatio")

    return {
        "debt_to_equity": dte,
        "current_ratio": current_ratio,
    }


# ---------------------------------------------------------------------------
# ETF-specific scoring — ETFs don't have financial statements
# ---------------------------------------------------------------------------


def _etf_quality_score(info: dict[str, Any]) -> int:
    """Simplified quality score for ETFs using fund-level metrics.

    Components:
      5yr avg return (25%), P/E reasonableness (25%), Dividend yield (20%),
      Total assets / liquidity (15%), Low beta (15%).
    """
    total = 0
    max_total = 0

    # 1. 5yr average return (25 points)
    max_total += 25
    five_yr = _safe_float(info, "fiveYearAverageReturn")
    if five_yr is not None:
        if five_yr > 0.12:
            total += 25
        elif five_yr > 0.08:
            total += 20
        elif five_yr > 0.05:
            total += 15
        elif five_yr > 0.02:
            total += 8

    # 2. P/E reasonableness (25 points) — lower is better for ETFs
    max_total += 25
    pe = _safe_float(info, "trailingPE")
    if pe is not None and pe > 0:
        if pe < 15:
            total += 25
        elif pe < 20:
            total += 20
        elif pe < 25:
            total += 15
        elif pe < 35:
            total += 8

    # 3. Dividend yield (20 points)
    max_total += 20
    div_yield = _safe_float(info, "dividendYield")
    if div_yield is not None:
        # yfinance returns yield as decimal for ETFs (e.g., 0.38 = 0.38%)
        # but sometimes as percentage (e.g., 2.5 = 2.5%)
        y = div_yield if div_yield < 1 else div_yield / 100
        if y > 0.04:
            total += 20
        elif y > 0.02:
            total += 15
        elif y > 0.01:
            total += 10
        elif y > 0:
            total += 5

    # 4. Total assets / liquidity (15 points) — larger = more liquid/stable
    max_total += 15
    assets = _safe_float(info, "totalAssets")
    if assets is not None:
        if assets > 50e9:
            total += 15
        elif assets > 10e9:
            total += 12
        elif assets > 1e9:
            total += 8
        elif assets > 100e6:
            total += 4

    # 5. Low beta (15 points) — lower beta = less market sensitivity
    max_total += 15
    beta = _safe_float(info, "beta3Year") or _safe_float(info, "beta")
    if beta is not None:
        if beta < 0.7:
            total += 15
        elif beta < 0.9:
            total += 12
        elif beta < 1.1:
            total += 8
        elif beta < 1.3:
            total += 4

    return round(100 * total / max_total) if max_total > 0 else 0


def _etf_garp_score(info: dict[str, Any]) -> int:
    """Simplified GARP score for ETFs.

    ETFs don't have PEG or earnings growth. Use P/E and yield as proxies.
    """
    total = 0
    max_total = 0

    # P/E (60 points)
    max_total += 60
    pe = _safe_float(info, "trailingPE")
    if pe is not None and pe > 0:
        if pe < 15:
            total += 60
        elif pe < 20:
            total += 45
        elif pe < 25:
            total += 30
        elif pe < 35:
            total += 15

    # Dividend yield as value proxy (40 points)
    max_total += 40
    div_yield = _safe_float(info, "dividendYield")
    if div_yield is not None and div_yield > 0:
        y = div_yield if div_yield < 1 else div_yield / 100
        if y > 0.04:
            total += 40
        elif y > 0.02:
            total += 30
        elif y > 0.01:
            total += 20
        elif y > 0:
            total += 10

    return round(100 * total / max_total) if max_total > 0 else 0


def _etf_thesis_health(info: dict[str, Any]) -> dict[str, Any]:
    """Simplified thesis health for ETFs — based on available fund metrics."""
    flags: list[str] = []

    five_yr = _safe_float(info, "fiveYearAverageReturn")
    if five_yr is not None and five_yr < 0:
        flags.append("negative 5yr average return")

    assets = _safe_float(info, "totalAssets")
    if assets is not None and assets < 100e6:
        flags.append("small fund (<$100M AUM)")

    category = info.get("category", "Unknown")
    fund_family = info.get("fundFamily", "Unknown")

    status = "Strong" if len(flags) == 0 else "Monitor" if len(flags) == 1 else "Review"

    return {
        "status": status,
        "type": "ETF",
        "category": category,
        "fund_family": fund_family,
        "five_year_return": five_yr,
        "total_assets": assets,
        "flags": flags,
    }


def _info_only_quality_score(info: dict[str, Any]) -> int:
    """Simplified quality score when financial statements are unavailable.

    Used for holding companies (Berkshire), foreign stocks with limited
    yfinance coverage, and other tickers where financials are empty.
    Uses only ticker.info fields which are available for most equities.

    Components:
      ROE (25%) — proxy for capital efficiency
      Gross margin (20%) — pricing power (may be absent for holding cos)
      FCF yield (20%) — cash generation
      Debt/equity (20%) — balance sheet safety
      Revenue growth (15%) — business momentum
    """
    total = 0
    max_total = 0

    # 1. ROE as proxy for ROIC when statement data is unavailable (25 pts)
    max_total += 25
    roe = _safe_float(info, "returnOnEquity")
    if roe is not None:
        if roe > 0.20:
            total += 25
        elif roe > 0.12:
            total += 18
        elif roe > 0.07:
            total += 10
        elif roe > 0:
            total += 5

    # 2. Gross margin (20 pts)
    max_total += 20
    gm = _safe_float(info, "grossMargins")
    if gm is not None:
        if gm > 0.50:
            total += 20
        elif gm > 0.30:
            total += 14
        elif gm > 0.15:
            total += 8

    # 3. FCF yield (20 pts)
    max_total += 20
    fcf = _safe_float(info, "freeCashflow")
    mcap = _safe_float(info, "marketCap")
    if fcf is not None and mcap is not None and mcap > 0 and fcf > 0:
        yield_ = fcf / mcap
        if yield_ > 0.06:
            total += 20
        elif yield_ > 0.03:
            total += 14
        elif yield_ > 0.01:
            total += 7

    # 4. Debt health (20 pts)
    max_total += 20
    dte = _safe_float(info, "debtToEquity")
    if dte is not None:
        if dte < 30:
            total += 20
        elif dte < 80:
            total += 14
        elif dte < 150:
            total += 7

    # 5. Revenue growth (15 pts)
    max_total += 15
    rg = _safe_float(info, "revenueGrowth")
    if rg is not None and rg > 0:
        if rg > 0.12:
            total += 15
        elif rg > 0.06:
            total += 10
        elif rg > 0.02:
            total += 5

    return round(100 * total / max_total) if max_total > 0 else 0
