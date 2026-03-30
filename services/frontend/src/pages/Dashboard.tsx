import { useQuery } from "@tanstack/react-query";
import type { Holding } from "../api/client";
import { analyzePortfolio, getPortfolioProfile, getCorrelation } from "../api/client";
import InfoTooltip from "../components/InfoTooltip";
import CorrelationMatrix from "../components/CorrelationMatrix/CorrelationMatrix";
import EfficientFrontier from "../components/EfficientFrontier/EfficientFrontier";
import ConcentrationChart from "../components/ConcentrationChart/ConcentrationChart";
import QualityDashboard from "../components/QualityDashboard/QualityDashboard";
import MCTRBar from "../components/MCTRBar/MCTRBar";
import DrawdownChart from "../components/DrawdownChart/DrawdownChart";
import Recommendations from "../components/Recommendations/Recommendations";
import SectorImpact from "../components/SectorImpact/SectorImpact";
import { fmtMetric, titleize } from "../utils/format";
import { RISK_LABELS } from "../utils/labels";

interface Props {
  holdings: Holding[];
  age: number | null;
}

export default function Dashboard({ holdings, age }: Props) {
  const tickers = holdings.map((h) => h.ticker);
  const enabled = holdings.length >= 2;

  const analysisQuery = useQuery({
    queryKey: ["analyzePortfolio", holdings, age],
    queryFn: () => analyzePortfolio(holdings, "5y", age ?? undefined),
    enabled,
  });

  const profileQuery = useQuery({
    queryKey: ["portfolioProfile", holdings],
    queryFn: () => getPortfolioProfile(holdings),
    enabled,
  });

  const correlationQuery = useQuery({
    queryKey: ["correlation", tickers],
    queryFn: () => getCorrelation(tickers),
    enabled,
  });

  if (!enabled) {
    return (
      <div className="flex h-64 items-center justify-center text-slate-600">
        Add at least 2 holdings to view your portfolio dashboard.
      </div>
    );
  }

  const isLoading = analysisQuery.isLoading || profileQuery.isLoading || correlationQuery.isLoading;
  const error = analysisQuery.error || profileQuery.error || correlationQuery.error;

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-sm text-slate-500">Loading portfolio analysis...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="glass-card text-sm text-red-400">
          Error: {error instanceof Error ? error.message : "Failed to load data"}
        </div>
      </div>
    );
  }

  const analysis = analysisQuery.data;
  const profile = profileQuery.data;
  const correlation = correlationQuery.data;

  return (
    <div className="space-y-6">
      {/* Skipped tickers warning */}
      {analysis && analysis.skipped_tickers?.length > 0 && (
        <div className="rounded-2xl border border-amber-500/20 bg-amber-950/10 px-5 py-3 text-xs text-slate-400">
          <span className="font-medium text-amber-300">No market data: </span>
          {analysis.skipped_tickers.join(", ")} — these tickers were excluded from the analysis. Try an equivalent ticker listed on Yahoo Finance.
        </div>
      )}

      {/* Top metrics row */}
      {analysis && (
        <div className="grid grid-cols-3 gap-4 stagger-children">
          {Object.entries(analysis.risk)
            .filter(([key]) => !key.includes("drawdown") && key !== "recovery_days" && key !== "sortino_reliable" && key !== "var_95" && key !== "cvar_95" && key !== "sortino")
            .map(([key, value]) => (
              <div key={key} className="glass-card glass-card-hover px-4 py-5">
                <div className="metric-label">
                  {RISK_LABELS[key] ?? titleize(key)}
                  <InfoTooltip metricKey={key} />
                </div>
                <div className="mt-3 text-[22px] font-medium tracking-tight gradient-text">
                  {fmtMetric(key, value)}
                </div>
              </div>
            ))}
        </div>
      )}

      {/* MCTR + Correlation row */}
      <div className="grid grid-cols-2 gap-6 stagger-children">
        {analysis && <MCTRBar mctr={analysis.mctr} />}
        {correlation && <CorrelationMatrix data={correlation} />}
      </div>

      {/* Efficient Frontier + Concentration row */}
      <div className="grid grid-cols-2 gap-6 stagger-children">
        {profile && <EfficientFrontier frontier={profile.frontier} />}
        {profile && <ConcentrationChart concentration={profile.concentration} />}
      </div>

      {/* Quality Dashboard */}
      {analysis && profile && (
        <QualityDashboard
          holdings_quality={analysis.holdings_quality}
          portfolio_quality_score={profile.fundamentals.portfolio_quality_score ?? undefined}
          portfolio_garp_score={profile.fundamentals.portfolio_garp_score ?? undefined}
          mctr={analysis.mctr}
          internal_betas={analysis.internal_betas}
          weights={analysis.weights}
          correlation_clusters={analysis.hedging.correlation_clusters}
        />
      )}

      {/* Drawdown */}
      <div className="grid grid-cols-1 gap-6 stagger-children">
        {analysis && (
          <DrawdownChart
            max_drawdown_pct={analysis.risk.max_drawdown_pct ?? 0}
            max_drawdown_dollars={analysis.risk.max_drawdown_dollars ?? 0}
            recovery_days={analysis.risk.recovery_days ?? 0}
          />
        )}
      </div>

      {/* Sector scenario — "What if Technology drops 20%?" */}
      <SectorImpact holdings={holdings} />

      {/* Recommendations — Bogle + Buffett principles applied to this portfolio */}
      {(analysis?.recommendations?.length ?? 0) > 0 && (
        <Recommendations recommendations={analysis!.recommendations} />
      )}
    </div>
  );
}
