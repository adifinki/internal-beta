import type { CandidateAnalysis as CandidateAnalysisData } from "../../api/client";
import InfoTooltip from "../InfoTooltip";
import { fmtMetric, titleize } from "../../utils/format";
import { betaCardStyle, betaVerdict, deltaColor } from "../../utils/colors";
import { RISK_LABELS } from "../../utils/labels";

interface Props {
  data: CandidateAnalysisData;
}

export default function CandidateAnalysis({ data }: Props) {
  const { risk, candidate_metrics: cm } = data;
  // Cast to a looser type so we can access nested objects safely
  const candidate_metrics = cm as Record<string, number | Record<string, number>>;
  const HIDDEN_RISK_KEYS = new Set(["var_95", "cvar_95", "sortino", "sortino_reliable"]);
  const riskKeys = Object.keys(risk.baseline).filter(
    (k) => typeof risk.baseline[k] === "number" && !HIDDEN_RISK_KEYS.has(k),
  );

  return (
    <div className="space-y-6">
      {/* Internal Beta — THE hero, first thing you see */}
      {(() => {
        const betaNum = typeof candidate_metrics.internal_beta === "number" ? candidate_metrics.internal_beta as number : null;
        const corrNum = typeof candidate_metrics.correlation_to_portfolio === "number" ? candidate_metrics.correlation_to_portfolio as number : null;
        const style = betaNum !== null ? betaCardStyle(betaNum) : { border: "border-white/[0.04]", bg: "bg-white/[0.02]", text: "text-slate-500" };
        const verdict = betaNum !== null ? betaVerdict(betaNum) : "";

        return (
          <div className={`rounded-2xl border ${style.border} ${style.bg} p-6`} style={{ backdropFilter: "blur(16px)" }}>
            <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="metric-label">
                  Internal Beta
                  <InfoTooltip metricKey="internal_beta" />
                </div>
                <div className="mt-2 text-5xl font-semibold tracking-tight gradient-text">
                  {betaNum !== null ? betaNum.toFixed(2) : "--"}
                </div>
                <div className={`mt-3 text-sm font-medium ${style.text}`}>
                  {verdict}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="glass-surface px-4 py-3 text-center">
                  <div className="metric-label">Correlation</div>
                  <div className="mt-2 text-xl font-medium tracking-tight text-slate-200">
                    {corrNum !== null ? corrNum.toFixed(2) : "--"}
                  </div>
                  <div className="mt-1 text-[10px] text-slate-600">
                    {corrNum !== null
                      ? corrNum < 0.3 ? "Strong diversifier"
                      : corrNum < 0.6 ? "Some diversification"
                      : corrNum < 0.8 ? "Limited diversification"
                      : "Moves in lockstep"
                      : ""}
                  </div>
                </div>
                <div className="glass-surface px-4 py-3 text-center">
                  <div className="metric-label">MCTR</div>
                  <div className="mt-2 text-xl font-medium tracking-tight text-slate-200">
                    {typeof candidate_metrics.mctr_contribution === "number"
                      ? (candidate_metrics.mctr_contribution as number).toFixed(4)
                      : "--"}
                  </div>
                  <div className="mt-1 text-[10px] text-slate-600">
                    Risk contribution
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Risk Comparison */}
      <div className="glass-card">
        <h2 className="section-title">
          Risk Comparison
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.06] text-xs text-slate-400">
                <th className="pb-2 text-left font-medium">Metric</th>
                <th className="pb-2 text-right font-medium">Before</th>
                <th className="pb-2 text-right font-medium">After</th>
                <th className="pb-2 text-right font-medium">Delta</th>
              </tr>
            </thead>
            <tbody>
              {riskKeys.map((key) => {
                const baseline = risk.baseline[key] ?? 0;
                const after = risk.with_candidate[key] ?? 0;
                const delta = risk.delta[key] ?? 0;
                return (
                  <tr key={key} className="border-b border-white/[0.04] row-hover transition-colors">
                    <td className="py-2 text-slate-300">
                      {RISK_LABELS[key] ?? titleize(key)}
                      <InfoTooltip metricKey={key} />
                    </td>
                    <td className="py-2 text-right font-mono text-slate-300">
                      {fmtMetric(key, baseline)}
                    </td>
                    <td className="py-2 text-right font-mono text-slate-100">
                      {fmtMetric(key, after)}
                    </td>
                    <td className={`py-2 text-right font-mono font-semibold ${deltaColor(key, delta)}`}>
                      {delta > 0 ? "+" : ""}
                      {fmtMetric(key, delta)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Correlation to each holding */}
      {candidate_metrics.correlation_to_each &&
        typeof candidate_metrics.correlation_to_each === "object" && (
          <div className="glass-card">
            <h2 className="section-title">
              Correlation to Each Holding
            </h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {Object.entries(
                candidate_metrics.correlation_to_each as Record<string, number>,
              ).map(([ticker, corr]) => (
                <div key={ticker} className="glass-surface p-3 text-center">
                  <div className="text-xs text-slate-400">{ticker}</div>
                  <div className="mt-1 text-lg font-bold text-slate-100">
                    {typeof corr === "number" ? corr.toFixed(4) : "--"}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

    </div>
  );
}
