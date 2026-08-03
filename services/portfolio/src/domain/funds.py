from src.schemas.funds_schemas import (
    CatalogCategory,
    CatalogCompany,
    CatalogResponse,
    CatalogTrack,
    DerivedHolding,
    DerivedHoldingSource,
    FundSelection,
    FundTrackEntry,
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


def compute_derived_holdings(
    selections: list[FundSelection],
    catalog: list[FundTrackEntry],
    prices: dict[str, float],
) -> tuple[list[DerivedHolding], list[UnmappedRow]]:
    holdings: list[DerivedHolding] = []
    unmapped: list[UnmappedRow] = []

    for selection in selections:
        track = find_track(catalog, selection.category, selection.company_id, selection.track_id)
        if track is None:
            continue

        source = DerivedHoldingSource(
            category=track.category, company_name=track.company_name, track_name=track.track_name
        )

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

    return holdings, unmapped
