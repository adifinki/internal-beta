import { useState } from "react";
import type { Recommendation } from "../../api/client";

interface Props {
  recommendations: Recommendation[];
}

const PRIORITY_COLORS = {
  high: { dot: "bg-rose-400/70", border: "border-rose-500/20", bg: "bg-rose-950/10", label: "text-rose-400/80" },
  medium: { dot: "bg-amber-400/70", border: "border-amber-500/20", bg: "bg-amber-950/10", label: "text-amber-400/80" },
  low: { dot: "bg-slate-400/50", border: "border-slate-500/20", bg: "bg-slate-900/20", label: "text-slate-500" },
};

const TYPE_LABELS: Record<string, string> = {
  add: "Add",
  trim: "Trim",
  exit: "Exit",
  rebalance: "Rebalance",
  context: "Context",
};

// Map evidence keys and rec types to their intellectual source.
// Multiple sources can apply — we show the most prominent one.
function getSource(type: string, evidence: Record<string, number | string | null>): { label: string; color: string } {
  const keys = Object.keys(evidence);
  if (keys.some((k) => ["quality_score", "thesis_flags", "roic", "moat"].includes(k)) || type === "exit")
    return { label: "Buffett", color: "text-amber-400/70" };
  if (keys.some((k) => ["peg", "peg_ratio", "earnings_growth", "earningsGrowth"].includes(k)))
    return { label: "Lynch", color: "text-blue-400/70" };
  if (keys.some((k) => ["hhi", "sector_weight", "num_holdings", "portfolio_beta"].includes(k)) || type === "rebalance")
    return { label: "Bogle", color: "text-green-400/70" };
  return { label: "Risk", color: "text-slate-500" };
}

// Human-readable labels for evidence keys
const EVIDENCE_LABELS: Record<string, string> = {
  pct_contribution: "% of risk",
  internal_beta: "int. beta",
  weight: "weight",
  quality_score: "quality",
  garp_score: "GARP",
  thesis_flags: "flags",
  sharpe: "Sharpe",
  volatility: "vol",
  max_drawdown: "max DD",
  var_95: "VaR 95",
  cvar_95: "CVaR 95",
  hhi: "HHI",
  portfolio_beta: "port. beta",
  sector_weight: "sector wt",
  num_holdings: "holdings",
  vol_improvement: "vol Δ",
  new_weights: "new wts",
};

// Keys that are internal detail — hide from the evidence panel
const HIDDEN_EVIDENCE_KEYS = new Set(["action_detail", "principle"]);

function formatEvidenceValue(k: string, v: number | string | null): string {
  if (v == null) return "—";
  if (Array.isArray(v)) return (v as string[]).slice(0, 2).join(", ");
  if (typeof v === "number") {
    if (["pct_contribution", "weight", "sector_weight", "vol_improvement", "volatility", "max_drawdown"].includes(k))
      return `${(v * 100).toFixed(1)}%`;
    if (["sharpe", "internal_beta", "portfolio_beta"].includes(k)) return v.toFixed(2);
    if (["var_95", "cvar_95"].includes(k)) return `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
    return v.toFixed(2);
  }
  return String(v);
}

export default function Recommendations({ recommendations }: Props) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  if (!recommendations?.length) return null;

  const high = recommendations.filter((r) => r.priority === "high");
  const medium = recommendations.filter((r) => r.priority === "medium");
  const low = recommendations.filter((r) => r.priority === "low");

  return (
    <div className="glass-card">
      <div className="mb-5 flex items-center justify-between">
        <h2 className="section-title mb-0">Things to Consider</h2>
        <div className="flex gap-3 text-xs text-slate-600">
          {high.length > 0 && <span><span className="text-rose-400/80 font-semibold">{high.length}</span> high</span>}
          {medium.length > 0 && <span><span className="text-amber-400/80 font-semibold">{medium.length}</span> medium</span>}
          {low.length > 0 && <span><span className="text-slate-500 font-semibold">{low.length}</span> low</span>}
        </div>
      </div>

      <div className="space-y-3">
        {recommendations.map((rec, i) => {
          const colors = PRIORITY_COLORS[rec.priority];
          const source = getSource(rec.type, rec.evidence);
          const isExpanded = expandedIdx === i;
          // Filter out null values and empty arrays — only count entries that will actually render
          const evidenceEntries = Object.entries(rec.evidence ?? {}).filter(([k, v]) =>
            !HIDDEN_EVIDENCE_KEYS.has(k) && v != null && !(Array.isArray(v) && (v as unknown[]).length === 0),
          );
          const hasEvidence = evidenceEntries.length > 0;

          return (
            <div
              key={i}
              className={`rounded-2xl border ${colors.border} ${colors.bg} overflow-hidden`}
            >
              {/* Main row — click to expand */}
              <div
                className={`flex items-start gap-3 p-5 ${hasEvidence ? "cursor-pointer" : ""}`}
                onClick={() => hasEvidence && setExpandedIdx(isExpanded ? null : i)}
              >
                <div className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${colors.dot}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="text-sm font-bold text-slate-100">{rec.action}</span>
                    <span className={`text-[10px] font-medium uppercase tracking-wider ${colors.label}`}>
                      {TYPE_LABELS[rec.type] ?? rec.type}
                    </span>
                    {rec.ticker && (
                      <span className="font-mono text-xs text-slate-400">{rec.ticker}</span>
                    )}
                    <span className={`text-[10px] font-medium ${source.color}`}>{source.label}</span>
                  </div>
                  <p className="text-xs leading-relaxed text-slate-400">{rec.reason}</p>
                </div>
                {hasEvidence && (
                  <span className="shrink-0 text-slate-600 text-xs select-none">
                    {isExpanded ? "▲" : "▼"}
                  </span>
                )}
              </div>

              {/* Expanded evidence panel */}
              {isExpanded && hasEvidence && (
                <div className="border-t border-white/[0.05] px-5 py-3 bg-black/[0.15]">
                  <div className="mb-2 text-[10px] font-semibold tracking-wider text-slate-600">
                    Evidence
                  </div>
                  <div className="flex flex-wrap gap-x-5 gap-y-1.5">
                    {evidenceEntries.map(([k, v]) => (
                      <div key={k} className="flex flex-col">
                        <span className="text-[10px] text-slate-600">
                          {EVIDENCE_LABELS[k] ?? k.replace(/_/g, " ")}
                        </span>
                        <span className="font-mono text-xs text-slate-300">
                          {formatEvidenceValue(k, v as number | string | null)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
