import React, { useState, useRef, useMemo } from "react";
import InfoTooltip from "../InfoTooltip";
import { betaColor } from "../../utils/colors";

interface HoldingQuality {
  ticker: string;
  quality_score?: number;
  garp_score?: number;
  thesis_health?: Record<string, unknown>;
}

interface Props {
  holdings_quality: HoldingQuality[];
  portfolio_quality_score?: number;
  portfolio_garp_score?: number;
  mctr?: Record<string, { mctr: number; pct_contribution: number }>;
  internal_betas?: Record<string, number>;
  weights?: Record<string, number>;
  correlation_clusters?: (string | number)[][];
}

type ThesisStatus = "Strong" | "Monitor" | "Review" | "Broken" | "No data";

function getThesisStatus(q: HoldingQuality): ThesisStatus {
  if (q.quality_score == null) return "No data";

  const backendStatus = q.thesis_health?.status as string | undefined;
  if (q.thesis_health?.type === "ETF" && backendStatus) {
    if (backendStatus === "Strong") return "Strong";
    if (backendStatus === "Monitor") return "Monitor";
    if (backendStatus === "Review") return "Review";
    if (backendStatus === "Broken") return "Broken";
  }

  const score = q.quality_score;
  if (score === 0 && (!q.thesis_health || Object.keys(q.thesis_health).length === 0)) return "No data";
  if (score >= 70) return "Strong";
  if (score >= 50) return "Monitor";
  if (score >= 30) return "Review";
  return "Broken";
}

function getThesisReason(q: HoldingQuality): string {
  const th = q.thesis_health as Record<string, unknown> | undefined;
  if (!th) return `Quality score: ${q.quality_score ?? "N/A"}`;

  const lines: string[] = [];
  const score = q.quality_score;
  if (score != null) lines.push(`Quality score: ${score}`);

  // ROIC / moat
  const roic = th.roic as Record<string, unknown> | undefined;
  if (roic) {
    const cur = roic.current as number | undefined;
    const moat = roic.moat as string | undefined;
    if (cur != null) lines.push(`ROIC: ${(cur * 100).toFixed(1)}%${moat ? ` (${moat} moat)` : ""}`);
    if (roic.stable === false) lines.push("ROIC declining");
  }

  // Revenue
  const rev = th.revenue as Record<string, unknown> | undefined;
  if (rev) {
    const yoy = rev.latest_yoy as number | undefined;
    if (yoy != null) lines.push(`Revenue growth: ${(yoy * 100).toFixed(1)}% YoY`);
    if (rev.accelerating === true) lines.push("Revenue accelerating");
    if (rev.accelerating === false) lines.push("Revenue decelerating");
    if (rev.all_positive === false) lines.push("Had negative revenue year(s)");
  }

  // Earnings
  const earn = th.earnings as Record<string, unknown> | undefined;
  if (earn) {
    if (earn.margin_expanding === true) lines.push("Margins expanding");
    if (earn.margin_expanding === false) lines.push("Margins contracting");
    if (earn.all_positive === false) lines.push("Had negative earnings year(s)");
  }

  // FCF
  const fcf = th.fcf as Record<string, unknown> | undefined;
  if (fcf) {
    const yield_ = fcf.yield as number | undefined;
    if (yield_ != null) lines.push(`FCF yield: ${(yield_ * 100).toFixed(1)}%`);
    if (fcf.growing === false) lines.push("FCF not growing");
  }

  // Balance sheet
  const bal = th.balance as Record<string, unknown> | undefined;
  if (bal) {
    const dte = bal.debt_to_equity as number | undefined;
    if (dte != null && dte > 50) lines.push(`High D/E: ${dte.toFixed(0)}`);
  }

  // Flags
  const flags = th.flags as string[] | undefined;
  if (flags && flags.length > 0) lines.push(...flags);

  return lines.join(" · ") || `Quality score: ${score ?? "N/A"}`;
}

const statusColors: Record<ThesisStatus, string> = {
  Strong: "text-green-400",
  Monitor: "text-yellow-400",
  Review: "text-orange-400",
  "No data": "text-slate-500",
  Broken: "text-red-400",
};

const statusRgb: Record<ThesisStatus, string> = {
  Strong: "74, 222, 128",
  Monitor: "250, 204, 21",
  Review: "251, 146, 60",
  Broken: "248, 113, 113",
  "No data": "100, 116, 139",
};

// --- Portfolio-context thesis ---

type PortfolioFit = "Core" | "Diversifier" | "Overweight" | "Redundant" | "Trim";

const fitColors: Record<PortfolioFit, string> = {
  Core: "text-green-400",
  Diversifier: "text-blue-400",
  Overweight: "text-yellow-400",
  Redundant: "text-orange-400",
  Trim: "text-red-400",
};

const fitRgb: Record<PortfolioFit, string> = {
  Core: "74, 222, 128",
  Diversifier: "96, 165, 250",
  Overweight: "250, 204, 21",
  Redundant: "251, 146, 60",
  Trim: "248, 113, 113",
};

function getPortfolioFit(
  ticker: string,
  quality: HoldingQuality,
  mctr?: Record<string, { mctr: number; pct_contribution: number }>,
  weights?: Record<string, number>,
  clusters?: (string | number)[][],
  internalBetas?: Record<string, number>,
): { fit: PortfolioFit; reason: string } {
  const qualityScore = quality.quality_score ?? 0;
  const garpScore = quality.garp_score ?? 0;
  const weight = weights?.[ticker] ?? 0;
  const riskPct = mctr?.[ticker]?.pct_contribution ?? 0;
  const beta = internalBetas?.[ticker] ?? null;
  const holdingCount = Object.keys(weights ?? {}).length;
  const evenWeight = holdingCount > 0 ? 1 / holdingCount : 0;

  // ── Thesis health sub-metrics ──────────────────────────────────────────────
  const th = quality.thesis_health as Record<string, unknown> | undefined;
  const thesisStatus = th?.status as string | undefined;
  const roic = th?.roic as Record<string, unknown> | undefined;
  const moat = roic?.moat as string | undefined;
  const roicStable = roic?.stable as boolean | undefined;
  const rev = th?.revenue as Record<string, unknown> | undefined;
  const revenueAccelerating = rev?.accelerating as boolean | undefined;
  const revenueAllPositive = rev?.all_positive as boolean | undefined;
  const earn = th?.earnings as Record<string, unknown> | undefined;
  const marginExpanding = earn?.margin_expanding as boolean | undefined;
  const fcf = th?.fcf as Record<string, unknown> | undefined;
  const fcfGrowing = fcf?.growing as boolean | undefined;
  const bal = th?.balance as Record<string, unknown> | undefined;
  const debtToEquity = bal?.debt_to_equity as number | undefined;
  const flags = (th?.flags as string[] | undefined) ?? [];

  // ── Derived signals ────────────────────────────────────────────────────────
  const isHighQuality = qualityScore >= 60;
  const isGoodValue = garpScore >= 50;
  const isOverweight = weight > evenWeight * 2.5 && holdingCount >= 3;
  const isRiskHog = riskPct > 0.4;
  const isHighBeta = beta != null && beta > 1.5;
  const isLowBeta = beta != null && beta < 0.4;
  const isVeryLowBeta = beta != null && beta < 0.2;
  const isNegativeBeta = beta != null && beta < 0;
  const hasHighDebt = debtToEquity != null && debtToEquity > 120;
  const isBrokenThesis = thesisStatus === "Broken";
  const isWideM = moat === "Wide";
  const isCompounding = isWideM && roicStable !== false && marginExpanding === true && fcfGrowing === true;
  const hasRedFlags = flags.length > 0 || revenueAllPositive === false;

  // Correlation cluster peers
  let clusterPeers = 0;
  if (clusters) {
    for (const cluster of clusters) {
      const tickers = cluster.filter((v): v is string => typeof v === "string");
      if (tickers.includes(ticker) && tickers.length > 1) {
        clusterPeers = tickers.length - 1;
        break;
      }
    }
  }
  const isRedundant = clusterPeers >= 2;

  // ── Helpers to build reason strings ───────────────────────────────────────
  const betaStr = beta != null ? `Int. beta ${beta.toFixed(2)}` : null;
  const weightStr = `${(weight * 100).toFixed(0)}% weight`;
  const riskStr = `${(riskPct * 100).toFixed(0)}% of portfolio risk`;

  // ── Classification ─────────────────────────────────────────────────────────

  // TRIM: broken thesis compounded by structural risk factors
  if (isBrokenThesis && (isRiskHog || isOverweight || isHighBeta || hasHighDebt)) {
    const reasons = ["Broken thesis"];
    if (isRiskHog) reasons.push(riskStr);
    if (isOverweight) reasons.push(weightStr);
    if (isHighBeta) reasons.push(betaStr!);
    if (hasHighDebt) reasons.push(`D/E ${debtToEquity!.toFixed(0)}`);
    return { fit: "Trim", reason: reasons.join(" · ") };
  }

  // TRIM: low quality + overweight or risk hog
  if (!isHighQuality && (isRiskHog || isOverweight)) {
    const reasons = [`Quality ${qualityScore} below threshold`];
    if (isRiskHog) reasons.push(riskStr);
    if (isOverweight) reasons.push(`overweight at ${weightStr}`);
    if (hasRedFlags) reasons.push(`${flags[0] ?? "negative revenue years"}`);
    return { fit: "Trim", reason: reasons.join(" · ") };
  }

  // REDUNDANT: correlated with multiple peers
  if (isRedundant) {
    const peers = `Moves with ${clusterPeers} other holding${clusterPeers > 1 ? "s" : ""}`;
    if (!isHighQuality) {
      return { fit: "Redundant", reason: `${peers} · Quality ${qualityScore} below threshold · Low diversification value` };
    }
    return { fit: "Redundant", reason: `${peers} · Quality ${qualityScore} is good but correlation reduces marginal value` };
  }

  // OVERWEIGHT: structural position sizing issue
  if (isOverweight || isRiskHog) {
    const reasons = [weightStr, riskStr];
    if (isHighQuality) reasons.push("reduce size to let quality compound without concentration risk");
    else reasons.push("quality doesn't justify the concentration");
    return { fit: "Overweight", reason: reasons.join(" · ") };
  }

  // NATURAL HEDGE / EXCELLENT DIVERSIFIER: negative or very low beta
  if (isNegativeBeta || isVeryLowBeta) {
    const reasons = [betaStr!];
    if (isNegativeBeta) reasons.push("moves against the portfolio — acts as a hedge");
    else reasons.push("moves nearly independently of the portfolio");
    if (isHighQuality) reasons.push(`quality ${qualityScore} adds fundamental support`);
    return { fit: "Diversifier", reason: reasons.join(" · ") };
  }

  // DIVERSIFIER: low beta or low risk contribution
  if ((isLowBeta || (riskPct < 0.15 && riskPct > 0)) && qualityScore >= 40) {
    const reasons: string[] = [];
    if (betaStr) reasons.push(betaStr);
    reasons.push(riskStr);
    if (isHighQuality) reasons.push(`quality ${qualityScore} adds stability`);
    else reasons.push("adds diversification even at moderate quality");
    return { fit: "Diversifier", reason: reasons.join(" · ") };
  }

  // CORE (premium): compounding quality machine
  if (isHighQuality && isGoodValue && isCompounding) {
    const reasons = [`Quality ${qualityScore} · GARP ${garpScore}`];
    if (isWideM) reasons.push("wide moat");
    if (marginExpanding) reasons.push("margins expanding");
    if (fcfGrowing) reasons.push("FCF growing");
    if (betaStr) reasons.push(betaStr);
    return { fit: "Core", reason: reasons.join(" · ") };
  }

  // CORE: high quality + good value
  if (isHighQuality && isGoodValue) {
    const reasons = [`Quality ${qualityScore} · GARP ${garpScore}`];
    if (isWideM) reasons.push("wide moat");
    if (revenueAccelerating) reasons.push("revenue accelerating");
    if (!hasRedFlags) reasons.push("clean fundamentals");
    if (betaStr) reasons.push(betaStr);
    return { fit: "Core", reason: reasons.join(" · ") };
  }

  // CORE: high quality even without great GARP
  if (isHighQuality) {
    const reasons = [`Quality ${qualityScore}`];
    if (isWideM) reasons.push("wide moat");
    if (roicStable !== false) reasons.push("stable ROIC");
    reasons.push(`GARP ${garpScore} — check valuation before adding`);
    return { fit: "Core", reason: reasons.join(" · ") };
  }

  // DEFAULT: low quality diversifier
  const reasons = [`Quality ${qualityScore} below 60`];
  if (betaStr) reasons.push(betaStr);
  reasons.push(riskStr);
  if (hasRedFlags && flags.length > 0) reasons.push(flags[0]);
  return { fit: "Diversifier", reason: reasons.join(" · ") };
}

// ─── Sorting ─────────────────────────────────────────────────────────────────

type SortCol = "quality" | "garp" | "beta" | "thesis" | "fit";

const THESIS_ORDER: Record<ThesisStatus, number> = { Strong: 4, Monitor: 3, Review: 2, Broken: 1, "No data": 0 };
const FIT_ORDER: Record<PortfolioFit, number> = { Core: 5, Diversifier: 4, Overweight: 3, Redundant: 2, Trim: 1 };

// ─── Improvement hints ────────────────────────────────────────────────────────

function getQualityHints(h: HoldingQuality): string {
  const score = h.quality_score;
  if (score == null) return "No data available.";
  if (score >= 80) return `Score ${score} — strong across ROIC, margins, FCF, and earnings consistency.`;

  const th = h.thesis_health as Record<string, unknown> | undefined;
  if (!th) return `Score ${score}. Drivers: ROIC (25%), gross margins (25%), FCF yield (15%), earnings consistency (15%), debt health (10%), revenue growth (10%).`;

  const hints: string[] = [];
  const roic = th.roic as Record<string, unknown> | undefined;
  if (roic?.current != null && (roic.current as number) < 0.15)
    hints.push(`ROIC ${((roic.current as number) * 100).toFixed(1)}% — target >15% (worth 20/25 pts)`);
  const fcf = th.fcf as Record<string, unknown> | undefined;
  if (fcf?.yield != null && (fcf.yield as number) < 0.03)
    hints.push(`FCF yield ${((fcf.yield as number) * 100).toFixed(1)}% — target >3% (up to 12/15 pts)`);
  if (fcf?.growing === false) hints.push("FCF not growing — resuming growth unlocks up to 5 pts");
  const rev = th.revenue as Record<string, unknown> | undefined;
  if (rev?.accelerating === false) hints.push("Revenue decelerating — acceleration adds up to 5 pts");
  if (rev?.all_positive === false) hints.push("Had negative revenue year — all-positive trend needed");
  const earn = th.earnings as Record<string, unknown> | undefined;
  if (earn?.margin_expanding === false) hints.push("Margins contracting — expansion unlocks pts");
  if (earn?.all_positive === false) hints.push("Had negative earnings year — consistency needed");
  const bal = th.balance as Record<string, unknown> | undefined;
  if (bal?.debt_to_equity != null && (bal.debt_to_equity as number) > 100)
    hints.push(`D/E ${(bal.debt_to_equity as number).toFixed(0)} — reduce below 75 for full debt pts`);
  const flags = th.flags as string[] | undefined;
  if (flags && flags.length > 0 && hints.length === 0) hints.push(...flags);

  return hints.length > 0
    ? `Score ${score} — to improve: ${hints.join(" · ")}`
    : `Score ${score} — components: ROIC, margins, FCF yield, earnings consistency, debt, revenue growth.`;
}

function getGarpHints(score: number | undefined): string {
  if (score == null) return "No data.";
  if (score >= 70) return `Score ${score} — PEG ratio, earnings growth, revenue growth, and forward P/E are all favorable.`;
  const hints: string[] = [];
  if (score < 40) hints.push("PEG likely above 2 — target PEG < 1.5 (worth 25/40 pts)");
  else hints.push("PEG is moderate — target PEG < 1.0 for full 40 pts");
  hints.push("Earnings growth > 15% adds 20/25 pts", "Revenue growth > 20% adds 15/15 pts", "Forward P/E < 20 adds 15/20 pts");
  return `Score ${score} — to improve: ${hints.join(" · ")}`;
}

// ─── Sortable column header ───────────────────────────────────────────────────

function SortTh({
  label, col, sortCol, sortDir, onToggle, children,
}: {
  label: string; col: SortCol; sortCol: SortCol; sortDir: "asc" | "desc";
  onToggle: (col: SortCol) => void; children?: React.ReactNode;
}) {
  const active = sortCol === col;
  return (
    <th className="pb-2 text-center font-medium">
      <span className="cursor-pointer select-none hover:text-slate-200" onClick={() => onToggle(col)}>
        {label}
        <span className="ml-1 text-slate-500">{active ? (sortDir === "desc" ? "↓" : "↑") : "↕"}</span>
      </span>
      {children}
    </th>
  );
}

// ─── Tooltip badge ────────────────────────────────────────────────────────────
// Uses fixed positioning so the tooltip escapes overflow:hidden/auto containers.

function BadgeWithTooltip({
  label,
  tooltip,
  colorClass,
  rgb,
}: {
  label: string;
  tooltip: string;
  colorClass: string;
  rgb: string;
}) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const ref = useRef<HTMLSpanElement>(null);

  function show() {
    if (!ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const TOOLTIP_W = 240; // w-60
    const rawX = r.left + r.width / 2;
    const clampedX = Math.max(TOOLTIP_W / 2 + 8, Math.min(rawX, window.innerWidth - TOOLTIP_W / 2 - 8));
    setPos({ x: clampedX, y: r.top - 8 });
  }

  return (
    <>
      <span
        ref={ref}
        className={`badge-bordered cursor-default ${colorClass}`}
        style={{ background: `rgba(${rgb}, 0.08)`, border: `1px solid rgba(${rgb}, 0.15)` }}
        onMouseEnter={show}
        onMouseLeave={() => setPos(null)}
      >
        {label}
      </span>
      {pos && (
        <span
          className="pointer-events-none fixed z-50 w-60 rounded-xl px-3 py-2 text-left text-[11px] leading-relaxed text-slate-300 shadow-xl"
          style={{
            left: pos.x,
            top: pos.y,
            transform: "translateY(-100%) translateX(-50%)",
            background: "#1a1d24",
            border: "1px solid rgba(255,255,255,0.1)",
          }}
        >
          {tooltip}
        </span>
      )}
    </>
  );
}

export default function QualityDashboard({
  holdings_quality,
  portfolio_quality_score,
  portfolio_garp_score,
  mctr,
  internal_betas,
  weights,
  correlation_clusters,
}: Props) {
  const [sortCol, setSortCol] = useState<SortCol>("quality");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  function toggleSort(col: SortCol) {
    if (sortCol === col) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else { setSortCol(col); setSortDir(col === "beta" ? "asc" : "desc"); }
  }

  const sortedRows = useMemo(() => {
    const rows = holdings_quality.map((h) => {
      const { fit } = getPortfolioFit(h.ticker, h, mctr, weights, correlation_clusters, internal_betas);
      return { h, fit };
    });
    return [...rows].sort((a, b) => {
      let av = 0, bv = 0;
      if (sortCol === "quality") { av = a.h.quality_score ?? -1; bv = b.h.quality_score ?? -1; }
      else if (sortCol === "garp") { av = a.h.garp_score ?? -1; bv = b.h.garp_score ?? -1; }
      else if (sortCol === "beta") { av = internal_betas?.[a.h.ticker] ?? 999; bv = internal_betas?.[b.h.ticker] ?? 999; }
      else if (sortCol === "thesis") { av = THESIS_ORDER[getThesisStatus(a.h)]; bv = THESIS_ORDER[getThesisStatus(b.h)]; }
      else if (sortCol === "fit") { av = FIT_ORDER[a.fit]; bv = FIT_ORDER[b.fit]; }
      return sortDir === "desc" ? bv - av : av - bv;
    });
  }, [holdings_quality, sortCol, sortDir, mctr, weights, correlation_clusters, internal_betas]);

  return (
    <div className="glass-card">
      <h2 className="section-title">
        Quality Dashboard
        <InfoTooltip metricKey="quality_section" />
      </h2>

      {/* Portfolio-level scores */}
      <div className="mb-4 flex gap-6">
        <div className="glass-surface px-5 py-3 text-center">
          <div className="metric-label">
            Portfolio Quality <InfoTooltip metricKey="quality_section" />
          </div>
          <div className="mt-1 text-2xl font-bold text-blue-400 gradient-text">
            {portfolio_quality_score != null ? portfolio_quality_score.toFixed(0) : "--"}
          </div>
        </div>
        <div className="glass-surface px-5 py-3 text-center">
          <div className="metric-label">
            Portfolio GARP <InfoTooltip metricKey="garp_section" />
          </div>
          <div className="mt-1 text-2xl font-bold text-purple-400 gradient-text">
            {portfolio_garp_score != null ? portfolio_garp_score.toFixed(0) : "--"}
          </div>
        </div>
      </div>

      {/* Holdings table */}
      <div className="overflow-x-auto">
        <table className="w-full table-fixed text-sm">
          <thead>
            <tr className="border-b border-white/[0.06] text-[10px] font-medium tracking-wider text-slate-500">
              <th className="w-1/6 pb-2 text-left font-medium">Ticker</th>
              <SortTh label="Quality" col="quality" sortCol={sortCol} sortDir={sortDir} onToggle={toggleSort}><InfoTooltip metricKey="quality_section" /></SortTh>
              <SortTh label="GARP" col="garp" sortCol={sortCol} sortDir={sortDir} onToggle={toggleSort}><InfoTooltip metricKey="garp_section" /></SortTh>
              <SortTh label="Int. Beta" col="beta" sortCol={sortCol} sortDir={sortDir} onToggle={toggleSort}><InfoTooltip metricKey="internal_beta" /></SortTh>
              <SortTh label="Thesis" col="thesis" sortCol={sortCol} sortDir={sortDir} onToggle={toggleSort}><InfoTooltip metricKey="thesis_status" /></SortTh>
              <SortTh label="Portfolio Fit" col="fit" sortCol={sortCol} sortDir={sortDir} onToggle={toggleSort}><InfoTooltip metricKey="portfolio_fit" /></SortTh>
            </tr>
          </thead>
          <tbody>
            {sortedRows.map(({ h, fit: precomputedFit }) => {
              const status = getThesisStatus(h);
              const thesisReason = getThesisReason(h);
              const { reason: fitReason } = getPortfolioFit(h.ticker, h, mctr, weights, correlation_clusters, internal_betas);
              return (
                <tr key={h.ticker} className="border-b border-white/[0.04] row-hover transition-colors">
                  <td className="py-2 font-mono font-semibold text-slate-100">{h.ticker}</td>
                  <td className="py-2 text-center">
                    <BadgeWithTooltip
                      label={h.quality_score != null ? h.quality_score.toFixed(0) : "--"}
                      tooltip={getQualityHints(h)}
                      colorClass={h.quality_score != null && h.quality_score >= 70 ? "text-green-400" : h.quality_score != null && h.quality_score >= 50 ? "text-yellow-400" : "text-slate-400"}
                      rgb={h.quality_score != null && h.quality_score >= 70 ? "74,222,128" : h.quality_score != null && h.quality_score >= 50 ? "250,204,21" : "148,163,184"}
                    />
                  </td>
                  <td className="py-2 text-center">
                    <BadgeWithTooltip
                      label={h.garp_score != null ? h.garp_score.toFixed(0) : "--"}
                      tooltip={getGarpHints(h.garp_score)}
                      colorClass={h.garp_score != null && h.garp_score >= 70 ? "text-purple-400" : h.garp_score != null && h.garp_score >= 50 ? "text-yellow-400" : "text-slate-400"}
                      rgb={h.garp_score != null && h.garp_score >= 70 ? "196,181,253" : h.garp_score != null && h.garp_score >= 50 ? "250,204,21" : "148,163,184"}
                    />
                  </td>
                  <td className="py-2 text-center font-mono text-slate-300">
                    {(() => {
                      const b = internal_betas?.[h.ticker];
                      if (b == null) return "--";
                      return <span className={betaColor(b)}>{b.toFixed(2)}</span>;
                    })()}
                  </td>
                  <td className="py-2 text-center">
                    <BadgeWithTooltip
                      label={status}
                      tooltip={thesisReason}
                      colorClass={statusColors[status]}
                      rgb={statusRgb[status]}
                    />
                  </td>
                  <td className="py-2 text-center">
                    <BadgeWithTooltip
                      label={precomputedFit}
                      tooltip={fitReason}
                      colorClass={fitColors[precomputedFit]}
                      rgb={fitRgb[precomputedFit]}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
