import { useRef, useState } from "react";
import type { Holding } from "../../api/client";

interface PortfolioInputProps {
  holdings: Holding[];
  onChange: (holdings: Holding[]) => void;
}

export default function PortfolioInput({ holdings, onChange }: PortfolioInputProps) {
  const [ticker, setTicker] = useState("");
  const [shares, setShares] = useState(0);
  const tickerRef = useRef<HTMLInputElement>(null);

  function addHolding() {
    const t = ticker.trim().toUpperCase();
    if (!t || shares <= 0) return;
    if (holdings.some((h) => h.ticker === t)) return;
    onChange([...holdings, { ticker: t, shares }]);
    setTicker("");
    setShares(0);
    tickerRef.current?.focus();
  }

  function removeHolding(t: string) {
    onChange(holdings.filter((h) => h.ticker !== t));
  }

  function updateShares(t: string, newShares: number) {
    if (newShares <= 0) return;
    onChange(holdings.map((h) => (h.ticker === t ? { ...h, shares: newShares } : h)));
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      addHolding();
    }
  }

  return (
    <div className="glass-card">
      <h2 className="section-title">Portfolio Holdings</h2>

      {/* Compact holdings list + add row in one block */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Existing holdings as compact pills */}
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
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
            </button>
          </div>
        ))}

        {/* Inline add */}
        <div className="flex items-center gap-1.5" onKeyDown={handleKey}>
          <input
            ref={tickerRef}
            autoFocus
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="Ticker"
            className="w-20 rounded-lg border border-white/[0.06] bg-white/[0.03] px-2.5 py-1.5 text-xs text-slate-200 placeholder-slate-600 outline-none transition-colors focus:border-white/[0.1]"
          />
          <input
            type="number"
            min={0}
            value={shares || ""}
            onChange={(e) => setShares(Number(e.target.value))}
            placeholder="Qty"
            className="w-14 rounded-lg border border-white/[0.06] bg-white/[0.03] px-2 py-1.5 text-center text-xs text-slate-200 placeholder-slate-600 outline-none transition-colors focus:border-white/[0.1] [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
          />
          <button
            onClick={addHolding}
            disabled={!ticker.trim() || shares <= 0}
            className="rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-1.5 text-xs text-slate-500 transition-colors hover:border-white/[0.1] hover:text-slate-200 disabled:opacity-30"
          >
            +
          </button>
        </div>
      </div>
    </div>
  );
}
