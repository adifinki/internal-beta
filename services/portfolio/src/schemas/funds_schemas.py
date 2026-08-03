from typing import Literal

from pydantic import BaseModel, Field

FundCategory = Literal["pension", "kupat_gemel_lehashkaa", "keren_hishtalmut"]


class FundRow(BaseModel):
    label: str
    pct_of_fund: float  # fraction of the whole fund's value, e.g. 0.0712 for 7.12%
    proxy_ticker: str | None  # None => no real tradeable proxy exists


class FundTrackEntry(BaseModel):
    category: FundCategory
    company_id: str
    company_name: str
    track_id: str
    track_name: str
    as_of_date: str
    rows: list[FundRow]


class CatalogTrack(BaseModel):
    track_id: str
    track_name: str
    as_of_date: str


class CatalogCompany(BaseModel):
    company_id: str
    company_name: str
    tracks: list[CatalogTrack]


class CatalogCategory(BaseModel):
    category: str
    companies: list[CatalogCompany]


class CatalogResponse(BaseModel):
    categories: list[CatalogCategory]


class FundSelection(BaseModel):
    category: FundCategory
    company_id: str
    track_id: str
    # gt=0 rejects zero/negative amounts; le=1e12 is a generous sanity ceiling;
    # allow_inf_nan=False rejects NaN/Infinity, which Pydantic otherwise accepts
    # for floats but which would break the frontend's JSON.parse.
    amount_usd: float = Field(gt=0, le=1e12, allow_inf_nan=False)


class DeriveHoldingsRequest(BaseModel):
    # 16 is a generous ceiling: the UI only exposes 3 fixed category slots today,
    # but this caps the request body size against abuse/mistakes without
    # blocking legitimate future multi-track-per-category use.
    selections: list[FundSelection] = Field(max_length=16)


class DerivedHoldingSource(BaseModel):
    category: str
    company_name: str
    track_name: str


class DerivedHolding(BaseModel):
    ticker: str
    shares: float
    source: DerivedHoldingSource


class UnmappedRow(BaseModel):
    category: str
    company_name: str
    track_name: str
    label: str
    pct_of_fund: float


class SelectionCoverage(BaseModel):
    """Per-selection disclosure of how much of a fund's allocation actually
    maps to a real tradeable proxy, vs. how much is silently dropped."""

    category: str
    company_name: str
    track_name: str
    amount_usd: float
    # Sum of pct_of_fund across rows that DO have a proxy_ticker.
    mapped_pct: float
    # Sum of pct_of_fund across ALL rows (mapped + unmapped). Funds can
    # disclose more than 100% of value (e.g. leveraged sleeves), so this
    # isn't guaranteed to be 1.0 - it's the denominator mapped_pct is
    # measured against.
    total_pct: float
    # amount_usd * (mapped_pct / total_pct) - the dollar amount that actually
    # contributes to computed holdings; the remainder is disclosed but dropped.
    mapped_amount_usd: float


class DeriveHoldingsResponse(BaseModel):
    holdings: list[DerivedHolding]
    unmapped: list[UnmappedRow]
    coverage: list[SelectionCoverage]
