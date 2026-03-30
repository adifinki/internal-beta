/**
 * Centralized color logic for metrics.
 * Single source of truth for beta colors, delta colors, and score colors.
 */

/** Internal beta color — used in Screener, QualityDashboard, CandidateAnalysis. */
export function betaColor(beta: number): string {
  if (beta < 0) return "text-emerald-400/80";
  if (beta < 0.5) return "text-emerald-400/70";
  if (beta < 0.8) return "text-blue-300/70";
  if (beta < 1.2) return "text-slate-400";
  return "text-red-400/80";
}

/** Plain-English beta verdict. */
export function betaVerdict(beta: number): string {
  if (beta < 0) return "Natural hedge: moves against your portfolio";
  if (beta < 0.5) return "Strong diversifier: weakly tied to your portfolio";
  if (beta < 0.8) return "Good diversifier: moderate independence";
  if (beta < 1.2) return "Moves with your portfolio: limited diversification";
  return "Amplifies your portfolio: increases concentration risk";
}

/** Border/bg color for the internal beta hero card — subtle, not shouty. */
export function betaCardStyle(beta: number): { border: string; bg: string; text: string } {
  if (beta < 0) return { border: "border-emerald-500/20", bg: "bg-emerald-950/10", text: "text-emerald-400/80" };
  if (beta < 0.5) return { border: "border-emerald-500/15", bg: "bg-emerald-950/8", text: "text-emerald-400/70" };
  if (beta < 0.8) return { border: "border-blue-500/15", bg: "bg-blue-950/8", text: "text-blue-300/70" };
  if (beta < 1.2) return { border: "border-amber-500/15", bg: "bg-amber-950/8", text: "text-amber-400/70" };
  return { border: "border-red-500/15", bg: "bg-red-950/8", text: "text-red-400/70" };
}

/** Delta color: muted green if improvement, muted red if worse. */
export function deltaColor(key: string, delta: number): string {
  if (delta === 0) return "text-slate-600";
  const good = isDeltaGood(key, delta);
  return good ? "text-emerald-400/80" : "text-red-400/70";
}

/** Whether a delta represents an improvement depends on the metric.
 *
 * "Higher is better" metrics: sharpe, sortino, annual_return,
 *   var_95/cvar_95 (negative dollar amounts — less negative = better),
 *   max_drawdown_pct/max_drawdown_dollars (negative — less negative = better).
 *
 * "Lower is better" metrics: volatility, recovery_days.
 */
export function isDeltaGood(key: string, delta: number): boolean {
  if (key === "volatility" || key === "recovery_days") return delta < 0;
  return delta > 0;
}

/** Score bar color for quality/garp scores. */
export function scoreColor(value: number): string {
  if (value >= 70) return "bg-emerald-700";
  if (value >= 40) return "bg-amber-700";
  return "bg-red-800";
}

/** Correlation color for the heatmap — desaturated jewel tones. */
export function correlationColor(v: number, isDiagonal: boolean): string {
  if (isDiagonal) return "bg-slate-700/40 text-slate-500";
  if (v >= 0.8) return "bg-red-900/60 text-red-200 font-semibold";
  if (v >= 0.6) return "bg-red-900/40 text-red-300";
  if (v >= 0.4) return "bg-amber-900/30 text-amber-200";
  if (v >= 0.3) return "bg-amber-900/15 text-slate-300";
  if (v >= 0.15) return "bg-slate-700/30 text-slate-400";
  if (v >= 0) return "bg-emerald-900/20 text-emerald-300";
  if (v > -0.3) return "bg-emerald-900/30 text-emerald-200";
  if (v > -0.6) return "bg-emerald-900/40 text-emerald-200";
  return "bg-emerald-900/50 text-emerald-100 font-semibold";
}

/** Chart color palette — desaturated jewel tones. */
export const CHART_COLORS = [
  "#5b8def", "#8a7cc8", "#4a9eab", "#4a9e6d", "#c9a84c",
  "#c8875a", "#b85c5c", "#a8698a", "#6e74b8", "#5a9e94",
  "#9076b8", "#b89a5a",
];

/** Recharts tooltip style — consistent across all charts. */
export const CHART_TOOLTIP_STYLE = {
  backgroundColor: "#1a1d24",
  border: "1px solid rgba(255,255,255,0.12)",
  borderRadius: 10,
  fontSize: 12,
  color: "#e2e8f0",
  padding: "8px 12px",
};
