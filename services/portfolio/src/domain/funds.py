from src.schemas.funds_schemas import (
    CatalogCategory,
    CatalogCompany,
    CatalogResponse,
    CatalogTrack,
    DerivedHolding,
    DerivedHoldingSource,
    FundSelection,
    FundTrackEntry,
    SelectionCoverage,
    UnmappedRow,
)


def find_track(
    catalog: list[FundTrackEntry],
    category: str,
    company_id: str,
    track_id: str,
) -> FundTrackEntry | None:
    for entry in catalog:
        if entry.category == category and entry.company_id == company_id and entry.track_id == track_id:
            return entry
    return None


def build_catalog_response(catalog: list[FundTrackEntry]) -> CatalogResponse:
    categories: dict[str, dict[str, CatalogCompany]] = {}

    for entry in catalog:
        companies = categories.setdefault(entry.category, {})
        company = companies.setdefault(
            entry.company_id,
            CatalogCompany(company_id=entry.company_id, company_name=entry.company_name, tracks=[]),
        )
        company.tracks.append(
            CatalogTrack(track_id=entry.track_id, track_name=entry.track_name, as_of_date=entry.as_of_date)
        )

    return CatalogResponse(
        categories=[
            CatalogCategory(category=category, companies=list(companies.values()))
            for category, companies in categories.items()
        ]
    )


def compute_selection_coverage(selection: FundSelection, track: FundTrackEntry) -> SelectionCoverage:
    """Compute what fraction of a fund's disclosed allocation actually maps to
    a real tradeable proxy vs. is silently dropped (no proxy_ticker).

    mapped_pct / total_pct is the fraction of the *disclosed* allocation that's
    tradeable; total_pct need not be 1.0 (funds can disclose >100% of value,
    e.g. via leveraged sleeves), so it's used as the normalizing denominator
    rather than assumed to be 1.0.
    """
    mapped_pct = sum(row.pct_of_fund for row in track.rows if row.proxy_ticker is not None)
    total_pct = sum(row.pct_of_fund for row in track.rows)
    mapped_ratio = (mapped_pct / total_pct) if total_pct > 0 else 0.0

    return SelectionCoverage(
        category=track.category,
        company_name=track.company_name,
        track_name=track.track_name,
        amount_usd=selection.amount_usd,
        mapped_pct=mapped_pct,
        total_pct=total_pct,
        mapped_amount_usd=selection.amount_usd * mapped_ratio,
    )


def compute_derived_holdings(
    selections: list[FundSelection],
    catalog: list[FundTrackEntry],
    prices: dict[str, float],
) -> tuple[list[DerivedHolding], list[UnmappedRow], list[SelectionCoverage]]:
    holdings: list[DerivedHolding] = []
    unmapped: list[UnmappedRow] = []
    coverage: list[SelectionCoverage] = []

    for selection in selections:
        track = find_track(catalog, selection.category, selection.company_id, selection.track_id)
        if track is None:
            continue

        source = DerivedHoldingSource(
            category=track.category, company_name=track.company_name, track_name=track.track_name
        )
        coverage.append(compute_selection_coverage(selection, track))

        for row in track.rows:
            if row.proxy_ticker is None:
                unmapped.append(
                    UnmappedRow(
                        category=track.category,
                        company_name=track.company_name,
                        track_name=track.track_name,
                        label=row.label,
                        pct_of_fund=row.pct_of_fund,
                    )
                )
                continue

            price = prices.get(row.proxy_ticker)
            if price is None or price <= 0:
                continue

            shares = selection.amount_usd * row.pct_of_fund / price
            holdings.append(DerivedHolding(ticker=row.proxy_ticker, shares=shares, source=source))

    return holdings, unmapped, coverage
