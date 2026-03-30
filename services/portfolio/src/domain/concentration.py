"""Portfolio concentration analysis.

Computes sector, geographic, and currency exposure weights,
plus HHI (Herfindahl-Hirschman Index) for position concentration.

All functions are pure computation — no I/O.
"""

from typing import Any

# Country → currency mapping for the most common domiciles.
# Used as a proxy — HQ country does not perfectly reflect revenue exposure,
# but it's the best approximation available from yfinance.
COUNTRY_TO_CURRENCY: dict[str, str] = {
    "United States": "USD",
    "China": "CNY",
    "Japan": "JPY",
    "United Kingdom": "GBP",
    "Germany": "EUR",
    "France": "EUR",
    "Netherlands": "EUR",
    "Ireland": "EUR",
    "Switzerland": "CHF",
    "Canada": "CAD",
    "Australia": "AUD",
    "South Korea": "KRW",
    "Taiwan": "TWD",
    "India": "INR",
    "Brazil": "BRL",
    "Israel": "ILS",
}


def _etf_sector(info: dict[str, Any]) -> str:
    """Derive a meaningful sector label for ETFs from their category/name."""
    category = info.get("category") or ""
    name = (info.get("shortName") or info.get("longName") or "").lower()
    if isinstance(category, str) and category:
        return category  # e.g. "Large Growth", "Large Value", "Bond"
    # Fallback from name keywords
    if any(k in name for k in ("bond", "treasury", "fixed", "aggregate", "tip")):
        return "Fixed Income"
    if any(k in name for k in ("dividend", "value")):
        return "Value Equity"
    if any(k in name for k in ("growth", "nasdaq", "tech")):
        return "Growth Equity"
    if any(
        k in name for k in ("international", "world", "global", "europe", "emerging")
    ):
        return "International Equity"
    if any(k in name for k in ("gold", "silver", "commodity", "oil")):
        return "Commodity"
    if any(k in name for k in ("real estate", "reit")):
        return "Real Estate"
    return "Diversified Equity"


def _etf_country(info: dict[str, Any]) -> str:
    """Derive a meaningful geographic label for ETFs."""
    category = (info.get("category") or "").lower()
    name = (info.get("shortName") or info.get("longName") or "").lower()
    fund_family = (info.get("fundFamily") or "").lower()

    # Explicit geographic signals
    if any(k in name or k in category for k in ("emerging", "em ")):
        return "Emerging Markets"
    if any(k in name or k in category for k in ("europe", "european")):
        return "Europe"
    if any(k in name or k in category for k in ("japan", "japanese")):
        return "Japan"
    if any(k in name or k in category for k in ("china", "chinese")):
        return "China"
    if any(
        k in name or k in category
        for k in ("international", "world", "global", "foreign")
    ):
        return "International"
    if any(k in name or k in category for k in ("israel", "tase")):
        return "Israel"
    # US-domiciled ETFs from major US fund families default to United States
    if any(
        k in fund_family
        for k in ("schwab", "vanguard", "ishares", "spdr", "invesco", "fidelity")
    ):
        return "United States"
    # Country from domicile if available
    country = info.get("country")
    if isinstance(country, str) and country:
        return country
    return "United States"  # sensible default for most ETFs


def compute_sector_weights(
    weights: dict[str, float],
    info_by_ticker: dict[str, dict[str, Any]],
) -> dict[str, float]:
    """Portfolio weight per sector.

    For stocks: uses yfinance sector field.
    For ETFs: uses category or infers from name (e.g. "Large Growth", "Fixed Income").
    """
    sectors: dict[str, float] = {}
    for ticker, w in weights.items():
        info = info_by_ticker.get(ticker, {})
        sector = info.get("sector")
        if not isinstance(sector, str) or not sector:
            # ETF or stock with missing sector
            quote_type = info.get("quoteType", "")
            if quote_type in ("ETF", "MUTUALFUND"):
                sector = _etf_sector(info)
            else:
                sector = "Unknown"
        sectors[sector] = sectors.get(sector, 0.0) + w
    return sectors


def compute_geographic_weights(
    weights: dict[str, float],
    info_by_ticker: dict[str, dict[str, Any]],
) -> dict[str, float]:
    """Portfolio weight per country of domicile.

    For stocks: uses yfinance country field.
    For ETFs: infers from fund name/category.
    """
    countries: dict[str, float] = {}
    for ticker, w in weights.items():
        info = info_by_ticker.get(ticker, {})
        country = info.get("country")
        if not isinstance(country, str) or not country:
            quote_type = info.get("quoteType", "")
            if quote_type in ("ETF", "MUTUALFUND"):
                country = _etf_country(info)
            else:
                country = "Unknown"
        countries[country] = countries.get(country, 0.0) + w
    return countries


def compute_currency_weights(
    geographic_weights: dict[str, float],
) -> dict[str, float]:
    """Derive currency exposure from geographic weights."""
    currencies: dict[str, float] = {}
    for country, w in geographic_weights.items():
        currency = COUNTRY_TO_CURRENCY.get(country, "OTHER")
        currencies[currency] = currencies.get(currency, 0.0) + w
    return currencies


def compute_hhi(weights: dict[str, float]) -> float:
    """Herfindahl-Hirschman Index: sum of squared weights.

    HHI = Σ(w_i²)
    Range: 1/n (perfectly equal) to 1.0 (single stock).
    HHI > 0.25 flags high concentration.
    """
    return sum(w * w for w in weights.values())


def compute_top_holding_pct(weights: dict[str, float]) -> float:
    """Weight of the largest single position."""
    return max(weights.values()) if weights else 0.0
