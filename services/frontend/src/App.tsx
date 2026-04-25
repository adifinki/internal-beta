import { useState, useCallback, useEffect } from "react";
import type { Holding } from "./api/client";
import PortfolioInput from "./components/PortfolioInput/PortfolioInput";
import Holdings from "./pages/Holdings";
import Dashboard from "./pages/Dashboard";
import Analysis from "./pages/Analysis";
import Screener from "./pages/Screener";

const LS_KEY = "portfolio_saved";

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

type Tab = "holdings" | "dashboard" | "candidate" | "screener";

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
  const valid: Tab[] = ["holdings", "dashboard", "candidate", "screener"];
  return valid.includes(t as Tab) ? (t as Tab) : "holdings";
}

const TABS: { id: Tab; label: string; tooltip: string }[] = [
  { id: "holdings", label: "My Portfolio", tooltip: "View your current positions" },
  { id: "dashboard", label: "Analysis", tooltip: "Understand your portfolio" },
  { id: "screener", label: "Find a Stock", tooltip: "Find underpriced quality stocks" },
  { id: "candidate", label: "Test a Stock", tooltip: "Analyze how adding a specific stock would impact your portfolio" },
];

export default function App() {
  const [holdings, setHoldings] = useState<Holding[]>(() => {
    const fromUrl = parseHoldingsFromUrl();
    if (fromUrl.length > 0) return fromUrl;
    return loadFromLocalStorage()?.holdings ?? [];
  });
  const [activeTab, setActiveTab] = useState<Tab>(() => parseTabFromUrl());

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (holdings.length === 0) {
      params.delete("h");
    } else {
      params.set("h", holdings.map((h) => `${h.ticker}:${h.shares}`).join(","));
    }
    params.set("tab", activeTab);
    const qs = params.toString();
    window.history.replaceState({}, "", qs ? `?${qs}` : window.location.pathname);
  }, [holdings, activeTab]);

  const [hasSaved, setHasSaved] = useState(() => localStorage.getItem(LS_KEY) !== null);
  const [candidateTicker, setCandidateTicker] = useState("");
  const [candidateShares, setCandidateShares] = useState<number | null>(null);

  function saveToLocalStorage() {
    const state: SavedState = { holdings };
    localStorage.setItem(LS_KEY, JSON.stringify(state));
    setHasSaved(true);
  }

  function deleteFromLocalStorage() {
    localStorage.removeItem(LS_KEY);
    setHasSaved(false);
  }

  function handleAnalyzeTicker(ticker: string) {
    setCandidateTicker(ticker);
    setCandidateShares(null);
    setActiveTab("candidate");
  }

  const handleOptimalComputed = useCallback(
    (shares: number) => { if (candidateShares === null) setCandidateShares(Math.max(1, Math.round(shares))); },
    [candidateShares]
  );

  return (
    <div className="min-h-screen bg-[#111318] text-slate-300">
      {/* Header */}
      <header className="border-b border-white/[0.03] px-4 py-4 flex items-center justify-between sm:px-8 sm:py-5">
        <h1 className="flex items-center gap-3">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="9.5" cy="12" r="6.5" stroke="rgba(148,163,184,0.2)" strokeWidth="1" />
            <circle cx="14.5" cy="12" r="6.5" stroke="rgba(148,163,184,0.45)" strokeWidth="1" />
          </svg>
          <span className="text-[15px] font-normal tracking-wide text-slate-500">
            internal<span className="ml-1 font-medium text-slate-300">beta</span>
          </span>
        </h1>
        <div className="flex items-center gap-2">
          {/* Save button */}
          <div className="relative group">
            <button
              onClick={saveToLocalStorage}
              className="flex items-center gap-1.5 rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-1.5 text-xs text-slate-500 transition-colors hover:border-white/[0.1] hover:text-slate-200"
            >
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                <path d="M2 2h7l2 2v7a1 1 0 01-1 1H2a1 1 0 01-1-1V3a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
                <rect x="4" y="8" width="5" height="3" rx="0.5" stroke="currentColor" strokeWidth="1.2"/>
                <rect x="4" y="2" width="4" height="3" rx="0.5" stroke="currentColor" strokeWidth="1.2"/>
              </svg>
              Save
            </button>
            <div className="pointer-events-none absolute right-0 top-full mt-2 w-52 rounded-lg bg-[#1a1d24] border border-white/[0.08] px-3 py-2 text-[11px] leading-relaxed text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-50">
              Saves your current portfolio holdings to this browser's local storage so they load automatically next visit.
            </div>
          </div>
          {/* Delete from local storage button */}
          {hasSaved && (
            <div className="relative group">
              <button
                onClick={deleteFromLocalStorage}
                className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-1.5 text-slate-600 transition-colors hover:border-red-400/20 hover:text-red-400"
              >
                <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                  <path d="M2 3.5h9M5 3.5V2.5a.5.5 0 01.5-.5h2a.5.5 0 01.5.5v1M3.5 3.5l.5 7h5l.5-7" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
              <div className="pointer-events-none absolute right-0 top-full mt-2 w-52 rounded-lg bg-[#1a1d24] border border-white/[0.08] px-3 py-2 text-[11px] leading-relaxed text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-50">
                Removes your saved portfolio from local storage. The current session is not affected.
              </div>
            </div>
          )}
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-8 sm:py-8">
        {/* Portfolio Input */}
        <PortfolioInput holdings={holdings} onChange={setHoldings} />

        {/* Tab bar */}
        <div className="mt-8 overflow-x-auto">
          <div className="flex gap-1 rounded-2xl bg-white/[0.02] p-1 w-fit mx-auto min-w-max">
            {TABS.map((tab) => (
              <div key={tab.id} className="relative group">
                <button
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-5 py-2 text-xs font-medium transition-all duration-300 ${
                    activeTab === tab.id
                      ? "rounded-xl bg-white/[0.06] text-slate-200"
                      : "rounded-xl text-slate-600 hover:text-slate-400"
                  }`}
                >
                  {tab.label}
                </button>
                <div className="pointer-events-none absolute left-1/2 -translate-x-1/2 top-full mt-2 w-56 rounded-lg bg-[#1a1d24] border border-white/[0.08] px-3 py-2 text-[11px] leading-relaxed text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-50">
                  {tab.tooltip}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Tab content */}
        <div className="mt-8 fade-in">
          {activeTab === "holdings" && <Holdings holdings={holdings} />}

          {activeTab === "dashboard" && <Dashboard holdings={holdings} />}

          {activeTab === "screener" && (
            <Screener onAnalyze={handleAnalyzeTicker} holdings={holdings} />
          )}

          {activeTab === "candidate" && (
            <div className="space-y-6">
              {/* Candidate input */}
              <div className="glass-card">
                <h2 className="section-title">Evaluate a Stock</h2>
                <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
                  <div className="flex-1">
                    <label className="metric-label mb-1.5 block">Ticker</label>
                    <input
                      type="text"
                      value={candidateTicker}
                      onChange={(e) => { setCandidateTicker(e.target.value.toUpperCase()); setCandidateShares(null); }}
                      placeholder="GOOGL"
                      className="w-full rounded-xl bg-white/[0.03] border border-white/[0.04] px-4 py-2.5 text-sm text-slate-200 placeholder-slate-600 outline-none transition-all duration-200 focus:border-white/[0.08]"
                    />
                  </div>
                  <div className="w-full sm:w-36">
                    <label className="metric-label mb-1.5 block">Shares to Add</label>
                    <input
                      type="number"
                      min={0}
                      step={1}
                      value={candidateShares ?? ""}
                      onChange={(e) => {
                        const v = parseInt(e.target.value);
                        setCandidateShares(isNaN(v) || v <= 0 ? null : v);
                      }}
                      placeholder="auto"
                      className="w-full rounded-xl bg-white/[0.03] border border-white/[0.04] px-4 py-2.5 text-sm text-slate-200 placeholder-slate-600 outline-none transition-all duration-200 focus:border-white/[0.08] font-mono"
                    />
                  </div>
                </div>
              </div>

              {/* Analysis results */}
              <Analysis
                holdings={holdings}
                candidateTicker={candidateTicker}
                sharesOverride={candidateShares}
                onOptimalComputed={handleOptimalComputed}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
