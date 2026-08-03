# Savings Funds Tab — Design

## Problem

Israeli users typically hold significant wealth in regulated savings vehicles — pension funds, Kupat Gemel LeHashkaa (investment-purpose provident funds), and Keren Hishtalmut (further-education funds) — managed by insurance/investment companies (Analyst, Harel, Altshuler Shaham, Migdal, etc). These accounts are invisible to the rest of the app: correlation, risk, concentration, and optimization all only see manually-entered stock tickers.

Users don't get to pick individual stocks inside these funds — they pick a company and a fund track (e.g. "General", "S&P 500 track"), and the company invests according to a disclosed asset-allocation policy (equities/bonds/cash split, further split across benchmark indices). We want the app to treat money in these accounts as part of the user's overall stock exposure, without requiring the user to guess what to type in manually.

## Goals

- Let the user pick a company + fund track for each of the 3 categories (Pension, Kupat Gemel LeHashkaa, Keren Hishtalmut) and enter a USD amount held in each.
- Translate each fund's disclosed allocation into real, tradeable proxy tickers with computed share counts.
- Merge those proxy holdings into the same holdings pipeline used everywhere else in the app (Holdings, Dashboard, Screener, Candidate Analysis) — no special-casing needed downstream.
- Be honest about the parts of a fund's allocation that have no good real-world proxy (e.g. non-tradeable Israeli-only instruments) instead of forcing a misleading mapping.

## Non-goals

- Exhaustive, day-one coverage of every company × category × track combination. Data population is best-effort and incremental — the catalog is just data, so more entries can be added later without code changes.
- Automatic PDF parsing. Fund allocation data is entered manually by us, sourced from company-published fact sheets.
- FX conversion. The user enters the USD-equivalent amount directly; no NIS→USD conversion is performed by the app.
- Persisting fund selections in the shareable URL. They live in `localStorage` only, alongside manually-entered holdings.

## Architecture

### Fund catalog (new static data)

A new module in the portfolio service holds a catalog of fund tracks:

```
Company (e.g. "Analyst", "Harel", "Altshuler Shaham", "Migdal")
  └─ Category ("pension" | "kupat_gemel_lehashkaa" | "keren_hishtalmut")
       └─ Track (e.g. "Klali" / "General", "S&P 500 track")
            └─ Rows: [{ label, pct_of_fund, proxy_ticker: str | null }]
```

`pct_of_fund` is precomputed at data-entry time by multiplying sleeve weight × benchmark sub-split (e.g. equities 47.46% × S&P 500 sub-weight 15% → ~7.1% of the whole fund maps to SPY). This keeps the runtime computation a single multiplication — no allocation-percentage math happens outside the catalog.

Each row's `proxy_ticker` is chosen using this priority, decided at data-entry time:

1. A real ETF already reachable through the existing yfinance-backed pipeline. For US/global exposures this is a well-known ETF (SPY for S&P 500, URTH for MSCI World, QQQ for Nasdaq, LQD for global corporate bonds, IEF/TLT for global government bonds by duration). For Israeli-only exposures (TA-125/TA-35 equities, Israeli government/corporate bonds, מק"מ cash) this is a TASE-listed ETF referenced with its Yahoo Finance `.TA` suffix, since Yahoo already carries many TASE securities — this needs no new infrastructure, only correct ticker identification per exposure.
2. If no such Yahoo-covered ETF exists for a given exposure, the TASE Maya public API (maya.tase.co.il) is investigated as a supplementary price source in a follow-up phase. This requires a small new adapter in market-data-service and is not required for the initial version.
3. If neither is available, `proxy_ticker` is `null` and the row is informational only — it is never force-mapped to a misleading proxy (e.g. cash never becomes an equity ETF).

MVP ships with one fully-populated entry, sourced from the "Analyst — Gemel LeHaskaa Klali" fact sheet provided:

| Row | % of fund | Proxy |
|---|---|---|
| Equities → TA-125 | 47.46% × 45% ≈ 21.4% | TASE equity ETF (`.TA`, TBD during implementation) |
| Equities → S&P 500 | 47.46% × 15% ≈ 7.1% | SPY |
| Equities → MSCI World | 47.46% × 40% ≈ 19.0% | URTH |
| Government bonds | 31.00% | TASE gov bond ETF (`.TA`) or unmapped |
| Corporate bonds → Israeli general | 23.59% × 75% ≈ 17.7% | TASE corp bond ETF (`.TA`) or unmapped |
| Corporate bonds → Global aggregate | 23.59% × 25% ≈ 5.9% | LQD |
| Cash (מק"מ 3-month) | 13.77% | TASE money-market ETF (`.TA`) or BIL |
| Other | 1.51% | unmapped |

As part of implementation, the same schema will be populated with additional entries researched from Analyst, Harel, Altshuler Shaham, and Migdal's public fund fact sheets, across all three categories and their available tracks (general, S&P 500-tracking, etc). This is incremental, ongoing work, not a blocking prerequisite for shipping the feature.

### Backend endpoints (portfolio service)

- `GET /portfolio/funds/catalog` — returns the nested company/category/track structure (names and IDs only, no computation) for populating the 3 dropdowns.
- `POST /portfolio/funds/derive-holdings` — body: up to 3 `{ category, company_id, track_id, amount_usd }` selections. For each selection, looks up the track's rows, computes `shares = amount_usd * pct_of_fund / current_price` for every row with a non-null proxy ticker (fetching prices via the existing market-data client), and returns:
  - `holdings: [{ ticker, shares, source: { category, company, track } }]`
  - `unmapped: [{ category, company, track, label, pct_of_fund }]` for rows with no proxy ticker (informational, never converted to shares).

### Frontend

- New "Savings" tab alongside the existing 4 tabs (Holdings, Analysis, Find a Stock, Test a Stock).
- New `FundsInput` component: 3 fixed slots (Pension / Kupat Gemel LeHashkaa / Keren Hishtalmut), each with a company select → track select (populated from `/portfolio/funds/catalog`, fetched once) → USD amount number input. Slots are independently optional.
- `unmapped` rows are shown in this tab as an informational note per selected fund (e.g. "14% Israeli government bonds — no tradeable proxy available, not counted toward stock holdings"), mirroring the existing amber "excluded tickers" treatment in the Holdings page.
- `App.tsx` state changes:
  - Existing `holdings` state is renamed `manualHoldings` (unchanged behavior: typed in by the user, persisted to `localStorage`/URL as today).
  - New `fundSelections` state (`FundSlot[]`, up to 3), persisted to `localStorage` only (not the URL).
  - A query calls `derive-holdings` whenever `fundSelections` changes, producing `fundHoldings`.
  - A `combinedHoldings` memo sums `manualHoldings` and `fundHoldings` by ticker; this is what gets passed to Holdings, Dashboard, Screener, and Candidate Analysis — none of those components need to change their props' shape.
  - A `holdingsSources: Record<ticker, { manual: number; funds: { label: string; shares: number }[] }>` map is computed alongside, consumed only by the Holdings table.
- `Holdings.tsx`: rows whose ticker has a non-empty `funds` breakdown get a small badge; hovering/expanding shows the manual-vs-fund split (e.g. "5 manual + 12 via Pension — Migdal, S&P 500 track").

## Data flow example

User selects Kupat Gemel LeHashkaa → Analyst → Gemel LeHaskaa Klali, enters $10,000.

1. Frontend calls `derive-holdings` with that selection.
2. Backend looks up the track's 8 rows, fetches current prices for SPY, URTH, and any resolved `.TA` tickers.
3. For the SPY row (7.1% of fund): `shares = 10000 * 0.071 / spy_price`.
4. Response includes that computed SPY holding tagged with `source = { category: "kupat_gemel_lehashkaa", company: "Analyst", track: "Gemel LeHaskaa Klali" }`, plus similar rows for URTH, LQD, and any resolved TASE ETFs, plus an `unmapped` entry for rows with no proxy (e.g. "Other 1.51%").
5. Frontend merges the SPY shares into `combinedHoldings["SPY"]` (summed with any manually-entered SPY shares), and the Holdings table shows the combined total with a badge indicating part of it comes from this fund.

## Testing

- Backend: unit tests in `services/portfolio/tests` for the derivation math (amount × pct / price → shares, per-row and aggregated across multiple selections), and for unmapped-row handling (never produces a holding).
- Frontend: manual verification that selecting a fund updates the Holdings table total and badges, and that it flows through to Dashboard/correlation results, without altering manually-entered holdings when a fund selection is cleared.

## Open questions for implementation phase

- Exact `.TA` ticker identification for TASE-listed ETFs tracking TA-125, Israeli government bonds, Israeli corporate bonds, and money-market instruments — to be resolved by looking up each company's actual bond/equity sub-holdings (not just the benchmark name) during data population.
- Whether the TASE Maya public API is usable as a supplementary price source for exposures Yahoo Finance doesn't cover — scoped as a follow-up, not blocking.
