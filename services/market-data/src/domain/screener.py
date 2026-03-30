"""Cheap quality screener.

Finds the intersection of high quality and low valuation across
configurable stock universes. Default scans S&P 400 midcap (~440 tickers)
for speed; S&P 500 available via the "us_large" universe.

Quality from ROIC, margins, FCF, earnings consistency.
Valuation from PEG, forward P/E.

Scoring: cheap_quality = quality_score × (100 - valuation_pctile) / 100.
Or simple filter: quality > threshold AND PEG < 1.5 AND forward P/E < 20.
"""

from typing import Any


def cheap_quality_score(
    quality_data: dict[str, Any],
    info: dict[str, Any],
) -> float:
    """Compute a cheap-quality score combining quality and valuation.

    Higher = better (high quality, low valuation).
    """
    qs = quality_data.get("quality_score")
    if qs is None or qs == 0:
        return 0.0

    # Valuation penalty: higher P/E and PEG reduce the score
    fpe = info.get("forwardPE")
    peg = info.get("trailingPegRatio")

    # Forward P/E score: lower is better (0-100 scale)
    # Default 50 (neutral) when missing — consistent with peg_score default
    pe_score = 50.0
    if fpe is not None and isinstance(fpe, (int, float)) and fpe > 0:
        if fpe > 40:
            pe_score = 10.0
        elif fpe > 30:
            pe_score = 30.0
        elif fpe > 25:
            pe_score = 50.0
        elif fpe > 20:
            pe_score = 65.0
        elif fpe > 15:
            pe_score = 80.0
        else:
            pe_score = 100.0

    # PEG score: lower is better (0-100 scale)
    peg_score = 50.0  # default if missing
    if peg is not None and isinstance(peg, (int, float)) and peg > 0:
        if peg > 3.0:
            peg_score = 10.0
        elif peg > 2.0:
            peg_score = 25.0
        elif peg > 1.5:
            peg_score = 40.0
        elif peg > 1.0:
            peg_score = 65.0
        elif peg > 0.5:
            peg_score = 85.0
        else:
            peg_score = 100.0

    # Valuation composite (60% PE, 40% PEG)
    valuation_score = 0.6 * pe_score + 0.4 * peg_score

    # Cheap quality = quality × valuation / 100
    return float(qs) * valuation_score / 100.0


def screen_universe(
    scored: list[dict[str, Any]],
    min_quality: int = 50,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Filter and rank candidates by cheap-quality score.

    Args:
        scored: list of {ticker, quality_score, garp_score, cheap_quality_score, ...}.
        min_quality: minimum quality_score to include.
        limit: max results to return.

    Returns:
        Top candidates sorted by cheap_quality_score descending.
    """
    filtered = [
        s
        for s in scored
        if s.get("quality_score", 0) >= min_quality
        and s.get("cheap_quality_score", 0) > 0
    ]
    filtered.sort(key=lambda x: x.get("cheap_quality_score", 0), reverse=True)
    return filtered[:limit]
