# Ticker Autocomplete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add debounced Yahoo Finance ticker search autocomplete to PortfolioInput, eliminating invalid symbol entry.

**Architecture:** New `GET /tickers/search?q=&limit=5` endpoint in the market-data FastAPI service wraps `yf.Search()` with Redis caching (5 min TTL). The frontend `useTickerSearch` hook debounces 300ms + uses AbortController for cancellation. `PortfolioInput` is redesigned: full-width search input + qty + button in one row; dropdown anchors below; chips move below the row in expanded state; collapsed state shows count in header instead of chips.

**Tech Stack:** Python/FastAPI/yfinance/Redis (backend), React 19/TypeScript/Tailwind (frontend)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `services/market-data/src/infrastructure/redis_cache.py` | Modify | Add `SEARCH_TTL` constant + `get_search_cache_key()` |
| `services/market-data/src/infrastructure/yfinance_adapter.py` | Modify | Add `fetch_ticker_search()` async wrapper |
| `services/market-data/src/routes/tickers.py` | Modify | Add `GET /tickers/search` route |
| `services/market-data/tests/test_tickers_routes.py` | Modify | Add `TestSearchTickers` test class |
| `services/frontend/src/api/client.ts` | Modify | Add `TickerSearchResult` type + `searchTickers()` |
| `services/frontend/src/hooks/useTickerSearch.ts` | Create | Debounced search hook with AbortController |
| `services/frontend/src/components/PortfolioInput/PortfolioInput.tsx` | Modify | Full redesign per spec |

---

## Task 1: Redis search cache key

**Files:**
- Modify: `services/market-data/src/infrastructure/redis_cache.py`

- [ ] **Step 1: Add TTL constant and cache key helper**

Open `services/market-data/src/infrastructure/redis_cache.py`. Add after the existing TTL constants and add the new key function at the bottom:

```python
SEARCH_TTL = 300  # 5 minutes — search results change rarely
```

```python
def get_search_cache_key(q: str, limit: int) -> str:
    return f"search:{q.lower().strip()}:{limit}"
```

Final file after edits:

```python
# Cache-aside helper: get(key) / set(key, value, ttl)
# TTL: 24h

from typing import cast

from redis.asyncio import Redis

from src.models import Period

DEFAULT_TTL = 86400  # 24 hours — prices, info
FUNDAMENTALS_TTL = (
    604800  # 7 days — financials, balance sheet, cashflow (change quarterly)
)
INFO_TTL = 172800  # 48 hours — company info
SEARCH_TTL = 300  # 5 minutes — search results


async def cache_get(redis: Redis, key: str) -> str | None:
    return cast(str | None, await redis.get(key))


async def cache_set(redis: Redis, key: str, value: str, ttl: int = DEFAULT_TTL) -> None:
    await redis.set(key, value, ex=ttl)


def get_prices_cache_key(ticker: str, period: Period) -> str:
    return f"prices:{ticker}:{period}"


def get_info_cache_key(ticker: str) -> str:
    return f"info:{ticker}"


def get_financials_cache_key(ticker: str) -> str:
    return f"financials:{ticker}"


def get_balance_sheet_cache_key(ticker: str) -> str:
    return f"balance_sheet:{ticker}"


def get_cashflow_cache_key(ticker: str) -> str:
    return f"cashflow:{ticker}"


def get_quality_cache_key(ticker: str) -> str:
    return f"quality:{ticker}"


def get_search_cache_key(q: str, limit: int) -> str:
    return f"search:{q.lower().strip()}:{limit}"
```

- [ ] **Step 2: Commit**

```bash
git add services/market-data/src/infrastructure/redis_cache.py
git commit -m "feat: add search cache key helper"
```

---

## Task 2: yfinance search adapter

**Files:**
- Modify: `services/market-data/src/infrastructure/yfinance_adapter.py`

- [ ] **Step 1: Add `fetch_ticker_search` at the end of the file**

`yf.Search` is synchronous — wrap in `asyncio.to_thread`. Return `[]` on any exception so the route never surfaces yfinance errors to the UI.

Append to `services/market-data/src/infrastructure/yfinance_adapter.py`:

```python
async def fetch_ticker_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Search Yahoo Finance for tickers matching query.

    Returns a list of dicts with keys: symbol, name, exchange, type.
    Returns [] on any error — callers should treat empty as "no results".
    """
    def _search() -> list[dict[str, Any]]:
        results = yf.Search(query, max_results=max_results).quotes
        return [
            {
                "symbol": r.get("symbol", ""),
                "name": r.get("shortname") or r.get("longname") or "",
                "exchange": r.get("exchDisp", ""),
                "type": r.get("quoteType", ""),
            }
            for r in results
            if r.get("symbol")
        ]

    try:
        return await asyncio.to_thread(_search)
    except Exception as exc:
        logger.warning("Ticker search failed for query '%s': %s", query, exc)
        return []
```

- [ ] **Step 2: Commit**

```bash
git add services/market-data/src/infrastructure/yfinance_adapter.py
git commit -m "feat: add fetch_ticker_search yfinance adapter"
```

---

## Task 3: Backend route

**Files:**
- Modify: `services/market-data/src/routes/tickers.py`

- [ ] **Step 1: Add imports at top of tickers.py**

In `services/market-data/src/routes/tickers.py`, update the import from `yfinance_adapter`:

```python
from src.infrastructure.yfinance_adapter import (
    fetch_balance_sheet,
    fetch_cashflow,
    fetch_financials,
    fetch_prices_batch,
    fetch_ticker_info,
    fetch_ticker_search,
)
```

Also add to the `redis_cache` import:

```python
from src.infrastructure.redis_cache import (
    FUNDAMENTALS_TTL,
    INFO_TTL,
    SEARCH_TTL,
    cache_get,
    cache_set,
    get_balance_sheet_cache_key,
    get_cashflow_cache_key,
    get_financials_cache_key,
    get_info_cache_key,
    get_prices_cache_key,
    get_quality_cache_key,
    get_search_cache_key,
)
```

- [ ] **Step 2: Add the route handler at the end of the route handlers section (before the `/{ticker}/info` route to avoid path conflicts)**

Add after the `/returns` handler and before the `/{ticker}/info` handler:

```python
@router.get("/search")
async def search_tickers(
    q: str = Query(..., description="Search query (min 2 chars)"),
    limit: int = Query(5, ge=1, le=10, description="Max results to return"),
    redis: Redis = Depends(get_redis_client),
) -> list[dict[str, str]]:
    if len(q.strip()) < 2:
        return []

    cache_key = get_search_cache_key(q, limit)
    cached = await cache_get(redis, cache_key)
    if cached is not None:
        return cast(list[dict[str, str]], json.loads(cached))

    results = await fetch_ticker_search(q, max_results=limit)
    await cache_set(redis, cache_key, json.dumps(results), ttl=SEARCH_TTL)
    return results
```

**Important:** The `/search` route must be registered before `/{ticker}/info` and `/{ticker}/quality` in the file, otherwise FastAPI will try to match `"search"` as a ticker symbol. Since `tickers.py` uses `@router.get("/search")` and the wildcard routes use `@router.get("/{ticker}/...")`, order in the file matters — `/search` must come first.

- [ ] **Step 3: Commit**

```bash
git add services/market-data/src/routes/tickers.py
git commit -m "feat: add GET /tickers/search endpoint"
```

---

## Task 4: Backend tests

**Files:**
- Modify: `services/market-data/tests/test_tickers_routes.py`

- [ ] **Step 1: Write failing tests**

Add this class at the end of `services/market-data/tests/test_tickers_routes.py`:

```python
# ---------------------------------------------------------------------------
# GET /tickers/search
# ---------------------------------------------------------------------------


class TestSearchTickers:
    @patch("src.routes.tickers.fetch_ticker_search")
    def test_returns_results(self, mock_search: AsyncMock, client: TestClient) -> None:
        mock_search.return_value = [
            {"symbol": "BRK-B", "name": "Berkshire Hathaway Inc.", "exchange": "NYSE", "type": "EQUITY"},
            {"symbol": "BRKB.VI", "name": "Berkshire Hathaway Inc.", "exchange": "Vienna", "type": "EQUITY"},
        ]

        resp = client.get("/tickers/search", params={"q": "BRK", "limit": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["symbol"] == "BRK-B"
        assert data[0]["name"] == "Berkshire Hathaway Inc."
        assert data[0]["exchange"] == "NYSE"

    @patch("src.routes.tickers.fetch_ticker_search")
    def test_short_query_returns_empty_without_fetch(
        self, mock_search: AsyncMock, client: TestClient
    ) -> None:
        resp = client.get("/tickers/search", params={"q": "B"})
        assert resp.status_code == 200
        assert resp.json() == []
        mock_search.assert_not_called()

    @patch("src.routes.tickers.fetch_ticker_search")
    def test_uses_cache_on_second_call(
        self, mock_search: AsyncMock, client: TestClient
    ) -> None:
        mock_search.return_value = [
            {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ", "type": "EQUITY"}
        ]

        client.get("/tickers/search", params={"q": "AAPL", "limit": 5})
        # Verify cache_set was called
        app.state.redis.set.assert_awaited()

    @patch("src.routes.tickers.fetch_ticker_search")
    def test_missing_q_param_returns_422(
        self, mock_search: AsyncMock, client: TestClient
    ) -> None:
        resp = client.get("/tickers/search")
        assert resp.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd services/market-data
poetry run pytest tests/test_tickers_routes.py::TestSearchTickers -v
```

Expected: `FAILED` — `fetch_ticker_search` not yet imported in routes or route doesn't exist yet.

If Task 3 is already complete, these should pass. Move to Step 3.

- [ ] **Step 3: Run all market-data tests to verify nothing is broken**

```bash
cd services/market-data
poetry run pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add services/market-data/tests/test_tickers_routes.py
git commit -m "test: add TestSearchTickers route tests"
```

---

## Task 5: Frontend API client

**Files:**
- Modify: `services/frontend/src/api/client.ts`

- [ ] **Step 1: Add type and function**

In `services/frontend/src/api/client.ts`, add after the existing type definitions (after `ScreenerResult`):

```typescript
export interface TickerSearchResult {
  symbol: string;
  name: string;
  exchange: string;
  type: string;
}
```

Add at the end of the file:

```typescript
export async function searchTickers(q: string, signal?: AbortSignal): Promise<TickerSearchResult[]> {
  const params = new URLSearchParams({ q, limit: "5" });
  return fetchJson<TickerSearchResult[]>(`${BASE}/api/market-data/tickers/search?${params}`, { signal });
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd services/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add services/frontend/src/api/client.ts
git commit -m "feat: add searchTickers API function"
```

---

## Task 6: useTickerSearch hook

**Files:**
- Create: `services/frontend/src/hooks/useTickerSearch.ts`

- [ ] **Step 1: Create the hooks directory and hook file**

```bash
mkdir -p services/frontend/src/hooks
```

Create `services/frontend/src/hooks/useTickerSearch.ts`:

```typescript
import { useEffect, useRef, useState } from "react";
import { searchTickers, type TickerSearchResult } from "../api/client";

export function useTickerSearch(query: string) {
  const [results, setResults] = useState<TickerSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    // Clear previous timer
    if (timerRef.current) clearTimeout(timerRef.current);
    // Abort previous in-flight request
    if (abortRef.current) abortRef.current.abort();

    if (query.trim().length < 2) {
      setResults([]);
      setLoading(false);
      return;
    }

    setLoading(true);

    timerRef.current = setTimeout(async () => {
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const data = await searchTickers(query.trim(), controller.signal);
        setResults(data);
      } catch {
        // AbortError (user typed more) or network error — both are silent
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (abortRef.current) abortRef.current.abort();
    };
  }, [query]);

  return { results, loading };
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd services/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add services/frontend/src/hooks/useTickerSearch.ts
git commit -m "feat: add useTickerSearch debounced hook"
```

---

## Task 7: Redesign PortfolioInput

**Files:**
- Modify: `services/frontend/src/components/PortfolioInput/PortfolioInput.tsx`

- [ ] **Step 1: Replace the entire file**

Replace `services/frontend/src/components/PortfolioInput/PortfolioInput.tsx` with:

```typescript
import { useEffect, useRef, useState } from "react";
import type { Holding } from "../../api/client";
import { useTickerSearch } from "../../hooks/useTickerSearch";

interface PortfolioInputProps {
  holdings: Holding[];
  onChange: (holdings: Holding[]) => void;
}

export default function PortfolioInput({ holdings, onChange }: PortfolioInputProps) {
  const [query, setQuery] = useState("");
  const [selectedTicker, setSelectedTicker] = useState("");
  const [shares, setShares] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const searchRef = useRef<HTMLInputElement>(null);
  const qtyRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const { results } = useTickerSearch(query);

  // Open dropdown when results arrive; reset highlight
  useEffect(() => {
    if (results.length > 0) {
      setDropdownOpen(true);
      setActiveIndex(0);
    } else {
      setDropdownOpen(false);
    }
  }, [results]);

  function selectResult(symbol: string) {
    setSelectedTicker(symbol);
    setQuery(symbol);
    setDropdownOpen(false);
    qtyRef.current?.focus();
  }

  function addHolding() {
    const t = selectedTicker.trim();
    if (!t || shares <= 0) return;
    if (holdings.some((h) => h.ticker === t)) return;
    onChange([...holdings, { ticker: t, shares }]);
    setQuery("");
    setSelectedTicker("");
    setShares(0);
    searchRef.current?.focus();
  }

  function removeHolding(t: string) {
    onChange(holdings.filter((h) => h.ticker !== t));
  }

  function updateShares(t: string, newShares: number) {
    if (newShares <= 0) return;
    onChange(holdings.map((h) => (h.ticker === t ? { ...h, shares: newShares } : h)));
  }

  function handleSearchKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!dropdownOpen) {
      if (e.key === "Enter") {
        e.preventDefault();
        addHolding();
      }
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (results[activeIndex]) selectResult(results[activeIndex].symbol);
    } else if (e.key === "Escape") {
      setDropdownOpen(false);
      setQuery("");
      setSelectedTicker("");
    } else if (e.key === "Tab") {
      if (results[0]) {
        e.preventDefault();
        selectResult(results[0].symbol);
      }
    }
  }

  function handleQtyKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      addHolding();
    }
  }

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node) &&
        searchRef.current &&
        !searchRef.current.contains(e.target as Node)
      ) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const canAdd = !!selectedTicker && shares > 0 && !holdings.some((h) => h.ticker === selectedTicker);

  return (
    <div className="glass-card">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="section-title mb-0">Portfolio Holdings</h2>
        <div className="flex items-center gap-3">
          {!expanded && holdings.length > 0 && (
            <span className="text-[11px] text-slate-500">
              {holdings.length} holding{holdings.length !== 1 ? "s" : ""}
            </span>
          )}
          <span className="hidden text-[11px] text-slate-500 sm:inline">Min 2 tickers for analysis</span>
          {holdings.length > 0 && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="flex items-center gap-1 rounded-lg border border-white/[0.06] bg-white/[0.03] px-2.5 py-1 text-[11px] text-slate-500 transition-colors hover:text-slate-300"
            >
              {expanded ? "Hide" : "Edit"}
              <svg
                width="12"
                height="12"
                viewBox="0 0 12 12"
                fill="none"
                className={`transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
              >
                <path d="M3 4.5l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Expanded: editable chips below header, above input row */}
      {expanded && holdings.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {holdings.map((h) => (
            <div
              key={h.ticker}
              className="flex items-center gap-1 rounded-lg border border-white/[0.06] bg-white/[0.03] pl-3 pr-1 py-1"
            >
              <span className="font-mono text-xs font-semibold text-slate-200">{h.ticker}</span>
              <input
                type="number"
                min={1}
                value={h.shares}
                onChange={(e) => updateShares(h.ticker, Number(e.target.value))}
                className="w-10 bg-transparent text-center font-mono text-xs text-slate-300 outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
              />
              <button
                onClick={() => removeHolding(h.ticker)}
                className="rounded p-0.5 text-slate-600 transition-colors hover:text-red-400"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input row — always visible */}
      <div className="flex items-center gap-1.5">
        {/* Search input + dropdown wrapper */}
        <div className="relative flex-1">
          <input
            ref={searchRef}
            autoFocus
            type="text"
            value={query}
            onChange={(e) => {
              const v = e.target.value.toUpperCase();
              setQuery(v);
              setSelectedTicker(""); // clear confirmed selection when user edits
            }}
            onKeyDown={handleSearchKeyDown}
            onFocus={() => results.length > 0 && setDropdownOpen(true)}
            placeholder="Search ticker…"
            className="w-full rounded-lg border border-white/[0.06] bg-white/[0.03] px-2.5 py-1.5 text-xs text-slate-200 placeholder-slate-600 outline-none transition-colors focus:border-white/[0.1]"
          />

          {/* Autocomplete dropdown */}
          {dropdownOpen && results.length > 0 && (
            <div
              ref={dropdownRef}
              className="absolute left-0 right-0 top-full z-20 mt-1 overflow-hidden rounded-lg border border-white/[0.1] bg-[#1a2030] shadow-xl"
            >
              {results.map((r, i) => (
                <button
                  key={r.symbol}
                  onMouseDown={(e) => {
                    e.preventDefault(); // prevent input blur before click fires
                    selectResult(r.symbol);
                  }}
                  onMouseEnter={() => setActiveIndex(i)}
                  className={`flex w-full items-center justify-between px-3 py-1.5 text-left transition-colors ${
                    i === activeIndex ? "bg-white/[0.06]" : "hover:bg-white/[0.03]"
                  }`}
                >
                  <span className="font-mono text-xs font-bold text-slate-200">{r.symbol}</span>
                  <span className="ml-2 truncate text-[10px] text-slate-500">
                    {r.name} · {r.exchange}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Qty input */}
        <input
          ref={qtyRef}
          type="number"
          min={0}
          value={shares || ""}
          onChange={(e) => setShares(Number(e.target.value))}
          onKeyDown={handleQtyKeyDown}
          placeholder="Qty"
          className="w-14 rounded-lg border border-white/[0.06] bg-white/[0.03] px-2 py-1.5 text-center text-xs text-slate-200 placeholder-slate-600 outline-none transition-colors focus:border-white/[0.1] [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
        />

        {/* Add button */}
        <button
          onClick={addHolding}
          disabled={!canAdd}
          className="rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-1.5 text-xs text-slate-500 transition-colors hover:border-white/[0.1] hover:text-slate-200 disabled:opacity-30"
        >
          +
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd services/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Start dev server and test manually**

```bash
cd services/frontend
npm run dev
```

Open the app. Test the following:
1. Type "BRK" in the search field — dropdown shows BRK-B, BRK-A, etc. after ~300ms
2. Press ↓/↑ — highlight moves through results
3. Press Enter — selected ticker fills field, Qty input is focused
4. Enter a qty and press Enter — holding added, chips appear in expanded state
5. Click "Edit" — chips show below input row with editable qty and ✕ remove
6. Click "Hide" — chips hidden, "N holdings" count shown in header
7. Type 1 char — no dropdown (min 2 chars)
8. Type "BRKB" — BRK-B appears in dropdown (fixes the original bug)
9. Press Escape — dropdown closes, query cleared

- [ ] **Step 4: Commit**

```bash
git add services/frontend/src/components/PortfolioInput/PortfolioInput.tsx
git commit -m "feat: redesign PortfolioInput with ticker autocomplete"
```

---

## Task 8: Final integration check

- [ ] **Step 1: Run all backend tests**

```bash
cd services/market-data
poetry run pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 2: TypeScript check**

```bash
cd services/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Smoke test with docker-compose**

```bash
docker-compose -f docker-compose.dev.yml up --build
```

Open the app and add a holding with "BRKB" — confirm BRK-B appears in dropdown and can be added successfully. Verify the correlation endpoint no longer returns 400 for portfolios containing BRK-B.

- [ ] **Step 4: Final commit (if any cleanup needed)**

```bash
git add -A
git commit -m "feat: ticker autocomplete — complete"
```
