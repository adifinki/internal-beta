import type { PortfolioProfile } from "../../api/client";
import InfoTooltip from "../InfoTooltip";

type Concentration = PortfolioProfile["concentration"];

interface Props {
  before: Concentration;
  after: Concentration;
  candidateTicker: string;
}

function Row({ label, bVal, aVal }: { label: string; bVal: number; aVal: number }) {
  const delta = aVal - bVal;
  const isNew = bVal === 0 && aVal > 0;
  return (
    <div className="flex items-center justify-between py-1 border-b border-white/[0.02] last:border-0">
      <span className="text-slate-400 text-xs">{label}</span>
      <span className="font-mono text-xs">
        <span className="text-slate-500">{bVal === 0 ? "—" : `${bVal.toFixed(1)}%`}</span>
        <span className="text-slate-600 mx-1.5">→</span>
        <span className="text-slate-200">{aVal === 0 ? "—" : `${aVal.toFixed(1)}%`}</span>
        <span className={`ml-2 w-14 inline-block text-right ${
          isNew ? "text-blue-400" : delta > 0.5 ? "text-amber-400" : delta < -0.5 ? "text-emerald-400" : "text-slate-600"
        }`}>
          {isNew ? "+new" : `${delta > 0 ? "+" : ""}${delta.toFixed(1)}`}
        </span>
      </span>
    </div>
  );
}

function Category({ title, before, after }: { title: string; before: Record<string, number>; after: Record<string, number> }) {
  const keys = Array.from(new Set([...Object.keys(before), ...Object.keys(after)]));
  keys.sort((a, b) => (after[b] ?? 0) - (after[a] ?? 0));
  return (
    <div className="glass-surface">
      <div className="metric-label mb-2">{title}</div>
      {keys.map((k) => <Row key={k} label={k} bVal={(before[k] ?? 0) * 100} aVal={(after[k] ?? 0) * 100} />)}
    </div>
  );
}

export default function ConcentrationDelta({ before, after }: Props) {
  return (
    <div className="glass-card">
      <h2 className="section-title">
        Concentration Impact <InfoTooltip metricKey="concentration_section" />
      </h2>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Category title="Sectors" before={before.sectors} after={after.sectors} />
        <Category title="Countries" before={before.countries} after={after.countries} />
        <Category title="Currencies" before={before.currencies} after={after.currencies} />
      </div>
    </div>
  );
}
