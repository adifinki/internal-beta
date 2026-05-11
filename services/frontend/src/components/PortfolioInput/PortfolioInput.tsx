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
  const [expanded, setExpanded] = useState(true);
  const [activeIndex, setActiveIndex] = useState(0);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const searchRef = useRef<HTMLInputElement>(null);
  const qtyRef = useRef<HTMLInputElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const { results } = useTickerSearch(query);

  useEffect(() => {
    if (selectedTicker) return;
    if (results.length > 0) {
      setDropdownOpen(true);
      setActiveIndex(0);
    } else {
      setDropdownOpen(false);
    }
  }, [results, selectedTicker]);

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
    } else if (e.key === "Tab") {
      if (results[activeIndex]) {
        e.preventDefault();
        selectResult(results[activeIndex].symbol);
      }
    }
  }

  function handleQtyKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      addHolding();
    } else if (e.key === "Tab" && !e.shiftKey) {
      e.preventDefault();
      buttonRef.current?.focus();
    }
  }

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

      <div className="flex items-center gap-1.5">
        <div className="relative flex-1">
          <input
            ref={searchRef}
            autoFocus
            type="text"
            value={query}
            onChange={(e) => {
              const v = e.target.value.toUpperCase();
              setQuery(v);
              setSelectedTicker("");
            }}
            onKeyDown={handleSearchKeyDown}
            onFocus={() => {
              if (results.length > 0) {
                setDropdownOpen(true);
                setActiveIndex(0);
              }
            }}
            placeholder="Search ticker…"
            className="w-full rounded-lg border border-white/[0.06] bg-white/[0.03] px-2.5 py-1.5 text-xs text-slate-200 placeholder-slate-600 outline-none transition-colors focus:border-white/[0.1]"
          />

          {dropdownOpen && results.length > 0 && (
            <div
              ref={dropdownRef}
              className="absolute left-0 right-0 top-full z-50 mt-1 overflow-hidden rounded-lg border border-white/[0.1] bg-[#1a2030] shadow-xl"
            >
              {results.map((r, i) => (
                <button
                  key={r.symbol}
                  onMouseDown={(e) => {
                    e.preventDefault();
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

        <button
          ref={buttonRef}
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
