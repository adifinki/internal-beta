import { useRef, useState, useMemo } from "react";
import {
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Label,
  Line,
  ComposedChart,
} from "recharts";
import type { PortfolioProfile } from "../../api/client";
import InfoTooltip from "../InfoTooltip";

interface Props {
  frontier: PortfolioProfile["frontier"];
  candidatePosition?: { volatility: number; historical_return: number };
  candidateFrontier?: PortfolioProfile["frontier"];
}

const OVERLAP_THRESHOLD_X = 5;
const OVERLAP_THRESHOLD_Y = 8;

function computeLabelOffsets(holdings: { x: number; y: number }[]): number[] {
  const offsets = holdings.map(() => -14);
  for (let i = 0; i < holdings.length; i++) {
    for (let j = 0; j < i; j++) {
      if (
        Math.abs(holdings[i].x - holdings[j].x) < OVERLAP_THRESHOLD_X &&
        Math.abs(holdings[i].y - holdings[j].y) < OVERLAP_THRESHOLD_Y
      ) {
        offsets[i] = 20;
        break;
      }
    }
  }
  return offsets;
}

interface HoldingDotProps {
  cx: number;
  cy: number;
  fill: string;
  ticker: string;
  labelDy: number;
}

function HoldingDot({ cx, cy, fill, ticker, labelDy }: HoldingDotProps) {
  return (
    <g>
      <circle cx={cx} cy={cy} r={5} fill={fill} />
      <text
        x={cx}
        y={cy + labelDy}
        textAnchor="middle"
        fill="#94a3b8"
        fontSize={10}
        fontFamily="ui-monospace, monospace"
      >
        {ticker}
      </text>
    </g>
  );
}

const CHART_MARGIN = { top: 5, right: 20, bottom: 35, left: 20 };
const CHART_HEIGHT = 400;
const TOOLTIP_W = 180;

interface HoverInfo {
  name: string;
  x: number;
  y: number;
  px: number;
  py: number;
}

export default function EfficientFrontier({ frontier, candidatePosition, candidateFrontier }: Props) {
  const { frontier_points, portfolio_position, min_variance_point, individual_holdings } = frontier;
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoverInfo, setHoverInfo] = useState<HoverInfo | null>(null);

  const frontierData = frontier_points.map((p) => ({
    x: +(p.volatility * 100).toFixed(2),
    y: +(p.historical_return * 100).toFixed(2),
  }));

  const expandedFrontierData = candidateFrontier?.frontier_points.map((p) => ({
    x: +(p.volatility * 100).toFixed(2),
    y: +(p.historical_return * 100).toFixed(2),
  }));

  const rawHoldings = individual_holdings.map((h) => ({
    x: +(h.volatility * 100).toFixed(2),
    y: +(h.historical_return * 100).toFixed(2),
    ticker: h.ticker,
  }));

  const labelOffsets = computeLabelOffsets(rawHoldings);
  const holdingData = rawHoldings.map((h, i) => ({ ...h, labelDy: labelOffsets[i] }));

  const portfolioData = portfolio_position
    ? [{ x: +(portfolio_position.volatility * 100).toFixed(2), y: +(portfolio_position.historical_return * 100).toFixed(2) }]
    : [];

  const minVarData = min_variance_point
    ? [{ x: +(min_variance_point.volatility * 100).toFixed(2), y: +(min_variance_point.historical_return * 100).toFixed(2) }]
    : [];

  const candidateData = candidatePosition
    ? [{ x: +(candidatePosition.volatility * 100).toFixed(2), y: +(candidatePosition.historical_return * 100).toFixed(2) }]
    : [];

  // All named data points for hover magnetizing
  const allPoints = useMemo(() => {
    const pts: Array<{ name: string; x: number; y: number }> = [];
    frontierData.forEach((p) => pts.push({ name: "Current Frontier", ...p }));
    expandedFrontierData?.forEach((p) => pts.push({ name: "Frontier with Candidate", ...p }));
    holdingData.forEach((h) => pts.push({ name: h.ticker, x: h.x, y: h.y }));
    if (portfolioData.length) pts.push({ name: candidateData.length ? "Portfolio (without candidate)" : "Portfolio", ...portfolioData[0] });
    if (candidateData.length) pts.push({ name: "Portfolio (with candidate)", ...candidateData[0] });
    if (minVarData.length) pts.push({ name: "Min Variance", ...minVarData[0] });
    return pts;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [frontierData.length, expandedFrontierData?.length, holdingData.length, portfolioData.length, candidateData.length, minVarData.length]);

  function handleMouseMove(event: React.MouseEvent<HTMLDivElement>) {
    if (!containerRef.current || allPoints.length === 0) { setHoverInfo(null); return; }

    const rect = containerRef.current.getBoundingClientRect();
    const containerW = rect.width;

    // Data extent across all points
    const xs = allPoints.map((p) => p.x);
    const ys = allPoints.map((p) => p.y);
    const xMin = Math.min(...xs), xMax = Math.max(...xs);
    const yMin = Math.min(...ys), yMax = Math.max(...ys);
    // Add ~5% padding on each side (matches recharts auto domain)
    const xPad = (xMax - xMin) * 0.05 || 1;
    const yPad = (yMax - yMin) * 0.05 || 1;
    const xLo = xMin - xPad, xHi = xMax + xPad;
    const yLo = yMin - yPad, yHi = yMax + yPad;

    // Chart area pixel bounds within the container
    const left = CHART_MARGIN.left;
    const right = containerW - CHART_MARGIN.right;
    const top = CHART_MARGIN.top;
    const bottom = CHART_HEIGHT - CHART_MARGIN.bottom;

    const toPixelX = (v: number) => left + (v - xLo) / (xHi - xLo) * (right - left);
    const toPixelY = (v: number) => bottom - (v - yLo) / (yHi - yLo) * (bottom - top);

    // Cursor relative to container
    const cx = event.clientX - rect.left;
    const cy = event.clientY - rect.top;

    let minDist = Infinity;
    let best: HoverInfo | null = null;

    for (const pt of allPoints) {
      const px = toPixelX(pt.x);
      const py = toPixelY(pt.y);
      const d = (cx - px) ** 2 + (cy - py) ** 2;
      if (d < minDist) {
        minDist = d;
        best = { name: pt.name, x: pt.x, y: pt.y, px, py };
      }
    }

    setHoverInfo(minDist < 1600 ? best : null); // 40px radius
  }

  // Tooltip positioning: clamp to stay on screen
  const tooltipLeft = hoverInfo
    ? Math.max(4, Math.min(hoverInfo.px - TOOLTIP_W / 2, (containerRef.current?.offsetWidth ?? 600) - TOOLTIP_W - 4))
    : 0;
  const tooltipAbove = hoverInfo ? hoverInfo.py > 70 : true;

  return (
    <div className="glass-card flex h-full flex-col">
      <h2 className="section-title mb-3">
        Efficient Frontier
        <InfoTooltip metricKey="efficient_frontier" />
      </h2>
      <div
        ref={containerRef}
        className="relative"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoverInfo(null)}
      >
        <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
          <ComposedChart margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis type="number" dataKey="x" domain={["auto", "auto"]} tick={{ fill: "#94a3b8", fontSize: 11 }}>
              <Label value="Volatility (%)" position="bottom" offset={10} style={{ fill: "#94a3b8", fontSize: 11 }} />
            </XAxis>
            <YAxis type="number" dataKey="y" domain={["auto", "auto"]} tick={{ fill: "#94a3b8", fontSize: 11 }}>
              <Label value="Return (%)" angle={-90} position="insideLeft" offset={-5} style={{ fill: "#94a3b8", fontSize: 11 }} />
            </YAxis>
            <Tooltip content={() => null} cursor={false} />
            <Legend
              verticalAlign="top"
              align="center"
              wrapperStyle={{ fontSize: 11, paddingBottom: 15 }}
            />

            {expandedFrontierData && (
              <Line
                type="monotone"
                data={expandedFrontierData}
                dataKey="y"
                stroke="#d4a574"
                strokeWidth={2}
                strokeDasharray="8 4"
                dot={false}
                name="Frontier with Candidate"
                legendType="line"
              />
            )}

            <Line
              type="monotone"
              data={frontierData}
              dataKey="y"
              stroke="#7c8cc8"
              strokeWidth={2}
              dot={false}
              name="Current Frontier"
              legendType="line"
            />

            <Scatter
              data={holdingData}
              fill="#64748b"
              name="Holdings"
              legendType="circle"
              shape={(props: unknown) => {
                const p = props as HoldingDotProps;
                return <HoldingDot cx={p.cx} cy={p.cy} fill={p.fill} ticker={p.ticker} labelDy={p.labelDy} />;
              }}
            />

            {minVarData.length > 0 && (
              <Scatter data={minVarData} fill="#4a9e6d" name="Min Variance" legendType="circle" />
            )}

            {portfolioData.length > 0 && (
              <Scatter
                data={portfolioData}
                fill="#5b8def"
                name="Portfolio"
                legendType="circle"
                shape={(props: unknown) => {
                  const { cx, cy } = props as { cx: number; cy: number };
                  return <circle cx={cx} cy={cy} r={8} fill="#5b8def" stroke="#111318" strokeWidth={2} />;
                }}
              />
            )}

            {candidateData.length > 0 && (
              <Scatter
                data={candidateData}
                fill="#d4a574"
                name="Portfolio with Candidate"
                legendType="circle"
                shape={(props: unknown) => {
                  const { cx, cy } = props as { cx: number; cy: number };
                  return <circle cx={cx} cy={cy} r={8} fill="#d4a574" stroke="#111318" strokeWidth={2} />;
                }}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>

        {/* Hover highlight ring + tooltip */}
        {hoverInfo && (
          <>
            <svg
              style={{ position: "absolute", left: 0, top: 0, width: "100%", height: CHART_HEIGHT, pointerEvents: "none" }}
            >
              <circle
                cx={hoverInfo.px}
                cy={hoverInfo.py}
                r={9}
                fill="none"
                stroke="rgba(255,255,255,0.35)"
                strokeWidth={2}
              />
            </svg>
            <div
              style={{
                position: "absolute",
                left: tooltipLeft,
                top: tooltipAbove ? hoverInfo.py - 12 : hoverInfo.py + 12,
                transform: tooltipAbove ? "translateY(-100%)" : undefined,
                width: TOOLTIP_W,
                pointerEvents: "none",
                zIndex: 50,
                backgroundColor: "#111318",
                border: "1px solid rgba(255,255,255,0.08)",
                borderRadius: 8,
                padding: "8px 12px",
                fontSize: 12,
              }}
            >
              <div style={{ color: "#e2e8f0", fontWeight: 500, marginBottom: 4 }}>{hoverInfo.name}</div>
              <div style={{ color: "#94a3b8" }}>
                Volatility: <span style={{ color: "#e2e8f0", fontFamily: "monospace" }}>{hoverInfo.x.toFixed(2)}%</span>
              </div>
              <div style={{ color: "#94a3b8" }}>
                Return: <span style={{ color: "#e2e8f0", fontFamily: "monospace" }}>{hoverInfo.y.toFixed(2)}%</span>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
