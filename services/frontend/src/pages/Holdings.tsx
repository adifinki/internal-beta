import { Fragment, useMemo, useState } from "react";
import { useQueries } from "@tanstack/react-query";
import type { Holding } from "../api/client";
import { getTickerInfo } from "../api/client";
import { fmtDollar, fmtDollarCompact, fmtPct, fmtNum } from "../utils/format";

interface Props {
  holdings: Holding[];
}

const COLORS = [
  "#5b8def", "#d4a574", "#7c8cc8", "#4a9e6d", "#c77dba",
  "#e8917a", "#5bbfbf", "#d4d46a", "#a0a0a0", "#e06c75",
  "#98c379", "#e5c07b", "#61afef", "#c678dd", "#56b6c2",
];

function n(v: unknown): number | null {
  if (v == null) return null;
  const x = Number(v);
  return isFinite(x) ? x : null;
}

// SVG donut chart — filled arc wedges with gaps
function DonutChart({ slices, total, size = 240, hovered, onHover }: {
  slices: { ticker: string; value: number; color: string }[];
  total: number;
  size?: number;
  hovered: string | null;
  onHover: (ticker: string | null) => void;
}) {
  const cx = size / 2;
  const cy = size / 2;
  const outerR = size / 2 - 8;
  const innerR = outerR - 32;
  const gapDeg = slices.length > 1 ? 1.5 : 0; // gap between slices in degrees

  const toRad = (deg: number) => (deg * Math.PI) / 180;

  let cumAngle = -90;
  const wedges = slices.map((s) => {
    const pct = s.value / total;
    const fullAngle = pct * 360;
    const angle = Math.max(fullAngle - gapDeg, 0.5); // leave gap, min 0.5deg visible
    const start = cumAngle + gapDeg / 2;
    cumAngle += fullAngle;
    const end = start + angle;

    const s1 = toRad(start), e1 = toRad(end);
    const ox1 = cx + outerR * Math.cos(s1), oy1 = cy + outerR * Math.sin(s1);
    const ox2 = cx + outerR * Math.cos(e1), oy2 = cy + outerR * Math.sin(e1);
    const ix1 = cx + innerR * Math.cos(e1), iy1 = cy + innerR * Math.sin(e1);
    const ix2 = cx + innerR * Math.cos(s1), iy2 = cy + innerR * Math.sin(s1);
    const large = angle > 180 ? 1 : 0;

    const d = [
      `M ${ox1} ${oy1}`,
      `A ${outerR} ${outerR} 0 ${large} 1 ${ox2} ${oy2}`,
      `L ${ix1} ${iy1}`,
      `A ${innerR} ${innerR} 0 ${large} 0 ${ix2} ${iy2}`,
      "Z",
    ].join(" ");

    return { ...s, pct, d };
  });

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <defs>
        {wedges.map((w) => (
          <linearGradient key={`g-${w.ticker}`} id={`grad-${w.ticker}`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={w.color} stopOpacity={0.95} />
            <stop offset="100%" stopColor={w.color} stopOpacity={0.65} />
          </linearGradient>
        ))}
      </defs>

      {/* Subtle inner shadow ring */}
      <circle cx={cx} cy={cy} r={innerR + 1} fill="none" stroke="rgba(0,0,0,0.3)" strokeWidth={1} />

      {/* Wedges */}
      {wedges.map((w) => {
        const dimmed = hovered != null && hovered !== w.ticker;
        return (
          <path
            key={w.ticker}
            d={w.d}
            fill={`url(#grad-${w.ticker})`}
            className="transition-opacity duration-200 cursor-pointer"
            style={{
              opacity: dimmed ? 0.3 : 1,
              filter: dimmed ? "none" : "drop-shadow(0 1px 3px rgba(0,0,0,0.3))",
            }}
            onMouseEnter={() => onHover(w.ticker)}
            onMouseLeave={() => onHover(null)}
          >
            <title>{w.ticker} — {fmtDollarCompact(w.value)} ({(w.pct * 100).toFixed(1)}%)</title>
          </path>
        );
      })}

      {/* Center circle (dark background for text) */}
      <circle cx={cx} cy={cy} r={innerR - 2} fill="#111318" />
      <circle cx={cx} cy={cy} r={innerR - 2} fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth={1} />

      {/* Center text */}
      <text x={cx} y={cy - 10} textAnchor="middle" fill="#64748b" fontSize={10} fontFamily="ui-monospace, monospace" letterSpacing="0.05em">
        TOTAL VALUE
      </text>
      <text x={cx} y={cy + 14} textAnchor="middle" fill="#e2e8f0" fontSize={24} fontWeight={600} fontFamily="ui-monospace, monospace">
        {fmtDollarCompact(total)}
      </text>
    </svg>
  );
}

export default function Holdings({ holdings }: Props) {
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);
  const [hoveredTicker, setHoveredTicker] = useState<string | null>(null);

  const infoQueries = useQueries({
    queries: holdings.map((h) => ({
      queryKey: ["tickerInfo", h.ticker],
      queryFn: () => getTickerInfo(h.ticker),
      staleTime: 1000 * 60 * 60,
    })),
  });

  // Build enriched rows
  const rawRows = holdings.map((h, i) => {
    const info = infoQueries[i]?.data as Record<string, unknown> | undefined;
    const price = n(info?.currentPrice ?? info?.regularMarketPrice ?? info?.navPrice ?? info?.previousClose);
    const value = price != null ? price * h.shares : null;
    return { ...h, info, price, value, loading: infoQueries[i]?.isLoading ?? true };
  });

  // Sort by value descending — useMemo must be called before any early returns
  const rows = useMemo(
    () => [...rawRows].sort((a, b) => (b.value ?? 0) - (a.value ?? 0)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [JSON.stringify(rawRows.map((r) => [r.ticker, r.value]))],
  );

  if (holdings.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-slate-600">
        Add holdings above to see your portfolio.
      </div>
    );
  }

  const totalValue = rows.reduce((sum, r) => sum + (r.value ?? 0), 0);
  const allLoaded = rows.every((r) => !r.loading);

  // Donut slices — sorted, with colors assigned after sort
  const slices = rows
    .filter((r) => (r.value ?? 0) > 0)
    .map((r, i) => ({ ticker: r.ticker, value: r.value ?? 0, color: COLORS[i % COLORS.length] }));

  // Color lookup by ticker (based on sorted order)
  const colorMap: Record<string, string> = {};
  slices.forEach((s, i) => { colorMap[s.ticker] = COLORS[i % COLORS.length]; });

  return (
    <div className="space-y-6">
      {/* Summary card with donut */}
      <div className="glass-card">
        <div className="flex items-center justify-center">
          {/* Donut */}
          <div className="shrink-0">
            {allLoaded && totalValue > 0 ? (
              <DonutChart slices={slices} total={totalValue} hovered={hoveredTicker} onHover={setHoveredTicker} />
            ) : (
              <div className="flex h-[220px] w-[220px] items-center justify-center">
                <svg className="h-6 w-6 animate-spin text-slate-500" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              </div>
            )}
          </div>

          {/* Legend: left column = 1..half, right column = half+1..N */}
          <div className="flex gap-8">
            <div className="mb-3 text-[10px] font-medium uppercase tracking-wider text-slate-500">
              {holdings.length} holding{holdings.length !== 1 ? "s" : ""}
            </div>
            <div className="flex gap-20">
              {[slices.slice(0, Math.ceil(slices.length / 2)), slices.slice(Math.ceil(slices.length / 2))].map((col, ci) => (
                <div key={ci} className="flex flex-col gap-1.5">
                  {col.map((s, si) => {
                    const idx = ci === 0 ? si + 1 : Math.ceil(slices.length / 2) + si + 1;
                    const dimmed = hoveredTicker != null && hoveredTicker !== s.ticker;
                    return (
                      <div key={s.ticker} className="flex items-center gap-1.5 text-[12px]">
                        <span className="w-4 text-right font-mono text-[10px] text-slate-600">{idx}</span>
                        <span
                          className="inline-flex items-center gap-1.5 cursor-pointer transition-opacity duration-200"
                          style={{ opacity: dimmed ? 0.3 : 1 }}
                          onMouseEnter={() => setHoveredTicker(s.ticker)}
                          onMouseLeave={() => setHoveredTicker(null)}
                        >
                          <span className="inline-block h-2.5 w-2.5 rounded-full shrink-0" style={{ backgroundColor: s.color }} />
                          <span className="font-mono font-semibold text-slate-200">{s.ticker}</span>
                          <span className="text-slate-500">{fmtDollarCompact(s.value)}</span>
                          <span className="text-slate-600">{(s.value / totalValue * 100).toFixed(1)}%</span>
                        </span>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Holdings table — sorted by value desc */}
      <div className="glass-card">
        <h2 className="section-title mb-3">Positions</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/[0.06] text-[10px] font-medium tracking-wider text-slate-500">
              <th className="pb-2 text-left font-medium">Stock</th>
              <th className="pb-2 text-right font-medium">Price</th>
              <th className="pb-2 text-right font-medium">Shares</th>
              <th className="pb-2 text-right font-medium">Value</th>
              <th className="pb-2 text-right font-medium">Weight</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const pct = totalValue > 0 ? (r.value ?? 0) / totalValue : 0;
              const isExpanded = expandedTicker === r.ticker;
              const name = (r.info?.shortName ?? r.info?.longName ?? "") as string;
              const color = colorMap[r.ticker] ?? COLORS[0];

              return (
                <Fragment key={r.ticker}>
                  <tr
                    className={`border-b border-white/[0.04] cursor-pointer transition-colors hover:bg-white/[0.03] ${isExpanded ? "bg-white/[0.03]" : ""}`}
                    onClick={() => setExpandedTicker(isExpanded ? null : r.ticker)}
                  >
                    <td className="py-3">
                      <div className="flex items-center gap-2">
                        <div className="h-2.5 w-2.5 rounded-full shrink-0" style={{ backgroundColor: color }} />
                        <div>
                          <span className="font-mono font-semibold text-slate-100">{r.ticker}</span>
                          {name && <span className="ml-2 text-xs text-slate-500">{name}</span>}
                        </div>
                      </div>
                    </td>
                    <td className="py-3 text-right font-mono text-slate-300">
                      {r.loading ? "..." : fmtDollar(r.price)}
                    </td>
                    <td className="py-3 text-right font-mono text-slate-300">
                      {fmtNum(r.shares, r.shares % 1 === 0 ? 0 : 2)}
                    </td>
                    <td className="py-3 text-right font-mono font-medium text-slate-100">
                      {r.loading ? "..." : fmtDollarCompact(r.value)}
                    </td>
                    <td className="py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <div className="h-1.5 w-14 overflow-hidden rounded-full bg-white/[0.06]">
                          <div
                            className="h-full rounded-full transition-all duration-300"
                            style={{ width: `${pct * 100}%`, backgroundColor: color }}
                          />
                        </div>
                        <span className="w-10 text-right font-mono text-xs text-slate-400">
                          {fmtPct(pct, 1)}
                        </span>
                      </div>
                    </td>
                  </tr>

                  {isExpanded && r.info && (
                    <tr className="border-b border-white/[0.04] bg-white/[0.02]">
                      <td colSpan={5} className="px-4 py-4">
                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
                          <Stat label="Sector" value={(r.info.sector as string) ?? "—"} />
                          <Stat label="Industry" value={(r.info.industry as string) ?? "—"} />
                          <Stat label="Market Cap" value={fmtDollarCompact(n(r.info.marketCap))} />
                          <Stat label="P/E" value={fmtNum(n(r.info.trailingPE))} />
                          <Stat label="Fwd P/E" value={fmtNum(n(r.info.forwardPE))} />
                          <Stat label="PEG" value={fmtNum(n(r.info.trailingPegRatio))} />
                          <Stat label="Div Yield" value={fmtPct(n(r.info.dividendYield))} />
                          <Stat label="ROE" value={fmtPct(n(r.info.returnOnEquity))} />
                          <Stat label="Net Margin" value={fmtPct(n(r.info.profitMargins))} />
                          <Stat label="D/E" value={fmtNum(n(r.info.debtToEquity))} />
                          <Stat label="52w Low" value={fmtDollar(n(r.info.fiftyTwoWeekLow))} />
                          <Stat label="52w High" value={fmtDollar(n(r.info.fiftyTwoWeekHigh))} />
                        </div>
                        {(r.info.longBusinessSummary as string | undefined) && (
                          <p className="mt-3 line-clamp-3 text-xs leading-relaxed text-slate-500">
                            {r.info.longBusinessSummary as string}
                          </p>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
          {allLoaded && (
            <tfoot>
              <tr className="border-t border-white/[0.08]">
                <td className="py-3 font-medium text-slate-300">Total</td>
                <td />
                <td />
                <td className="py-3 text-right font-mono font-bold text-slate-100">{fmtDollarCompact(totalValue)}</td>
                <td />
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-white/[0.04] px-3 py-2">
      <div className="text-[10px] text-slate-600">{label}</div>
      <div className="mt-0.5 font-mono text-xs text-slate-200">{value}</div>
    </div>
  );
}
