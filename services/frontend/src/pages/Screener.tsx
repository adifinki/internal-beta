import { Fragment, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getTickerInfo, getBatchBeta } from "../api/client";
import type { Holding, ScreenerResult } from "../api/client";
import InfoTooltip from "../components/InfoTooltip";
import { fmtDollar, fmtMultiple, fmtNum, fmtPct } from "../utils/format";
import { useScreener } from "../contexts/ScreenerContext";

type SortKey = keyof Pick<
  ScreenerResult,
  "cheap_quality_score" | "quality_score" | "garp_score" | "forward_pe" | "peg_ratio"
> | "internal_beta" | "portfolio_fit";

interface Props {
  onAnalyze: (ticker: string) => void;
  holdings: Holding[];
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function ScoreBar({ value }: { value: number }) {
  const color = value >= 70 ? "bg-emerald-700" : value >= 40 ? "bg-amber-700" : "bg-red-800";
  return (
    <div className="flex items-center justify-end gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-700">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${value}%` }} />
      </div>
      <span className="w-8 text-right font-mono text-xs">{value.toFixed(0)}</span>
    </div>
  );
}

function n(v: unknown): number | null {
  if (v == null) return null;
  const x = Number(v);
  return isFinite(x) ? x : null;
}

function computePortfolioFit(quality: number, garp: number, internalBeta: number | undefined): number {
  const beta = internalBeta ?? 1;
  const qScore = quality >= 80 ? 40 : quality >= 65 ? 32 : quality >= 50 ? 20 : quality >= 35 ? 10 : 0;
  const gScore = garp >= 75 ? 30 : garp >= 60 ? 24 : garp >= 45 ? 15 : garp >= 30 ? 7 : 0;
  const dScore = beta < 0 ? 30 : beta < 0.3 ? 28 : beta < 0.5 ? 22 : beta < 0.7 ? 16 : beta < 0.9 ? 10 : beta < 1.1 ? 5 : 0;
  return qScore + gScore + dScore;
}

// ─── Detail panel ────────────────────────────────────────────────────────────

function StatGroup({ title, stats }: { title: string; stats: { label: string; value: string }[] }) {
  return (
    <div>
      <div className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
        {title}
      </div>
      <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
        {stats.map(({ label, value }) => (
          <div key={label} className="rounded-lg bg-white/[0.05] px-3 py-2">
            <div className="text-xs text-slate-500">{label}</div>
            <div className="mt-0.5 font-mono text-sm text-slate-200">{value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TickerDetail({ ticker, onAnalyze }: { ticker: string; onAnalyze: (t: string) => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ["tickerInfo", ticker],
    queryFn: () => getTickerInfo(ticker),
    staleTime: 1000 * 60 * 60,
  });

  if (isLoading) {
    return (
      <td colSpan={99} className="px-4 py-4 text-xs text-slate-400">
        Loading {ticker}…
      </td>
    );
  }

  if (!data) return null;

  const name = (data.shortName ?? data.longName ?? ticker) as string;
  const summary = data.longBusinessSummary as string | undefined;

  return (
    <td colSpan={99} className="p-0">
      <div className="px-4 pb-5 pt-4" style={{ maxWidth: 0, minWidth: "100%" }}>
        <div className="mb-3 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <span className="text-sm font-semibold text-slate-100">{name}</span>
            {data.industry != null ? (
              <span className="ml-2 text-xs text-slate-500">{String(data.industry)}</span>
            ) : null}
            {summary && (
              <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-slate-400">{summary}</p>
            )}
          </div>
          <button
            className="shrink-0 rounded-md bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-blue-500"
            onClick={() => onAnalyze(ticker)}
          >
            Analyze as candidate →
          </button>
        </div>

        <div className="space-y-3">
          <StatGroup
            title="Price & Market"
            stats={[
              { label: "Price", value: fmtDollar(n(data.currentPrice ?? data.regularMarketPrice)) },
              { label: "Market Cap", value: fmtDollar(n(data.marketCap)) },
              { label: "52w Low", value: fmtDollar(n(data.fiftyTwoWeekLow)) },
              { label: "52w High", value: fmtDollar(n(data.fiftyTwoWeekHigh)) },
            ]}
          />
          <StatGroup
            title="Valuation"
            stats={[
              { label: "Trailing P/E", value: fmtNum(n(data.trailingPE)) },
              { label: "Forward P/E", value: fmtNum(n(data.forwardPE)) },
              { label: "P/B", value: fmtMultiple(n(data.priceToBook)) },
              { label: "PEG", value: fmtNum(n(data.pegRatio)) },
            ]}
          />
          <StatGroup
            title="Growth"
            stats={[
              { label: "Revenue Growth", value: fmtPct(n(data.revenueGrowth)) },
              { label: "Earnings Growth", value: fmtPct(n(data.earningsGrowth)) },
              { label: "EPS (TTM)", value: fmtNum(n(data.trailingEps)) },
              { label: "EPS (Fwd)", value: fmtNum(n(data.forwardEps)) },
            ]}
          />
          <StatGroup
            title="Profitability & Health"
            stats={[
              { label: "ROE", value: fmtPct(n(data.returnOnEquity)) },
              { label: "Net Margin", value: fmtPct(n(data.profitMargins)) },
              { label: "Debt / Equity", value: fmtNum(n(data.debtToEquity)) },
              { label: "Div Yield", value: fmtPct(n(data.dividendYield)) },
            ]}
          />
        </div>
      </div>
    </td>
  );
}

// ─── Main component ──────────────────────────────────────────────────────────

const TOOLTIP_KEYS: Partial<Record<SortKey, string>> = {
  cheap_quality_score: "cheap_quality",
  quality_score: "quality_section",
  garp_score: "garp_section",
  forward_pe: "forward_pe",
  peg_ratio: "peg_ratio",
  internal_beta: "internal_beta",
  portfolio_fit: "portfolio_fit",
};

export default function Screener({ onAnalyze, holdings }: Props) {
  const screener = useScreener();
  const [sortKey, setSortKey] = useState<SortKey>("garp_score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [search, setSearch] = useState("");
  const [sectorFilter, setSectorFilter] = useState("All");
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);

  // Start the screener fetch when user visits this tab
  useEffect(() => {
    screener.start();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const hasPortfolio = holdings.length >= 1;
  const screenerTickers = (screener.data ?? []).map((r) => r.ticker);
  const betaQuery = useQuery({
    queryKey: ["batchBeta", holdings, screenerTickers],
    queryFn: () => getBatchBeta(holdings, screenerTickers),
    enabled: hasPortfolio && screenerTickers.length > 0,
    staleTime: 1000 * 60 * 5,
  });
  const betaMap = betaQuery.data ?? {};

  const portfolioFitMap = useMemo(() => {
    if (!hasPortfolio) return {} as Record<string, number>;
    return Object.fromEntries(
      (screener.data ?? []).map((r) => [
        r.ticker,
        computePortfolioFit(r.quality_score, r.garp_score, betaMap[r.ticker]?.internal_beta),
      ]),
    );
  }, [screener.data, betaMap, hasPortfolio]);

  const sectors = ["All", ...Array.from(new Set((screener.data ?? []).map((r) => r.sector ?? "Unknown"))).sort()];

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else { setSortKey(key); setSortDir(key === "internal_beta" ? "asc" : "desc"); }
  }

  const filtered = [...(screener.data ?? [])]
    .filter((r) => {
      const matchSearch = r.ticker.includes(search.toUpperCase());
      const matchSector = sectorFilter === "All" || r.sector === sectorFilter;
      return matchSearch && matchSector;
    })
    .sort((a, b) => {
      if (sortKey === "internal_beta") {
        const av = betaMap[a.ticker]?.internal_beta ?? (sortDir === "asc" ? Infinity : -Infinity);
        const bv = betaMap[b.ticker]?.internal_beta ?? (sortDir === "asc" ? Infinity : -Infinity);
        return sortDir === "asc" ? av - bv : bv - av;
      }
      if (sortKey === "portfolio_fit") {
        const av = portfolioFitMap[a.ticker] ?? (sortDir === "desc" ? -Infinity : Infinity);
        const bv = portfolioFitMap[b.ticker] ?? (sortDir === "desc" ? -Infinity : Infinity);
        return sortDir === "desc" ? bv - av : av - bv;
      }
      const av = a[sortKey] ?? (sortDir === "desc" ? -Infinity : Infinity);
      const bv = b[sortKey] ?? (sortDir === "desc" ? -Infinity : Infinity);
      return sortDir === "desc" ? (bv as number) - (av as number) : (av as number) - (bv as number);
    });

  function SortHeader({ label, col }: { label: string; col: SortKey }) {
    const active = sortKey === col;
    const tooltipKey = TOOLTIP_KEYS[col];
    return (
      <th className="pb-2 text-right font-medium">
        <span
          className="cursor-pointer select-none hover:text-slate-200"
          onClick={() => toggleSort(col)}
        >
          {label}
          <span className="ml-1 text-slate-500">
            {active ? (sortDir === "desc" ? "↓" : "↑") : "↕"}
          </span>
        </span>
        {tooltipKey && <InfoTooltip metricKey={tooltipKey} />}
      </th>
    );
  }

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value.toUpperCase())}
          placeholder="Search ticker..."
          className="w-40 rounded-xl bg-white/[0.03] border border-white/[0.04] px-4 py-2 text-sm text-slate-200 placeholder-slate-600 outline-none transition-all duration-200 focus:border-white/[0.08]"
        />

        <select
          value={sectorFilter}
          onChange={(e) => setSectorFilter(e.target.value)}
          className="rounded-xl bg-white/[0.03] border border-white/[0.04] px-4 py-2 text-sm text-slate-400 outline-none transition-all duration-200 focus:border-white/[0.08]"
        >
          {sectors.map((s) => <option key={s}>{s}</option>)}
        </select>

        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-600">Min quality</span>
          <input
            type="number"
            min={0}
            max={100}
            value={screener.minQuality}
            onChange={(e) => screener.setMinQuality(Number(e.target.value))}
            className="w-16 rounded-xl bg-white/[0.03] border border-white/[0.04] px-3 py-2 text-sm text-slate-200 outline-none transition-all duration-200 focus:border-white/[0.08] text-center font-mono"
          />
        </div>
      </div>

      {/* Table */}
      <div className="glass-card">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="section-title">
            Cheap Quality Stocks
            <InfoTooltip metricKey="cheap_quality_screener" />
          </h2>
          <div className="flex items-center gap-3">
            {screener.data && (
              <span className="text-xs text-slate-500">
                {filtered.length} of {screener.data.length} results
              </span>
            )}
            {filtered.length > 0 && (
              <button
                onClick={() => {
                  const headers = ["Ticker", "Sector", "Cheap Quality", "Quality", "GARP", "Fwd P/E", "PEG",
                    ...(hasPortfolio ? ["Int. Beta", "Portfolio Fit"] : [])];
                  const rows = filtered.map((r) => [
                    r.ticker, r.sector ?? "", r.cheap_quality_score, r.quality_score, r.garp_score,
                    r.forward_pe ?? "", r.peg_ratio ?? "",
                    ...(hasPortfolio ? [betaMap[r.ticker]?.internal_beta ?? "", portfolioFitMap[r.ticker] ?? ""] : []),
                  ]);
                  const csv = [headers, ...rows].map((row) => row.join(",")).join("\n");
                  const a = Object.assign(document.createElement("a"), {
                    href: URL.createObjectURL(new Blob([csv], { type: "text/csv" })),
                    download: "screener.csv",
                  });
                  a.click();
                  URL.revokeObjectURL(a.href);
                }}
                className="rounded-lg border border-white/[0.06] bg-white/[0.03] px-2.5 py-1 text-[11px] text-slate-500 transition-colors hover:text-slate-300"
              >
                ↓ CSV
              </button>
            )}
          </div>
        </div>

        {(screener.isLoading || screener.progress) && (
          <div className="flex h-56 flex-col items-center justify-center gap-4">
            <div className="w-64">
              <div className="mb-3 text-center text-xs text-slate-500">
                This is a complex analysis that can take a few minutes.
              </div>
              <div className="mb-2 flex items-center justify-between text-xs text-slate-500">
                <span>
                  {screener.progress?.phase === "info" ? "Fetching ticker info…" :
                   screener.progress?.phase === "quality" ? "Scoring fundamentals…" :
                   screener.progress?.phase === "done" ? "Done" : "Loading…"}
                </span>
                <span className="font-mono">{screener.progress?.pct ?? 0}%</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
                <div
                  className="h-full rounded-full bg-blue-500/60 transition-all duration-500 ease-out"
                  style={{ width: `${screener.progress?.pct ?? 0}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {screener.error && (
          <div className="flex h-48 items-center justify-center text-sm text-red-400">
            Failed to load screener results.
          </div>
        )}

        {screener.data && filtered.length === 0 && (
          <div className="flex h-48 items-center justify-center text-sm text-slate-500">
            No results: adjust your filters.
          </div>
        )}

        {screener.data && filtered.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-white/[0.06] text-[10px] font-medium tracking-wider text-slate-500">
                  <th className="w-6 pb-2" />
                  <th className="pb-2 text-left font-medium">Ticker</th>
                  <th className="pb-2 text-left font-medium">Sector</th>
                  <SortHeader label="Cheap Quality" col="cheap_quality_score" />
                  <SortHeader label="Quality" col="quality_score" />
                  <SortHeader label="GARP" col="garp_score" />
                  <SortHeader label="Fwd P/E" col="forward_pe" />
                  <SortHeader label="PEG" col="peg_ratio" />
                  {hasPortfolio && <SortHeader label="Int. Beta" col="internal_beta" />}
                  {hasPortfolio && <SortHeader label="Portfolio Fit" col="portfolio_fit" />}
                  <th className="w-[10%] pb-2" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => {
                  const isExpanded = expandedTicker === row.ticker;
                  return (
                    <Fragment key={row.ticker}>
                      <tr
                        className={`cursor-pointer border-b border-white/[0.04] transition-colors hover:bg-white/[0.03] ${
                          isExpanded ? "bg-white/[0.03]" : ""
                        }`}
                        onClick={() => setExpandedTicker(isExpanded ? null : row.ticker)}
                      >
                        <td className="py-2.5 pl-1 text-slate-500">
                          <span
                            className="inline-block transition-transform duration-150"
                            style={{ transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)" }}
                          >
                            ›
                          </span>
                        </td>
                        <td className="py-2.5 font-mono font-semibold text-slate-100">
                          {row.ticker}
                          {row.quality_score >= 70 && row.garp_score >= 65 && (
                            <span
                              className="ml-1 text-[10px] text-amber-400 cursor-default"
                              title="Buffett-grade: quality ≥70, GARP ≥65 — high-quality business at a reasonable price."
                            >★</span>
                          )}
                        </td>
                        <td className="py-2.5 text-slate-400">{row.sector ?? "—"}</td>
                        <td className="py-2.5"><ScoreBar value={row.cheap_quality_score} /></td>
                        <td className="py-2.5"><ScoreBar value={row.quality_score} /></td>
                        <td className="py-2.5"><ScoreBar value={row.garp_score} /></td>
                        <td className="py-2.5 text-right font-mono text-slate-300">
                          {row.forward_pe != null ? row.forward_pe.toFixed(1) : "—"}
                        </td>
                        <td className="py-2.5 text-right font-mono text-slate-300">
                          {row.peg_ratio != null ? row.peg_ratio.toFixed(2) : "—"}
                        </td>
                        {hasPortfolio && (() => {
                          const b = betaMap[row.ticker]?.internal_beta;
                          if (b == null) return <td className="py-2.5 text-right font-mono text-slate-500">—</td>;
                          const color = b < 0 ? "text-green-400" : b < 0.5 ? "text-green-400" : b < 0.8 ? "text-blue-400" : b < 1.2 ? "text-slate-300" : "text-red-400";
                          return <td className={`py-2.5 text-right font-mono font-semibold ${color}`}>{b.toFixed(2)}</td>;
                        })()}
                        {hasPortfolio && (
                          <td className="py-2.5">
                            {portfolioFitMap[row.ticker] != null
                              ? <ScoreBar value={portfolioFitMap[row.ticker]} />
                              : <span className="text-right font-mono text-slate-500">—</span>}
                          </td>
                        )}
                        <td className="py-2.5 text-right">
                          <button
                            className="rounded-lg bg-blue-500/10 border border-blue-500/20 px-2 py-0.5 text-xs text-blue-400 hover:bg-blue-500/20"
                            onClick={(e) => { e.stopPropagation(); onAnalyze(row.ticker); }}
                          >
                            Analyze →
                          </button>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className="border-b border-white/[0.04] bg-white/[0.02]">
                          <TickerDetail ticker={row.ticker} onAnalyze={onAnalyze} />
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
