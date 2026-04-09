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
  /** Optional: portfolio position after adding a candidate. Rendered as an orange dot. */
  candidatePosition?: { volatility: number; historical_return: number };
  /** Optional: frontier computed with the candidate stock included in the universe. */
  candidateFrontier?: PortfolioProfile["frontier"];
}

// Deconflict label positions: if two dots are close, push the later one's label below.
const OVERLAP_THRESHOLD_X = 5; // % points
const OVERLAP_THRESHOLD_Y = 8; // % points

function computeLabelOffsets(holdings: { x: number; y: number }[]): number[] {
  const offsets = holdings.map(() => -14); // default: above
  for (let i = 0; i < holdings.length; i++) {
    for (let j = 0; j < i; j++) {
      if (
        Math.abs(holdings[i].x - holdings[j].x) < OVERLAP_THRESHOLD_X &&
        Math.abs(holdings[i].y - holdings[j].y) < OVERLAP_THRESHOLD_Y
      ) {
        offsets[i] = 20; // below
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

export default function EfficientFrontier({ frontier, candidatePosition, candidateFrontier }: Props) {
  const { frontier_points, portfolio_position, min_variance_point, individual_holdings } = frontier;

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

  return (
    <div className="glass-card flex h-full flex-col">
      <h2 className="section-title mb-3">
        Efficient Frontier
        <InfoTooltip metricKey="efficient_frontier" />
      </h2>
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart margin={{ top: 5, right: 20, bottom: 35, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis type="number" dataKey="x" domain={["auto", "auto"]} tick={{ fill: "#94a3b8", fontSize: 11 }}>
            <Label value="Volatility (%)" position="bottom" offset={10} style={{ fill: "#94a3b8", fontSize: 11 }} />
          </XAxis>
          <YAxis type="number" dataKey="y" domain={["auto", "auto"]} tick={{ fill: "#94a3b8", fontSize: 11 }}>
            <Label value="Return (%)" angle={-90} position="insideLeft" offset={-5} style={{ fill: "#94a3b8", fontSize: 11 }} />
          </YAxis>
          <Tooltip
            contentStyle={{ backgroundColor: "#111318", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, fontSize: 12 }}
            labelStyle={{ color: "#e2e8f0" }}
            formatter={(value: number, name: string) => [`${value.toFixed(2)}%`, name]}
          />
          <Legend
            verticalAlign="top"
            align="center"
            wrapperStyle={{ fontSize: 11, paddingBottom: 15 }}
          />

          {/* Expanded frontier (with candidate) — rendered first so baseline draws on top */}
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

          {/* Frontier curve — monotone gives smooth interpolation between points */}
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

          {/* Individual holdings with inline deconflicted ticker labels */}
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

          {/* Min variance */}
          {minVarData.length > 0 && (
            <Scatter data={minVarData} fill="#4a9e6d" name="Min Variance" legendType="circle" />
          )}

          {/* Current portfolio — rendered after min variance so it's visible when overlapping */}
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

          {/* Portfolio with candidate — wired from CandidateAnalysis tab */}
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
    </div>
  );
}
