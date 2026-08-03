from pydantic import BaseModel


class FundRow(BaseModel):
    label: str
    pct_of_fund: float  # fraction of the whole fund's value, e.g. 0.0712 for 7.12%
    proxy_ticker: str | None  # None => no real tradeable proxy exists


class FundTrackEntry(BaseModel):
    category: str  # "pension" | "kupat_gemel_lehashkaa" | "keren_hishtalmut"
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
    category: str
    company_id: str
    track_id: str
    amount_usd: float


class DeriveHoldingsRequest(BaseModel):
    selections: list[FundSelection]


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


class DeriveHoldingsResponse(BaseModel):
    holdings: list[DerivedHolding]
    unmapped: list[UnmappedRow]
