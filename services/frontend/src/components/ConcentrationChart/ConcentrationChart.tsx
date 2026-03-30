import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import type { PortfolioProfile } from "../../api/client";
import InfoTooltip from "../InfoTooltip";

interface Props {
  concentration: PortfolioProfile["concentration"];
}

const SECTOR_COLORS = [
  "#b0a0c0", "#c4a0a8", "#8a8cb0", "#a890a8", "#9098b8",
  "#bca0b8", "#7e86a8", "#c0a8b8", "#9a8aaa", "#a898b8",
  "#8890a4", "#b8a0b0",
];

const COUNTRY_COLORS = [
  "#6e7a8a", "#586878", "#7a8896", "#4e5e6e", "#8892a0",
  "#5a6a7a", "#6a7888", "#50606e", "#7e8a98", "#566676",
  "#748290", "#5e6e7e",
];

function toEntries(record: Record<string, number>) {
  return Object.entries(record)
    .map(([name, value]) => ({ name, value: +(value * 100).toFixed(1) }))
    .sort((a, b) => b.value - a.value);
}

const TOOLTIP_STYLE = {
  backgroundColor: "#1a1d24",
  border: "1px solid rgba(255,255,255,0.12)",
  borderRadius: 10,
  fontSize: 12,
  color: "#e2e8f0",
  padding: "8px 12px",
};

function PieLegend({ entries, colors }: { entries: { name: string; value: number }[]; colors: string[] }) {
  return (
    <div className="mt-2 flex flex-wrap justify-center gap-x-3 gap-y-1">
      {entries.map((e, i) => (
        <span key={e.name} className="flex items-center gap-1 text-[10px] text-slate-400">
          <span
            className="inline-block h-2 w-2 shrink-0 rounded-full"
            style={{ backgroundColor: colors[i % colors.length] }}
          />
          {e.name}
        </span>
      ))}
    </div>
  );
}

export default function ConcentrationChart({ concentration }: Props) {
  const sectors = toEntries(concentration.sectors);
  const countries = toEntries(concentration.countries);

  return (
    <div className="glass-card flex h-full flex-col">
      <h2 className="section-title mb-3">
        Concentration
        <InfoTooltip metricKey="concentration_section" />
      </h2>
      <div className="grid flex-1 grid-cols-2 gap-4">
        {/* Sectors */}
        <div className="flex flex-col items-center">
          <h3 className="mb-1 text-xs font-medium text-slate-400">Sectors</h3>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie
                data={sectors}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={80}
                innerRadius={36}
                paddingAngle={1}
                stroke="none"
              >
                {sectors.map((_, i) => (
                  <Cell key={i} fill={SECTOR_COLORS[i % SECTOR_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                itemStyle={{ color: "#e2e8f0" }}
                formatter={(value: number) => `${value}%`}
              />
            </PieChart>
          </ResponsiveContainer>
          <PieLegend entries={sectors} colors={SECTOR_COLORS} />
        </div>

        {/* Countries */}
        <div className="flex flex-col items-center">
          <h3 className="mb-1 text-xs font-medium text-slate-400">Countries</h3>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie
                data={countries}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={80}
                innerRadius={36}
                paddingAngle={1}
                stroke="none"
              >
                {countries.map((_, i) => (
                  <Cell key={i} fill={COUNTRY_COLORS[i % COUNTRY_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                itemStyle={{ color: "#e2e8f0" }}
                formatter={(value: number) => `${value}%`}
              />
            </PieChart>
          </ResponsiveContainer>
          <PieLegend entries={countries} colors={COUNTRY_COLORS} />
        </div>
      </div>

      {/* HHI + Top Holding */}
      <div className="mt-4 flex justify-center gap-8 text-sm">
        <div className="text-center">
          <span className="text-slate-400">HHI <InfoTooltip metricKey="hhi" />: </span>
          <span className="font-semibold text-slate-100">{(concentration.hhi * 10000).toFixed(0)}</span>
          <span className="ml-1 text-xs text-slate-500">(10k = concentrated)</span>
        </div>
        <div className="text-center">
          <span className="text-slate-400">Top Holding <InfoTooltip metricKey="top_holding" />: </span>
          <span className="font-semibold text-slate-100">
            {(concentration.top_holding_pct * 100).toFixed(1)}%
          </span>
        </div>
      </div>
    </div>
  );
}
