import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Holding } from "../../api/client";
import { getSectorImpact } from "../../api/client";
import { fmtDollar, fmtPct } from "../../utils/format";
import InfoTooltip from "../InfoTooltip";

interface FactorOption {
  label: string;
  value: string;
  group: "sector" | "macro";
}

const FACTORS: FactorOption[] = [
  // Sectors
  { label: "Technology", value: "Technology", group: "sector" },
  { label: "Healthcare", value: "Healthcare", group: "sector" },
  { label: "Financials", value: "Financials", group: "sector" },
  { label: "Energy", value: "Energy", group: "sector" },
  { label: "Consumer Disc.", value: "Consumer Discretionary", group: "sector" },
  { label: "Consumer Staples", value: "Consumer Staples", group: "sector" },
  { label: "Industrials", value: "Industrials", group: "sector" },
  { label: "Utilities", value: "Utilities", group: "sector" },
  { label: "Comm. Services", value: "Communication Services", group: "sector" },
  { label: "Real Estate", value: "Real Estate", group: "sector" },
  { label: "Materials", value: "Materials", group: "sector" },
  // Macro
  { label: "Interest Rates", value: "Interest Rates", group: "macro" },
  { label: "US Dollar", value: "US Dollar", group: "macro" },
  { label: "Gold", value: "Gold", group: "macro" },
];

// TLT has ~17yr duration: +100bps ≈ -17% TLT price move
const RATE_DURATION = 17;

interface Preset { label: string; move: number }

const SECTOR_PRESETS: Preset[] = [
  { label: "-30%", move: -0.30 },
  { label: "-20%", move: -0.20 },
  { label: "-10%", move: -0.10 },
  { label: "+10%", move: 0.10 },
  { label: "+20%", move: 0.20 },
];

// Rate presets: user thinks in bps, we convert to TLT % move (inverted)
const RATE_PRESETS: Preset[] = [
  { label: "+200bp", move: -200 },
  { label: "+100bp", move: -100 },
  { label: "+50bp", move: -50 },
  { label: "-50bp", move: 50 },
  { label: "-100bp", move: 100 },
];

const MACRO_PRESETS: Preset[] = SECTOR_PRESETS;

interface Props {
  holdings: Holding[];
}

export default function SectorImpact({ holdings }: Props) {
  const [factor, setFactor] = useState("Technology");
  const [rawMove, setRawMove] = useState(-0.20); // stored as the user-facing value
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  const isRate = factor === "Interest Rates";
  const presets = isRate ? RATE_PRESETS : FACTORS.find((f) => f.value === factor)?.group === "macro" ? MACRO_PRESETS : SECTOR_PRESETS;

  // For rates: convert bps to TLT % move. User says "+100bp" (rates rise) → TLT falls ~17%
  // rawMove for rates is stored in bps (e.g. -100 means rates +100bp)
  const apiMove = isRate ? (rawMove / 100) * RATE_DURATION / 100 : rawMove;

  // For display: determine if the scenario is "bad" (portfolio loses money)
  const query = useQuery({
    queryKey: ["sectorImpact", holdings, factor, apiMove],
    queryFn: () => getSectorImpact(holdings, factor, apiMove),
    enabled: holdings.length >= 1,
  });

  const data = query.data;
  const impactIsNeg = (data?.portfolio_exposure.projected_portfolio_impact ?? 0) < 0;

  // Active preset check
  function isActive(p: Preset) { return rawMove === p.move; }
  function presetColor(p: Preset) {
    if (isRate) return p.move < 0 ? "red" : "green"; // rates rising = red
    return p.move < 0 ? "red" : "green";
  }

  const proxyLabel = data?.sector_etf ? `${data.sector_etf}` : "proxy";

  return (
    <div className="glass-card">
      <h2 className="section-title mb-4">Scenario Analysis <InfoTooltip metricKey="scenario_analysis" /></h2>

      {/* Controls */}
      <div className="flex flex-wrap items-end gap-4 mb-5">
        <div>
          <label className="text-[10px] font-medium uppercase tracking-wider text-slate-500 block mb-1">What if</label>
          <div className="relative">
            <button
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              className="rounded-xl bg-[#1a1d24] border border-white/[0.04] px-4 py-2 text-sm text-slate-200 outline-none focus:border-white/[0.08] w-full text-left flex items-center justify-between"
            >
              <span>{FACTORS.find((f) => f.value === factor)?.label || factor}</span>
              <span className="text-xs">▼</span>
            </button>
            {isDropdownOpen && (
              <div className="absolute top-full left-0 mt-1 w-64 bg-[#1a1d24] border border-white/[0.04] rounded-xl z-10 max-h-56 overflow-y-auto">
                <div className="py-1">
                  <div className="px-3 py-2 text-[10px] font-medium uppercase tracking-wider text-slate-500 bg-white/[0.02]">
                    Sectors
                  </div>
                  {FACTORS.filter((f) => f.group === "sector").map((f) => (
                    <button
                      key={f.value}
                      onClick={() => {
                        setFactor(f.value);
                        setRawMove(-0.20);
                        setIsDropdownOpen(false);
                      }}
                      className={`w-full text-left px-4 py-2 text-sm transition-colors ${
                        factor === f.value
                          ? "bg-white/[0.08] text-slate-100"
                          : "text-slate-300 hover:bg-white/[0.04] hover:text-slate-100"
                      }`}
                    >
                      {f.label}
                    </button>
                  ))}
                  <div className="px-3 py-2 text-[10px] font-medium uppercase tracking-wider text-slate-500 bg-white/[0.02] mt-1">
                    Macro
                  </div>
                  {FACTORS.filter((f) => f.group === "macro").map((f) => (
                    <button
                      key={f.value}
                      onClick={() => {
                        setFactor(f.value);
                        const newIsRate = f.value === "Interest Rates";
                        setRawMove(newIsRate ? -100 : -0.20);
                        setIsDropdownOpen(false);
                      }}
                      className={`w-full text-left px-4 py-2 text-sm transition-colors ${
                        factor === f.value
                          ? "bg-white/[0.08] text-slate-100"
                          : "text-slate-300 hover:bg-white/[0.04] hover:text-slate-100"
                      }`}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <div>
          <label className="text-[10px] font-medium uppercase tracking-wider text-slate-500 block mb-1">
            {isRate ? "rate change" : "moves by"}
          </label>
          <div className="flex gap-1">
            {presets.map((p) => {
              const c = presetColor(p);
              return (
                <button
                  key={p.label}
                  onClick={() => setRawMove(p.move)}
                  className={`rounded-lg px-3 py-2 text-xs font-mono transition-colors ${
                    isActive(p)
                      ? c === "red"
                        ? "bg-red-500/15 border border-red-500/25 text-red-400"
                        : "bg-green-500/15 border border-green-500/25 text-green-400"
                      : "bg-white/[0.03] border border-white/[0.04] text-slate-500 hover:text-slate-300"
                  }`}
                >
                  {p.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Rate context note */}
      {isRate && (
        <div className="mb-4 rounded-xl bg-white/[0.02] border border-white/[0.04] px-4 py-2.5 text-xs text-slate-500">
          Using <span className="font-mono text-slate-400">TLT</span> (20+ Year Treasury Bond ETF) as proxy.
          {rawMove < 0
            ? ` Rates rising ${Math.abs(rawMove)}bp ≈ TLT falling ${Math.abs(apiMove * 100).toFixed(0)}%.`
            : ` Rates falling ${rawMove}bp ≈ TLT rising ${(apiMove * 100).toFixed(0)}%.`}
        </div>
      )}

      {/* Loading */}
      {query.isLoading && (
        <div className="flex h-32 items-center justify-center">
          <svg className="h-5 w-5 animate-spin text-slate-500" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
      )}

      {/* Results */}
      {data && (
        <div className="space-y-4">
          {/* Impact summary */}
          <div className="flex gap-4">
            <SummaryCard
              label="Portfolio Impact"
              value={fmtPct(data.portfolio_exposure.projected_portfolio_impact)}
              sub={fmtDollar(data.portfolio_exposure.projected_dollar_impact)}
              negative={impactIsNeg}
            />
            <SummaryCard
              label={isRate ? "Rate Sensitivity" : `${factor} Weight`}
              value={isRate
                ? `β ${data.portfolio_exposure.portfolio_beta_to_sector.toFixed(2)}`
                : fmtPct(data.portfolio_exposure.sector_weight)}
              sub={isRate
                ? `Portfolio beta to ${proxyLabel}`
                : `Beta to ${proxyLabel}: ${data.portfolio_exposure.portfolio_beta_to_sector.toFixed(2)}`}
            />
          </div>

          {/* Affected holdings */}
          {data.affected_holdings.length > 0 && (
            <div>
              <div className="mb-2 text-[10px] font-medium uppercase tracking-wider text-slate-500">
                {isRate ? "Most sensitive" : "Exposed"} ({data.affected_holdings.length})
              </div>
              <div className="space-y-1.5">
                {data.affected_holdings.map((h) => (
                  <HoldingRow
                    key={h.ticker}
                    ticker={h.ticker}
                    weight={h.weight}
                    impact={h.projected_loss}
                    impactDollar={h.projected_loss_dollars}
                    detail={`β to ${proxyLabel}: ${h.beta_to_sector_etf.toFixed(2)}`}
                    negative={h.projected_loss_dollars < 0}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Unaffected holdings */}
          {data.unaffected_holdings.length > 0 && (
            <div>
              <div className="mb-2 text-[10px] font-medium uppercase tracking-wider text-slate-500">
                {isRate ? "Less sensitive" : "Not directly exposed"} ({data.unaffected_holdings.length})
              </div>
              <div className="space-y-1.5">
                {data.unaffected_holdings.map((h) => (
                  <div
                    key={h.ticker}
                    className="flex items-center justify-between rounded-xl bg-white/[0.02] border border-white/[0.04] px-4 py-2.5"
                  >
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-sm font-semibold text-slate-200">{h.ticker}</span>
                      <span className="text-xs text-slate-500">{h.sector}</span>
                    </div>
                    <div className="text-right text-xs text-slate-500">
                      Corr to {proxyLabel}: <span className="font-mono text-slate-400">{h.correlation_to_sector.toFixed(2)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SummaryCard({ label, value, sub, negative }: {
  label: string; value: string; sub: string; negative?: boolean;
}) {
  return (
    <div className={`flex-1 rounded-2xl border px-5 py-4 ${
      negative ? "border-red-500/15 bg-red-950/10" : "border-white/[0.04] bg-white/[0.02]"
    }`}>
      <div className="text-[10px] font-medium uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`mt-1 text-xl font-semibold font-mono ${negative ? "text-red-400" : "text-slate-100"}`}>
        {value}
      </div>
      <div className="mt-0.5 text-xs text-slate-500">{sub}</div>
    </div>
  );
}

function HoldingRow({ ticker, weight, impact, impactDollar, detail, negative }: {
  ticker: string; weight: number; impact: number; impactDollar: number; detail: string; negative?: boolean;
}) {
  return (
    <div className={`flex items-center justify-between rounded-xl border px-4 py-2.5 ${
      negative ? "border-red-500/10 bg-red-950/5" : "border-green-500/10 bg-green-950/5"
    }`}>
      <div className="flex items-center gap-3">
        <span className="font-mono text-sm font-semibold text-slate-200">{ticker}</span>
        <span className="text-xs text-slate-500">{fmtPct(weight)} weight</span>
        <span className="text-xs text-slate-600">{detail}</span>
      </div>
      <div className="text-right">
        <span className={`font-mono text-sm font-semibold ${negative ? "text-red-400" : "text-green-400"}`}>
          {fmtPct(impact)}
        </span>
        <span className="ml-2 font-mono text-xs text-slate-500">
          {fmtDollar(impactDollar)}
        </span>
      </div>
    </div>
  );
}
