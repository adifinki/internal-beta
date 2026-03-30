import InfoTooltip from "../InfoTooltip";

interface Props {
  max_drawdown_pct: number;
  max_drawdown_dollars: number;
  recovery_days: number;
}

export default function DrawdownChart({ max_drawdown_pct, max_drawdown_dollars, recovery_days }: Props) {
  return (
    <div className="glass-card flex h-full flex-col">
      <h2 className="section-title mb-3">
        Maximum Drawdown
        <InfoTooltip metricKey="drawdown_section" />
      </h2>
      <div className="grid flex-1 grid-cols-3 items-center gap-3">
        <div className="glass-surface text-center">
          <div className="text-xs text-slate-400">
            Drawdown % <InfoTooltip metricKey="max_drawdown_pct" />
          </div>
          <div className="mt-1 text-2xl font-bold text-red-400">
            {(max_drawdown_pct * 100).toFixed(1)}%
          </div>
        </div>
        <div className="glass-surface text-center">
          <div className="text-xs text-slate-400">
            Dollar Loss <InfoTooltip metricKey="max_drawdown_dollars" />
          </div>
          <div className="mt-1 text-2xl font-bold text-red-400">
            -${Math.abs(max_drawdown_dollars).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
        </div>
        <div className="glass-surface text-center">
          <div className="text-xs text-slate-400">
            Recovery Days <InfoTooltip metricKey="recovery_days" />
          </div>
          <div className="mt-1 text-2xl font-bold text-blue-400">
            {recovery_days > 0 ? recovery_days : "--"}
          </div>
        </div>
      </div>
    </div>
  );
}
