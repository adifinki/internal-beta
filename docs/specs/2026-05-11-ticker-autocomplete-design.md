# Ticker Autocomplete Design

**Date:** 2026-05-11  
**Status:** Approved

## Problem

Users enter ticker symbols as free text. Yahoo Finance uses non-obvious symbols (e.g. `BRK-B` not `BRKB`), causing 400 errors from the correlation and analysis endpoints when price data cannot be fetched for the entered symbol.

## Solution

Debounced autocomplete dropdown on every ticker input. User types, sees top 5 Yahoo Finance search results, must pick from the list. Eliminates invalid symbol entry at the source.

---

## Architecture

### Backend — new search endpoint

**Service:** `market-data`  
**Route:** `GET /tickers/search?q=<query>&limit=5`  
**File:** `services/market-data/src/routes/tickers.py` (new route on existing router)

- Calls `yf.Search(query).quotes` (yfinance built-in, wraps Yahoo Finance search API)
- Returns top `limit` results (default 5, max 10)
- Response shape:

```json
[
  { "symbol": "BRK-B", "name": "Berkshire Hathaway Inc.", "exchange": "NYSE", "type": "EQUITY" },
  { "symbol": "BRKB.VI", "name": "Berkshire Hathaway Inc.", "exchange": "Vienna", "type": "EQUITY" }
]
```

- Redis-cached per normalized query string (lowercased, trimmed), TTL 5 minutes
- Cache key: `search:<query>:<limit>`
- Empty query or `len(q) < 2` returns `[]` immediately (no Yahoo call)
- If yfinance raises, returns `[]` (don't propagate search errors to UI)

**Nginx proxy:** already routes `/api/market-data/*` to market-data service — no nginx changes needed.

### Frontend — API client

**File:** `services/frontend/src/api/client.ts`

New function:

```ts
export interface TickerSearchResult {
  symbol: string;
  name: string;
  exchange: string;
  type: string;
}

export async function searchTickers(q: string, signal?: AbortSignal): Promise<TickerSearchResult[]> {
  const params = new URLSearchParams({ q, limit: "5" });
  return fetchJson(`${BASE}/api/market-data/tickers/search?${params}`, { signal });
}
```

### Frontend — search hook

**File:** `services/frontend/src/hooks/useTickerSearch.ts` (new file)

- Accepts `query: string`
- Debounces 300ms
- Skips fetch if `query.length < 2`
- Uses `AbortController` to cancel in-flight request when query changes
- Returns `{ results: TickerSearchResult[], loading: boolean }`
- On error: sets `results: []`, does not throw

```ts
export function useTickerSearch(query: string) {
  const [results, setResults] = useState<TickerSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  // debounce + AbortController logic
}
```

---

## Component Redesign — PortfolioInput

**File:** `services/frontend/src/components/PortfolioInput/PortfolioInput.tsx`

### Layout

```
┌─ Portfolio Holdings ─────────────────── [Edit ▼] ┐
│ [Search ticker…──────────────────] [Qty] [+]      │
│                                                    │
│  AAPL 29 ✕   MSFT 14 ✕   BRK-B 4 ✕  ...         │  ← expanded only
└────────────────────────────────────────────────────┘
```

**Collapsed state** (`expanded = false`):
- Header: `"Portfolio Holdings"` left, `"N holdings"` + `Hide ▲` button right
- No chips shown
- Input row visible

**Expanded state** (`expanded = true`, button label "Edit"):
- Header: `"Portfolio Holdings"` left, `Edit ▼` button right — no count
- Input row visible
- Editable chips shown below input row

**Zero holdings state:**
- No toggle button (nothing to collapse/expand)
- Input row visible, no chips

### Input row

Single flex row: `[search input flex-1] [qty input w-14] [+ button]`

The search input replaces the old 80px ticker input — it stretches to fill available space.

### Autocomplete dropdown

- Absolutely positioned below the search input, full width of that input
- `z-index` above chips
- Shows while `results.length > 0` and input is focused
- 5 rows max, single-line format: bold monospace symbol left, muted `"Name · Exchange"` right (Option A from visual review)
- First result highlighted by default
- Keyboard: `↑`/`↓` navigate, `Enter` selects highlighted, `Escape` closes and clears query
- Click selects
- On select: fills `ticker` state with chosen symbol, closes dropdown, focuses Qty input

### Interaction flow

1. User types in search input → debounce 300ms → fetch → dropdown appears
2. User picks result (click or Enter) → ticker locked in, Qty input focused
3. User enters qty → Enter or clicks `+` → `addHolding()` called → ticker + query cleared, search input re-focused
4. If user types a symbol that exactly matches a result and presses Tab → auto-selects first result, moves to Qty

### Validation

- `addHolding()` only callable when a ticker was selected from dropdown (not raw typed text)
- Duplicate ticker check unchanged
- Qty > 0 check unchanged

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Search API returns error | Dropdown hidden, no toast — silent fail |
| Search returns 0 results | Dropdown hidden |
| Network timeout on search | AbortController cancels, dropdown hidden |
| User types then immediately deletes | In-flight request cancelled via AbortController |

---

## Files Changed

| File | Change |
|---|---|
| `services/market-data/src/routes/tickers.py` | Add `GET /tickers/search` route |
| `services/market-data/src/infrastructure/redis_cache.py` | Add `get_search_cache_key()` helper |
| `services/frontend/src/api/client.ts` | Add `TickerSearchResult` type + `searchTickers()` |
| `services/frontend/src/hooks/useTickerSearch.ts` | New hook (debounce + abort) |
| `services/frontend/src/components/PortfolioInput/PortfolioInput.tsx` | Full redesign per layout above |

---

## Out of Scope

- Screener "Search ticker…" filter — that's a local filter on loaded data, not a symbol lookup
- Caching search results in the browser (Redis backend cache is sufficient)
- Showing price/market cap in dropdown rows
