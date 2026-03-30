import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Holding } from "../api/client";
import { analyzeCandidate, getPortfolioProfile } from "../api/client";
import CandidateAnalysisComponent from "../components/CandidateAnalysis/CandidateAnalysis";
import ConcentrationDelta from "../components/ConcentrationDelta/ConcentrationDelta";
import EfficientFrontier from "../components/EfficientFrontier/EfficientFrontier";

interface Props {
  holdings: Holding[];
  candidateTicker: string;
  sharesOverride: number | null;
  onOptimalComputed: (shares: number) => void;
}

export default function Analysis({ holdings, candidateTicker, sharesOverride, onOptimalComputed }: Props) {
  const ticker = candidateTicker.trim().toUpperCase();
  const enabled = holdings.length >= 1 && ticker.length > 0;

  // Fetch analysis — if sharesOverride is null, backend computes optimal
  const query = useQuery({
    queryKey: ["analyzeCandidate", holdings, ticker, sharesOverride],
    queryFn: () =>
      analyzeCandidate(
        holdings,
        sharesOverride != null ? { ticker, shares_to_add: sharesOverride } : { ticker },
      ),
    enabled,
  });

  // When optimal is computed, push the value up so the input field shows it
  useEffect(() => {
    if (query.data?.optimal_allocation?.optimal_shares != null && sharesOverride === null) {
      onOptimalComputed(query.data.optimal_allocation.optimal_shares);
    }
  }, [query.data, sharesOverride, onOptimalComputed]);

  const profileQuery = useQuery({
    queryKey: ["portfolioProfile", holdings],
    queryFn: () => getPortfolioProfile(holdings),
    enabled: holdings.length >= 2,
  });

  // Build with-candidate holdings for concentration comparison
  const effectiveShares = query.data?.effective_shares ?? sharesOverride ?? 0;
  const withCandidateHoldings = useMemo(() => {
    if (!ticker || effectiveShares <= 0) return null;
    const existing = holdings.find((h) => h.ticker === ticker);
    if (existing) {
      return holdings.map((h) =>
        h.ticker === ticker ? { ...h, shares: h.shares + effectiveShares } : h,
      );
    }
    return [...holdings, { ticker, shares: effectiveShares }];
  }, [holdings, ticker, effectiveShares]);

  const withCandidateProfileQuery = useQuery({
    queryKey: ["portfolioProfile:withCandidate", withCandidateHoldings],
    queryFn: () => getPortfolioProfile(withCandidateHoldings!),
    enabled: withCandidateHoldings != null && withCandidateHoldings.length >= 2,
  });

  if (!enabled) {
    return (
      <div className="flex h-64 items-center justify-center text-slate-600">
        Enter a candidate ticker to analyze.
      </div>
    );
  }

  if (query.isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-sm text-slate-500">
          {sharesOverride != null ? "Recalculating..." : "Computing optimal allocation..."}
        </div>
      </div>
    );
  }

  if (query.error) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="glass-card text-sm text-red-400">
          Error: {query.error instanceof Error ? query.error.message : "Failed to analyze candidate"}
        </div>
      </div>
    );
  }

  if (!query.data) return null;

  const data = query.data;

  const candidatePosition =
    data.risk.with_candidate.volatility != null && data.risk.with_candidate.annual_return != null
      ? {
          volatility: data.risk.with_candidate.volatility,
          historical_return: data.risk.with_candidate.annual_return,
        }
      : undefined;

  return (
    <div className="space-y-6 fade-in">
      {profileQuery.data && (
        <EfficientFrontier
          frontier={profileQuery.data.frontier}
          candidatePosition={candidatePosition}
          candidateFrontier={withCandidateProfileQuery.data?.frontier}
        />
      )}
      <CandidateAnalysisComponent data={data} />

      {/* Concentration before/after */}
      {profileQuery.data && withCandidateProfileQuery.data && (
        <ConcentrationDelta
          before={profileQuery.data.concentration}
          after={withCandidateProfileQuery.data.concentration}
          candidateTicker={ticker}
        />
      )}
    </div>
  );
}
