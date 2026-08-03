# Savings Funds Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Savings" tab where the user picks a company + fund track for each of Pension / Kupat Gemel LeHashkaa / Keren Hishtalmut, enters a USD amount, and has the fund's disclosed asset allocation translated into proxy-ETF holdings that merge into the same holdings pipeline used by every other tab.

**Architecture:** A new static fund catalog (portfolio service) maps company → category → track → allocation rows, each row carrying a precomputed `pct_of_fund` and an optional real `proxy_ticker`. A new `/portfolio/funds/catalog` endpoint feeds the 3 dropdown pickers; a new `/portfolio/funds/derive-holdings` endpoint turns the user's 3 selections + amounts into `{ticker, shares}` rows (fetching live prices exactly like the existing portfolio endpoints do). The frontend keeps manually-typed holdings and fund-derived holdings as separate state, sums them by ticker into one `combinedHoldings` array fed to every existing tab, and tags rows in the Holdings table with their source breakdown.

**Tech Stack:** FastAPI + Pydantic (portfolio service), React + TanStack Query + TypeScript (frontend). No new dependencies.

## Global Constraints

- No FX conversion — user enters the USD-equivalent amount directly (per design spec).
- Fund selections persist to `localStorage` only, not the shareable URL.
- Rows with no real tradeable proxy (`proxy_ticker: null`) must never be converted into a holding — they're surfaced as informational text only.
- Follow existing code conventions: portfolio service routes delegate to `src/domain/*` pure functions; schemas live in `src/schemas/*`; tests mock `market_data_client`/domain functions the same way `test_portfolio_routes.py` does.

---

### Task 1: Funds schemas

**Files:**
- Create: `services/portfolio/src/schemas/funds_schemas.py`

**Interfaces:**
- Produces: `FundRow`, `FundTrackEntry`, `CatalogTrack`, `CatalogCompany`, `CatalogCategory`, `CatalogResponse`, `FundSelection`, `DerivedHoldingSource`, `DerivedHolding`, `UnmappedRow`, `DeriveHoldingsRequest`, `DeriveHoldingsResponse` — all Pydantic `BaseModel`s, used by Tasks 2-4.

- [ ] **Step 1: Write the schemas**

```python
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
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `cd services/portfolio && python -c "from src.schemas.funds_schemas import CatalogResponse, DeriveHoldingsResponse; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add services/portfolio/src/schemas/funds_schemas.py
git commit -m "feat: add pydantic schemas for savings funds catalog and derivation"
```

---

### Task 2: Fund catalog seed data

**Files:**
- Create: `services/portfolio/src/domain/funds_catalog.py`

**Interfaces:**
- Consumes: `FundTrackEntry`, `FundRow` from Task 1 (`src.schemas.funds_schemas`).
- Produces: `FUND_CATALOG: list[FundTrackEntry]` — the module-level constant Tasks 3-4 read from.

This seeds exactly one real fund: **Analyst — Gemel LeHaskaa Klali**, sourced from the provided fact sheet (as of 2025-12-31). Percentages are the equity-sleeve weight (47.46%) times each benchmark sub-split, and the corporate-bond sleeve weight (23.59%) times its sub-split, matching the design spec's table. Government bonds, the Israeli-general corporate bond slice, and the money-market cash row have no confirmed real-world proxy yet — they're `proxy_ticker: None` for now; Task 9 researches real TASE-listed proxies for them.

- [ ] **Step 1: Write the catalog**

```python
from src.schemas.funds_schemas import FundRow, FundTrackEntry

FUND_CATALOG: list[FundTrackEntry] = [
    FundTrackEntry(
        category="kupat_gemel_lehashkaa",
        company_id="analyst",
        company_name="Analyst",
        track_id="gemel_lehaskaa_klali",
        track_name="Gemel LeHaskaa Klali",
        as_of_date="2025-12-31",
        rows=[
            FundRow(label="Equities - TA-125", pct_of_fund=0.4746 * 0.45, proxy_ticker=None),
            FundRow(label="Equities - S&P 500", pct_of_fund=0.4746 * 0.15, proxy_ticker="SPY"),
            FundRow(label="Equities - MSCI World", pct_of_fund=0.4746 * 0.40, proxy_ticker="URTH"),
            FundRow(label="Government bonds (Tel Gov Klali)", pct_of_fund=0.3100, proxy_ticker=None),
            FundRow(label="Corporate bonds - Israeli general", pct_of_fund=0.2359 * 0.75, proxy_ticker=None),
            FundRow(label="Corporate bonds - Global aggregate", pct_of_fund=0.2359 * 0.25, proxy_ticker="LQD"),
            FundRow(label="Cash (Makam 3-month)", pct_of_fund=0.1377, proxy_ticker=None),
            FundRow(label="Other", pct_of_fund=0.0151, proxy_ticker=None),
        ],
    ),
]
```

- [ ] **Step 2: Verify it imports and sums close to 1.0**

Run: `cd services/portfolio && python -c "
from src.domain.funds_catalog import FUND_CATALOG
total = sum(r.pct_of_fund for r in FUND_CATALOG[0].rows)
print(round(total, 4))
"`
Expected: a number close to `1.18` (the fund's disclosed total exceeds 100% due to derivative exposure, per the fact sheet's own footnote — this is expected, not a bug).

- [ ] **Step 3: Commit**

```bash
git add services/portfolio/src/domain/funds_catalog.py
git commit -m "feat: seed fund catalog with Analyst Gemel LeHaskaa Klali fact sheet"
```

---

### Task 3: Fund derivation domain logic

**Files:**
- Create: `services/portfolio/src/domain/funds.py`
- Test: `services/portfolio/tests/test_funds_domain.py`

**Interfaces:**
- Consumes: `FundTrackEntry`, `FundRow`, `FundSelection`, `DerivedHolding`, `DerivedHoldingSource`, `UnmappedRow`, `CatalogResponse`, `CatalogCategory`, `CatalogCompany`, `CatalogTrack` (Task 1).
- Produces:
  - `find_track(catalog: list[FundTrackEntry], category: str, company_id: str, track_id: str) -> FundTrackEntry | None`
  - `build_catalog_response(catalog: list[FundTrackEntry]) -> CatalogResponse`
  - `compute_derived_holdings(selections: list[FundSelection], catalog: list[FundTrackEntry], prices: dict[str, float]) -> tuple[list[DerivedHolding], list[UnmappedRow]]`
  - Used by Task 4's route.

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for savings-fund derivation: catalog lookup, catalog->API shape, and
amount -> proxy-ticker shares math."""

import pytest

from src.domain.funds import build_catalog_response, compute_derived_holdings, find_track
from src.schemas.funds_schemas import FundRow, FundSelection, FundTrackEntry


def _sample_catalog() -> list[FundTrackEntry]:
    return [
        FundTrackEntry(
            category="pension",
            company_id="acme",
            company_name="Acme",
            track_id="general",
            track_name="General",
            as_of_date="2025-01-01",
            rows=[
                FundRow(label="US equities", pct_of_fund=0.5, proxy_ticker="SPY"),
                FundRow(label="Bonds", pct_of_fund=0.3, proxy_ticker="LQD"),
                FundRow(label="Untradeable local bonds", pct_of_fund=0.2, proxy_ticker=None),
            ],
        ),
    ]


class TestFindTrack:
    def test_finds_existing_track(self) -> None:
        catalog = _sample_catalog()
        track = find_track(catalog, "pension", "acme", "general")
        assert track is not None
        assert track.track_name == "General"

    def test_returns_none_for_unknown_track(self) -> None:
        catalog = _sample_catalog()
        assert find_track(catalog, "pension", "acme", "nonexistent") is None

    def test_returns_none_for_unknown_category(self) -> None:
        catalog = _sample_catalog()
        assert find_track(catalog, "keren_hishtalmut", "acme", "general") is None


class TestBuildCatalogResponse:
    def test_groups_by_category_then_company(self) -> None:
        catalog = _sample_catalog()
        response = build_catalog_response(catalog)

        assert len(response.categories) == 1
        assert response.categories[0].category == "pension"
        assert len(response.categories[0].companies) == 1
        assert response.categories[0].companies[0].company_id == "acme"
        assert len(response.categories[0].companies[0].tracks) == 1
        assert response.categories[0].companies[0].tracks[0].track_id == "general"

    def test_two_tracks_same_company_grouped_together(self) -> None:
        catalog = _sample_catalog()
        catalog.append(
            FundTrackEntry(
                category="pension",
                company_id="acme",
                company_name="Acme",
                track_id="sp500",
                track_name="S&P 500 Track",
                as_of_date="2025-01-01",
                rows=[FundRow(label="US equities", pct_of_fund=1.0, proxy_ticker="SPY")],
            )
        )
        response = build_catalog_response(catalog)

        assert len(response.categories) == 1
        assert len(response.categories[0].companies) == 1
        assert len(response.categories[0].companies[0].tracks) == 2


class TestComputeDerivedHoldings:
    def test_computes_shares_from_amount_and_price(self) -> None:
        catalog = _sample_catalog()
        selections = [FundSelection(category="pension", company_id="acme", track_id="general", amount_usd=1000.0)]
        prices = {"SPY": 500.0, "LQD": 100.0}

        holdings, unmapped = compute_derived_holdings(selections, catalog, prices)

        spy = next(h for h in holdings if h.ticker == "SPY")
        assert spy.shares == pytest.approx(1000.0 * 0.5 / 500.0)  # = 1.0
        lqd = next(h for h in holdings if h.ticker == "LQD")
        assert lqd.shares == pytest.approx(1000.0 * 0.3 / 100.0)  # = 3.0

    def test_unmapped_rows_never_become_holdings(self) -> None:
        catalog = _sample_catalog()
        selections = [FundSelection(category="pension", company_id="acme", track_id="general", amount_usd=1000.0)]
        prices = {"SPY": 500.0, "LQD": 100.0}

        holdings, unmapped = compute_derived_holdings(selections, catalog, prices)

        assert all(h.ticker not in (None, "") for h in holdings)
        assert len(unmapped) == 1
        assert unmapped[0].label == "Untradeable local bonds"
        assert unmapped[0].pct_of_fund == pytest.approx(0.2)

    def test_holding_source_is_tagged(self) -> None:
        catalog = _sample_catalog()
        selections = [FundSelection(category="pension", company_id="acme", track_id="general", amount_usd=1000.0)]
        prices = {"SPY": 500.0, "LQD": 100.0}

        holdings, _ = compute_derived_holdings(selections, catalog, prices)

        spy = next(h for h in holdings if h.ticker == "SPY")
        assert spy.source.category == "pension"
        assert spy.source.company_name == "Acme"
        assert spy.source.track_name == "General"

    def test_missing_price_skips_that_row(self) -> None:
        """If a proxy ticker's price couldn't be fetched, that row is silently
        dropped from holdings — it is NOT added to unmapped (unmapped means
        'no real proxy exists', not 'price fetch failed')."""
        catalog = _sample_catalog()
        selections = [FundSelection(category="pension", company_id="acme", track_id="general", amount_usd=1000.0)]
        prices = {"SPY": 500.0}  # LQD price missing

        holdings, unmapped = compute_derived_holdings(selections, catalog, prices)

        tickers = [h.ticker for h in holdings]
        assert "LQD" not in tickers
        assert "SPY" in tickers
        assert len(unmapped) == 1  # still just the genuinely-unmapped row

    def test_unknown_selection_produces_no_holdings(self) -> None:
        catalog = _sample_catalog()
        selections = [FundSelection(category="pension", company_id="acme", track_id="nonexistent", amount_usd=1000.0)]

        holdings, unmapped = compute_derived_holdings(selections, catalog, {"SPY": 500.0})

        assert holdings == []
        assert unmapped == []

    def test_multiple_selections_are_independent(self) -> None:
        catalog = _sample_catalog()
        catalog.append(
            FundTrackEntry(
                category="keren_hishtalmut",
                company_id="beta",
                company_name="Beta",
                track_id="general",
                track_name="General",
                as_of_date="2025-01-01",
                rows=[FundRow(label="US equities", pct_of_fund=1.0, proxy_ticker="SPY")],
            )
        )
        selections = [
            FundSelection(category="pension", company_id="acme", track_id="general", amount_usd=1000.0),
            FundSelection(category="keren_hishtalmut", company_id="beta", track_id="general", amount_usd=500.0),
        ]
        prices = {"SPY": 500.0, "LQD": 100.0}

        holdings, _ = compute_derived_holdings(selections, catalog, prices)

        spy_holdings = [h for h in holdings if h.ticker == "SPY"]
        assert len(spy_holdings) == 2  # one per selection, NOT pre-summed — the frontend sums by ticker
        assert {h.source.category for h in spy_holdings} == {"pension", "keren_hishtalmut"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd services/portfolio && python -m pytest tests/test_funds_domain.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.domain.funds'`

- [ ] **Step 3: Write the implementation**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd services/portfolio && python -m pytest tests/test_funds_domain.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add services/portfolio/src/domain/funds.py services/portfolio/tests/test_funds_domain.py
git commit -m "feat: add fund catalog lookup and holdings-derivation domain logic"
```

---

### Task 4: Funds route + wire into app

**Files:**
- Modify: `services/portfolio/src/infrastructure/market_data_client.py` (extract shared `prices_from_info` helper)
- Modify: `services/portfolio/src/routes/portfolio.py:48-64` (use the extracted helper instead of the private `_prices_from_info`)
- Create: `services/portfolio/src/routes/funds.py`
- Modify: `services/portfolio/src/main.py`
- Test: `services/portfolio/tests/test_funds_routes.py`

**Interfaces:**
- Consumes: `fetch_info_batch` (existing, `src.infrastructure.market_data_client`), `find_track`/`build_catalog_response`/`compute_derived_holdings` (Task 3), `FUND_CATALOG` (Task 2), all schemas (Task 1).
- Produces: `prices_from_info(tickers: list[str], info_by_ticker: dict[str, dict]) -> dict[str, float]` (now public, in `market_data_client.py`), `GET /portfolio/funds/catalog`, `POST /portfolio/funds/derive-holdings`.

`_prices_from_info` in `routes/portfolio.py` is pure price-extraction logic that the new funds route also needs. Moving it to `infrastructure/market_data_client.py` (next to the other market-data helpers) avoids duplicating it — this is the one targeted refactor this plan makes, kept minimal.

- [ ] **Step 1: Extract the shared price helper**

In `services/portfolio/src/infrastructure/market_data_client.py`, add:

```python
def prices_from_info(
    tickers: list[str],
    info_by_ticker: dict[str, dict[str, Any]],
) -> dict[str, float]:
    """Extract current prices from yfinance info dicts."""
    prices: dict[str, float] = {}
    for t in tickers:
        info = info_by_ticker.get(t, {})
        p = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("navPrice")
            or info.get("previousClose")
        )
        if p is not None:
            prices[t] = float(p)
    return prices
```

In `services/portfolio/src/routes/portfolio.py`, delete the local `_prices_from_info` function (lines 48-64) and its two call sites' references — replace `_prices_from_info(...)` with `prices_from_info(...)` in both `get_portfolio_profile` and `post_optimize`, and add `prices_from_info` to the existing `from src.infrastructure.market_data_client import (...)` block.

- [ ] **Step 2: Run existing portfolio tests to confirm the refactor didn't break anything**

Run: `cd services/portfolio && python -m pytest tests/test_portfolio_routes.py -v`
Expected: all PASS (same as before the refactor)

- [ ] **Step 3: Write the failing route tests**

```python
"""Tests for savings-fund routes: GET /portfolio/funds/catalog and
POST /portfolio/funds/derive-holdings.

Uses FastAPI TestClient with a patched FUND_CATALOG so tests don't depend
on the real seeded data changing over time.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.schemas.funds_schemas import FundRow, FundTrackEntry


@pytest.fixture
def client() -> TestClient:
    app.state.redis = AsyncMock()
    app.state.market_data_client = AsyncMock()
    return TestClient(app)


def _test_catalog() -> list[FundTrackEntry]:
    return [
        FundTrackEntry(
            category="pension",
            company_id="acme",
            company_name="Acme",
            track_id="general",
            track_name="General",
            as_of_date="2025-01-01",
            rows=[
                FundRow(label="US equities", pct_of_fund=0.5, proxy_ticker="SPY"),
                FundRow(label="Untradeable bonds", pct_of_fund=0.5, proxy_ticker=None),
            ],
        ),
    ]


class TestGetCatalog:
    @patch("src.routes.funds.FUND_CATALOG", new=_test_catalog())
    def test_returns_categories(self, client: TestClient) -> None:
        resp = client.get("/portfolio/funds/catalog")
        assert resp.status_code == 200

        data = resp.json()
        assert data["categories"][0]["category"] == "pension"
        assert data["categories"][0]["companies"][0]["company_id"] == "acme"


class TestDeriveHoldings:
    @patch("src.routes.funds.FUND_CATALOG", new=_test_catalog())
    @patch("src.routes.funds.fetch_info_batch")
    def test_computes_holdings_for_valid_selection(
        self, mock_fetch: AsyncMock, client: TestClient
    ) -> None:
        mock_fetch.return_value = {"SPY": {"currentPrice": 500.0}}

        resp = client.post(
            "/portfolio/funds/derive-holdings",
            json={
                "selections": [
                    {"category": "pension", "company_id": "acme", "track_id": "general", "amount_usd": 1000.0}
                ]
            },
        )
        assert resp.status_code == 200

        data = resp.json()
        assert len(data["holdings"]) == 1
        assert data["holdings"][0]["ticker"] == "SPY"
        assert data["holdings"][0]["shares"] == pytest.approx(1.0)
        assert len(data["unmapped"]) == 1
        assert data["unmapped"][0]["label"] == "Untradeable bonds"

    @patch("src.routes.funds.FUND_CATALOG", new=_test_catalog())
    def test_empty_selections_returns_empty_response(self, client: TestClient) -> None:
        resp = client.post("/portfolio/funds/derive-holdings", json={"selections": []})
        assert resp.status_code == 200
        assert resp.json() == {"holdings": [], "unmapped": []}
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd services/portfolio && python -m pytest tests/test_funds_routes.py -v`
Expected: FAIL with 404 (route doesn't exist yet)

- [ ] **Step 5: Write the route**

```python
# GET  /portfolio/funds/catalog          — company/category/track picker options
# POST /portfolio/funds/derive-holdings  — turn 3 fund selections into proxy holdings

import httpx
from fastapi import APIRouter, Body, Depends

from src.dependencies import get_market_data_client
from src.domain.funds import build_catalog_response, compute_derived_holdings
from src.domain.funds_catalog import FUND_CATALOG
from src.infrastructure.market_data_client import fetch_info_batch, prices_from_info
from src.schemas.funds_schemas import (
    CatalogResponse,
    DeriveHoldingsRequest,
    DeriveHoldingsResponse,
)

router = APIRouter(
    prefix="/portfolio/funds",
    tags=["funds"],
)


@router.get("/catalog")
async def get_catalog() -> CatalogResponse:
    return build_catalog_response(FUND_CATALOG)


@router.post("/derive-holdings")
async def post_derive_holdings(
    request: DeriveHoldingsRequest = Body(...),
    market_data_client: httpx.AsyncClient = Depends(get_market_data_client),
) -> DeriveHoldingsResponse:
    proxy_tickers = sorted(
        {
            row.proxy_ticker
            for entry in FUND_CATALOG
            for row in entry.rows
            if row.proxy_ticker is not None
        }
    )
    info_by_ticker = await fetch_info_batch(market_data_client, proxy_tickers)
    prices = prices_from_info(proxy_tickers, info_by_ticker)

    holdings, unmapped = compute_derived_holdings(request.selections, FUND_CATALOG, prices)
    return DeriveHoldingsResponse(holdings=holdings, unmapped=unmapped)
```

Note: `@patch("src.routes.funds.FUND_CATALOG", ...)` in the tests works because the route module imports `FUND_CATALOG` by name into its own namespace — patch targets that imported name, not the original module.

- [ ] **Step 6: Register the router in `main.py`**

In `services/portfolio/src/main.py`, add the import and registration:

```python
from .routes.funds import router as FundsRouter
from .routes.portfolio import router as PortfolioRouter
```

```python
app.include_router(PortfolioRouter)
app.include_router(FundsRouter)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd services/portfolio && python -m pytest tests/test_funds_routes.py tests/test_portfolio_routes.py -v`
Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add services/portfolio/src/infrastructure/market_data_client.py services/portfolio/src/routes/portfolio.py services/portfolio/src/routes/funds.py services/portfolio/src/main.py services/portfolio/tests/test_funds_routes.py
git commit -m "feat: add GET /portfolio/funds/catalog and POST /portfolio/funds/derive-holdings"
```

---

### Task 5: Frontend API client for funds

**Files:**
- Modify: `services/frontend/src/api/client.ts`

**Interfaces:**
- Produces: `FundRow`, `CatalogTrack`, `CatalogCompany`, `CatalogCategory`, `FundsCatalog`, `FundSelection`, `DerivedHoldingSource`, `DerivedHolding`, `UnmappedRow`, `DeriveHoldingsResult` (TS types), `getFundsCatalog()`, `deriveFundHoldings()` — consumed by Tasks 6-7.

- [ ] **Step 1: Add the types and API calls**

Append to `services/frontend/src/api/client.ts` (after the existing `Holding` interface, and after the existing API-call functions):

```ts
export interface FundRow {
  label: string;
  pct_of_fund: number;
  proxy_ticker: string | null;
}

export interface CatalogTrack {
  track_id: string;
  track_name: string;
  as_of_date: string;
}

export interface CatalogCompany {
  company_id: string;
  company_name: string;
  tracks: CatalogTrack[];
}

export interface CatalogCategory {
  category: string;
  companies: CatalogCompany[];
}

export interface FundsCatalog {
  categories: CatalogCategory[];
}

export interface FundSelection {
  category: string;
  company_id: string;
  track_id: string;
  amount_usd: number;
}

export interface DerivedHoldingSource {
  category: string;
  company_name: string;
  track_name: string;
}

export interface DerivedHolding {
  ticker: string;
  shares: number;
  source: DerivedHoldingSource;
}

export interface UnmappedRow {
  category: string;
  company_name: string;
  track_name: string;
  label: string;
  pct_of_fund: number;
}

export interface DeriveHoldingsResult {
  holdings: DerivedHolding[];
  unmapped: UnmappedRow[];
}

export async function getFundsCatalog(): Promise<FundsCatalog> {
  return fetchJson(`${BASE}/api/portfolio/funds/catalog`);
}

export async function deriveFundHoldings(selections: FundSelection[]): Promise<DeriveHoldingsResult> {
  return fetchJson(`${BASE}/api/portfolio/funds/derive-holdings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ selections }),
  });
}
```

- [ ] **Step 2: Type-check**

Run: `cd services/frontend && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add services/frontend/src/api/client.ts
git commit -m "feat: add funds catalog/derive-holdings API client functions"
```

---

### Task 6: FundsInput component

**Files:**
- Create: `services/frontend/src/components/FundsInput/FundsInput.tsx`

**Interfaces:**
- Consumes: `getFundsCatalog`, `FundsCatalog`, `UnmappedRow` (Task 5).
- Produces: `FundSlotState` (`{ companyId: string; trackId: string; amountUsd: string }`), `EMPTY_FUND_SLOT`, `FUND_CATEGORIES` (`["pension", "kupat_gemel_lehashkaa", "keren_hishtalmut"] as const`), default export `FundsInput` component — consumed by Task 7 (`App.tsx`).

- [ ] **Step 1: Write the component**

```tsx
import { useQuery } from "@tanstack/react-query";
import { getFundsCatalog } from "../../api/client";
import type { UnmappedRow } from "../../api/client";

export const FUND_CATEGORIES = ["pension", "kupat_gemel_lehashkaa", "keren_hishtalmut"] as const;
export type FundCategory = (typeof FUND_CATEGORIES)[number];

const CATEGORY_LABELS: Record<FundCategory, string> = {
  pension: "Pension",
  kupat_gemel_lehashkaa: "Kupat Gemel LeHashkaa",
  keren_hishtalmut: "Keren Hishtalmut",
};

export interface FundSlotState {
  companyId: string;
  trackId: string;
  amountUsd: string;
}

export const EMPTY_FUND_SLOT: FundSlotState = { companyId: "", trackId: "", amountUsd: "" };

interface Props {
  slots: Record<FundCategory, FundSlotState>;
  onChange: (category: FundCategory, slot: FundSlotState) => void;
  unmapped: UnmappedRow[];
}

export default function FundsInput({ slots, onChange, unmapped }: Props) {
  const { data: catalog } = useQuery({
    queryKey: ["fundsCatalog"],
    queryFn: getFundsCatalog,
    staleTime: Infinity,
  });

  return (
    <div className="space-y-4">
      {FUND_CATEGORIES.map((category) => {
        const categoryData = catalog?.categories.find((c) => c.category === category);
        const slot = slots[category];
        const company = categoryData?.companies.find((c) => c.company_id === slot.companyId);

        return (
          <div key={category} className="glass-card">
            <h3 className="section-title mb-3">{CATEGORY_LABELS[category]}</h3>
            <div className="flex flex-col gap-3 sm:flex-row">
              <select
                value={slot.companyId}
                onChange={(e) => onChange(category, { companyId: e.target.value, trackId: "", amountUsd: slot.amountUsd })}
                className="flex-1 rounded-xl bg-white/[0.03] border border-white/[0.04] px-4 py-2.5 text-sm text-slate-200 outline-none transition-all duration-200 focus:border-white/[0.08]"
              >
                <option value="">Select company</option>
                {categoryData?.companies.map((c) => (
                  <option key={c.company_id} value={c.company_id}>{c.company_name}</option>
                ))}
              </select>
              <select
                value={slot.trackId}
                disabled={!company}
                onChange={(e) => onChange(category, { ...slot, trackId: e.target.value })}
                className="flex-1 rounded-xl bg-white/[0.03] border border-white/[0.04] px-4 py-2.5 text-sm text-slate-200 outline-none transition-all duration-200 focus:border-white/[0.08] disabled:opacity-40"
              >
                <option value="">Select fund track</option>
                {company?.tracks.map((t) => (
                  <option key={t.track_id} value={t.track_id}>{t.track_name}</option>
                ))}
              </select>
              <input
                type="number"
                min={0}
                placeholder="Amount (USD)"
                value={slot.amountUsd}
                onChange={(e) => onChange(category, { ...slot, amountUsd: e.target.value })}
                className="w-full sm:w-40 rounded-xl bg-white/[0.03] border border-white/[0.04] px-4 py-2.5 text-sm text-slate-200 placeholder-slate-600 outline-none transition-all duration-200 focus:border-white/[0.08] font-mono"
              />
            </div>
          </div>
        );
      })}

      {unmapped.length > 0 && (
        <div className="rounded-xl border border-amber-500/20 bg-amber-950/10 px-4 py-2.5 text-xs text-slate-400">
          <span className="font-medium text-amber-300">Not counted toward stock holdings: </span>
          {unmapped.map((u, i) => (
            <span key={i}>
              {i > 0 && ", "}
              {(u.pct_of_fund * 100).toFixed(1)}% {u.label} ({u.company_name} - {u.track_name})
            </span>
          ))}
          {" "}- no tradeable proxy exists for these positions yet.
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd services/frontend && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add services/frontend/src/components/FundsInput/FundsInput.tsx
git commit -m "feat: add FundsInput component for the 3 savings-fund slots"
```

---

### Task 7: Wire funds into App.tsx (new tab, merged holdings)

**Files:**
- Modify: `services/frontend/src/App.tsx`

**Interfaces:**
- Consumes: `FundsInput`, `FUND_CATEGORIES`, `FundCategory`, `FundSlotState`, `EMPTY_FUND_SLOT` (Task 6); `deriveFundHoldings`, `FundSelection`, `UnmappedRow`, `Holding` (Task 5).
- Produces: `combinedHoldings: Holding[]` and `holdingsSources: Record<string, { manual: number; funds: { label: string; shares: number }[] }>` — consumed by Task 8 (`Holdings.tsx`). Every other tab (`Dashboard`, `Screener`, `Analysis`) now receives `combinedHoldings` instead of the renamed `manualHoldings`.

- [ ] **Step 1: Rename `holdings` state to `manualHoldings` and add fund state**

In `services/frontend/src/App.tsx`, replace lines 1-57 with:

```tsx
import { useState, useCallback, useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Holding, FundSelection, UnmappedRow } from "./api/client";
import { deriveFundHoldings } from "./api/client";
import PortfolioInput from "./components/PortfolioInput/PortfolioInput";
import FundsInput, { FUND_CATEGORIES, EMPTY_FUND_SLOT } from "./components/FundsInput/FundsInput";
import type { FundCategory, FundSlotState } from "./components/FundsInput/FundsInput";
import Holdings from "./pages/Holdings";
import Dashboard from "./pages/Dashboard";
import Analysis from "./pages/Analysis";
import Screener from "./pages/Screener";

const LS_KEY = "portfolio_saved";
const FUNDS_LS_KEY = "portfolio_fund_slots";

interface SavedState {
  holdings: Holding[];
}

function loadFromLocalStorage(): SavedState | null {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as SavedState;
  } catch {
    return null;
  }
}

function loadFundSlotsFromLocalStorage(): Record<FundCategory, FundSlotState> {
  const defaults = Object.fromEntries(FUND_CATEGORIES.map((c) => [c, EMPTY_FUND_SLOT])) as Record<FundCategory, FundSlotState>;
  try {
    const raw = localStorage.getItem(FUNDS_LS_KEY);
    if (!raw) return defaults;
    return { ...defaults, ...(JSON.parse(raw) as Record<FundCategory, FundSlotState>) };
  } catch {
    return defaults;
  }
}

type Tab = "holdings" | "dashboard" | "candidate" | "screener" | "savings";

function parseHoldingsFromUrl(): Holding[] {
  const h = new URLSearchParams(window.location.search).get("h");
  if (!h) return [];
  return h.split(",").flatMap((part) => {
    const [ticker, sharesStr] = part.split(":");
    const shares = parseFloat(sharesStr ?? "");
    if (!ticker || !isFinite(shares) || shares <= 0) return [];
    return [{ ticker: ticker.toUpperCase(), shares }];
  });
}

function parseTabFromUrl(): Tab {
  const t = new URLSearchParams(window.location.search).get("tab");
  const valid: Tab[] = ["holdings", "dashboard", "candidate", "screener", "savings"];
  return valid.includes(t as Tab) ? (t as Tab) : "holdings";
}

const TABS: { id: Tab; label: string; tooltip: string }[] = [
  { id: "holdings", label: "My Portfolio", tooltip: "View your current positions" },
  { id: "dashboard", label: "Analysis", tooltip: "Understand your portfolio" },
  { id: "screener", label: "Find a Stock", tooltip: "Find underpriced quality stocks" },
  { id: "candidate", label: "Test a Stock", tooltip: "Analyze how adding a specific stock would impact your portfolio" },
  { id: "savings", label: "Savings", tooltip: "Pension, Kupat Gemel LeHashkaa, and Keren Hishtalmut" },
];

export default function App() {
  const [manualHoldings, setManualHoldings] = useState<Holding[]>(() => {
    const fromUrl = parseHoldingsFromUrl();
    if (fromUrl.length > 0) return fromUrl;
    return loadFromLocalStorage()?.holdings ?? [];
  });
  const [fundSlots, setFundSlots] = useState<Record<FundCategory, FundSlotState>>(loadFundSlotsFromLocalStorage);
  const [activeTab, setActiveTab] = useState<Tab>(() => parseTabFromUrl());
```

- [ ] **Step 2: Persist fund slots and compute derived+combined holdings**

Immediately after the `useEffect` that syncs `holdings`/`activeTab` to the URL (originally lines 59-69, now referencing `manualHoldings`), add:

```tsx
  useEffect(() => {
    localStorage.setItem(FUNDS_LS_KEY, JSON.stringify(fundSlots));
  }, [fundSlots]);

  const fundSelections: FundSelection[] = useMemo(
    () =>
      FUND_CATEGORIES.flatMap((category) => {
        const slot = fundSlots[category];
        const amount = parseFloat(slot.amountUsd);
        if (!slot.companyId || !slot.trackId || !isFinite(amount) || amount <= 0) return [];
        return [{ category, company_id: slot.companyId, track_id: slot.trackId, amount_usd: amount }];
      }),
    [fundSlots],
  );

  const fundHoldingsQuery = useQuery({
    queryKey: ["fundHoldings", fundSelections],
    queryFn: () => deriveFundHoldings(fundSelections),
    enabled: fundSelections.length > 0,
    staleTime: 1000 * 60 * 5,
  });

  const derivedHoldings = fundSelections.length > 0 ? fundHoldingsQuery.data?.holdings ?? [] : [];
  const unmappedFundRows: UnmappedRow[] = fundSelections.length > 0 ? fundHoldingsQuery.data?.unmapped ?? [] : [];

  const combinedHoldings: Holding[] = useMemo(() => {
    const byTicker = new Map<string, number>();
    for (const h of manualHoldings) byTicker.set(h.ticker, (byTicker.get(h.ticker) ?? 0) + h.shares);
    for (const h of derivedHoldings) byTicker.set(h.ticker, (byTicker.get(h.ticker) ?? 0) + h.shares);
    return [...byTicker.entries()].map(([ticker, shares]) => ({ ticker, shares }));
  }, [manualHoldings, derivedHoldings]);

  const holdingsSources = useMemo(() => {
    const sources: Record<string, { manual: number; funds: { label: string; shares: number }[] }> = {};
    for (const h of manualHoldings) {
      sources[h.ticker] ??= { manual: 0, funds: [] };
      sources[h.ticker].manual += h.shares;
    }
    for (const h of derivedHoldings) {
      sources[h.ticker] ??= { manual: 0, funds: [] };
      sources[h.ticker].funds.push({ label: `${h.source.company_name} - ${h.source.track_name}`, shares: h.shares });
    }
    return sources;
  }, [manualHoldings, derivedHoldings]);
```

- [ ] **Step 3: Update the URL-sync effect and remaining references from `holdings` to `manualHoldings`**

Replace the existing URL-sync `useEffect` (previously lines 59-69) so it reads `manualHoldings` instead of `holdings`:

```tsx
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (manualHoldings.length === 0) {
      params.delete("h");
    } else {
      params.set("h", manualHoldings.map((h) => `${h.ticker}:${h.shares}`).join(","));
    }
    params.set("tab", activeTab);
    const qs = params.toString();
    window.history.replaceState({}, "", qs ? `?${qs}` : window.location.pathname);
  }, [manualHoldings, activeTab]);
```

Update `saveToLocalStorage` to persist `manualHoldings`:

```tsx
  function saveToLocalStorage() {
    const state: SavedState = { holdings: manualHoldings };
    localStorage.setItem(LS_KEY, JSON.stringify(state));
    setHasSaved(true);
  }
```

- [ ] **Step 4: Pass `combinedHoldings` to every existing tab, add the Savings tab content**

Update the render section (previously lines 148-227):

```tsx
        <PortfolioInput holdings={manualHoldings} onChange={setManualHoldings} />
```

```tsx
          {activeTab === "holdings" && <Holdings holdings={combinedHoldings} sources={holdingsSources} />}

          {activeTab === "dashboard" && <Dashboard holdings={combinedHoldings} />}

          {activeTab === "screener" && (
            <Screener onAnalyze={handleAnalyzeTicker} holdings={combinedHoldings} />
          )}

          {activeTab === "savings" && (
            <FundsInput
              slots={fundSlots}
              onChange={(category, slot) => setFundSlots((prev) => ({ ...prev, [category]: slot }))}
              unmapped={unmappedFundRows}
            />
          )}
```

And inside the `candidate` tab block, replace both `holdings={holdings}` usages with `holdings={combinedHoldings}`.

- [ ] **Step 5: Type-check**

Run: `cd services/frontend && npx tsc --noEmit`
Expected: errors only in `Holdings.tsx` about the new `sources` prop not existing yet — that's expected, Task 8 adds it. If there are any other errors (e.g. a leftover reference to the old `holdings` variable name), fix them now.

- [ ] **Step 6: Commit**

```bash
git add services/frontend/src/App.tsx
git commit -m "feat: add Savings tab and merge fund-derived holdings into the portfolio"
```

---

### Task 8: Show fund-source badge in Holdings table

**Files:**
- Modify: `services/frontend/src/pages/Holdings.tsx`

**Interfaces:**
- Consumes: `sources?: Record<string, { manual: number; funds: { label: string; shares: number }[] }>` (new optional prop, from Task 7).

- [ ] **Step 1: Add the `sources` prop and badge**

In `services/frontend/src/pages/Holdings.tsx`, update the `Props` interface (line 7-9):

```tsx
interface Props {
  holdings: Holding[];
  sources?: Record<string, { manual: number; funds: { label: string; shares: number }[] }>;
}
```

Update the function signature (line 116):

```tsx
export default function Holdings({ holdings, sources }: Props) {
```

In the ticker cell (inside the `<div className="flex items-center gap-1.5">` block around line 262-270), add a badge when the ticker has fund contributions:

```tsx
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono font-semibold text-slate-100">{r.ticker}</span>
                          {name && <span className="ml-1 hidden text-xs text-slate-500 sm:inline">{name}</span>}
                          {excludedTickers.has(r.ticker) && (
                            <span className="rounded px-1 py-0.5 text-[9px] font-semibold uppercase tracking-wide bg-amber-500/10 text-amber-400 border border-amber-500/20">
                              no data
                            </span>
                          )}
                          {sources?.[r.ticker]?.funds.length ? (
                            <span
                              className="rounded px-1 py-0.5 text-[9px] font-semibold uppercase tracking-wide bg-sky-500/10 text-sky-400 border border-sky-500/20"
                              title={sources[r.ticker].funds.map((f) => `${f.shares.toFixed(2)} via ${f.label}`).join(", ")}
                            >
                              via fund
                            </span>
                          ) : null}
                        </div>
```

- [ ] **Step 2: Type-check**

Run: `cd services/frontend && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add services/frontend/src/pages/Holdings.tsx
git commit -m "feat: badge fund-derived holdings in the positions table"
```

---

### Task 9: Resolve TASE proxy tickers for the unmapped Analyst rows

**Files:**
- Modify: `services/portfolio/src/domain/funds_catalog.py`

This task researches real, Yahoo-Finance-reachable TASE tickers (`.TA` suffix) for the three rows currently `proxy_ticker=None` in the Analyst entry: Israeli government bonds (Tel Gov Klali), Israeli-general corporate bonds, and the Makam 3-month cash sleeve. Each candidate ticker must be verified against the live market-data service before being added — a ticker existing on TASE doesn't guarantee Yahoo Finance carries price data for it.

- [ ] **Step 1: Search for candidate TASE ETFs**

Use WebSearch for each exposure, e.g. `site:tase.co.il OR site:migdal.co.il "תל גוב" ETF` for the government-bond index, `"מק"מ" ETF תעודת סל` for the money-market sleeve, and `"אג"ח קונצרני כללי" ETF` for the Israeli corporate-bond index. Collect 2-3 candidate TASE ticker symbols per exposure (these are typically numeric TASE security IDs, e.g. `1159250`, which map to Yahoo tickers like `TACHLIT.TA`-style names — confirm the exact Yahoo symbol via a search like `<candidate name> yahoo finance ticker`).

- [ ] **Step 2: Verify each candidate against the market-data service**

For each candidate Yahoo ticker, run (with the market-data service running locally, or via its deployed URL):

```bash
curl -s "http://localhost:8001/tickers/<CANDIDATE>.TA/info" | python -m json.tool | head -20
```

Expected: a JSON body containing a usable price field (`currentPrice`, `regularMarketPrice`, `navPrice`, or `previousClose`). If the request 404s or returns an empty/error body, discard that candidate and try the next one.

- [ ] **Step 3: Update the catalog with confirmed tickers**

For each of the 3 rows where Step 2 found a working ticker, edit `services/portfolio/src/domain/funds_catalog.py` and change that row's `proxy_ticker=None` to the confirmed ticker string. Leave any row `proxy_ticker=None` if no working Yahoo-reachable ticker was found after reasonable effort — it stays informational, per the design spec's fallback rule.

- [ ] **Step 4: Re-run the catalog and domain tests**

Run: `cd services/portfolio && python -m pytest tests/test_funds_domain.py tests/test_funds_routes.py -v`
Expected: all PASS (these tests use their own fixture catalogs, not `FUND_CATALOG`, so they're unaffected by which tickers got filled in — this just confirms nothing broke).

- [ ] **Step 5: Commit**

```bash
git add services/portfolio/src/domain/funds_catalog.py
git commit -m "feat: resolve TASE proxy tickers for Analyst gov/corp bond and cash sleeves"
```

---

## Follow-up work (not part of this plan)

Populating additional companies (Harel, Altshuler Shaham, Migdal) across all 3 categories and their fund tracks is ongoing data-entry work using the same `FundTrackEntry` pattern established in Task 2 — each new entry is a pure data addition to `funds_catalog.py`, requiring no code changes. This is intentionally left open-ended per the design spec's non-goals (no exhaustive day-one coverage) and should be done incrementally as fact sheets are sourced.
