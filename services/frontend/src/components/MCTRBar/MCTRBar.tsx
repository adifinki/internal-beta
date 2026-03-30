import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import InfoTooltip from "../InfoTooltip";
import { CHART_COLORS, CHART_TOOLTIP_STYLE } from "../../utils/colors";

interface Props {
  mctr: Record<string, { mctr: number; pct_contribution: number }>;
}

export default function MCTRBar({ mctr }: Props) {
  const data = Object.entries(mctr)
    .map(([ticker, v]) => ({
      ticker,
      pct: +(v.pct_contribution * 100).toFixed(2),
      mctr: +v.mctr.toFixed(4),
    }))
    .sort((a, b) => b.pct - a.pct);

  return (
    <div className="glass-card flex h-full flex-col">
      <h2 className="section-title mb-3">
        Marginal Contribution to Risk
        <InfoTooltip metricKey="mctr_section" />
      </h2>
      <ResponsiveContainer width="100%" height={Math.max(200, data.length * 36)}>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 20, bottom: 0, left: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            tickFormatter={(v: number) => `${v}%`}
          />
          <YAxis
            type="category"
            dataKey="ticker"
            tick={{ fill: "#e2e8f0", fontSize: 12, fontFamily: "monospace" }}
            width={50}
          />
          <Tooltip
            contentStyle={CHART_TOOLTIP_STYLE}
            formatter={(value: number, name: string) => {
              if (name === "pct") return [`${value.toFixed(2)}%`, "Contribution"];
              return [value, name];
            }}
            labelStyle={{ color: "#e2e8f0", fontFamily: "monospace" }}
          />
          <Bar dataKey="pct" name="pct" radius={[0, 4, 4, 0]}>
            {data.map((_, i) => (
              <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
