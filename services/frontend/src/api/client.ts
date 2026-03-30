const BASE = "";

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// --- Types ---

export interface Holding {
  ticker: string;
  shares: number;
}

export interface PortfolioAnalysis {
  risk: Record<string, number>;
  mctr: Record<string, { mctr: number; pct_contribution: number }>;
  hedging: { portfolio_beta: number; correlation_clusters: (string | number)[][] };
  stress: Record<string, { return_pct: number; dollars: number }>;
  holdings_quality: { ticker: string; quality_score?: number; garp_score?: number; thesis_health?: Record<string, unknown> }[];
  internal_betas: Record<string, number>;
  weights: Record<string, number>;
  portfolio_value: number;
  skipped_tickers: string[];
  recommendations: Recommendation[];
}

export interface Recommendation {
  type: "add" | "trim" | "exit" | "rebalance" | "context";
  ticker: string | null;
  action: string;
  reason: string;
  evidence: Record<string, number | string | null>;
  priority: "high" | "medium" | "low";
}

export interface CandidateAnalysis {
  risk: {
    baseline: Record<string, number>;
    with_candidate: Record<string, number>;
    delta: Record<string, number>;
  };
  candidate_metrics: Record<string, unknown>;
  stress: Record<string, { baseline: Record<string, number>; with_candidate: Record<string, number> }>;
  candidate_quality: Record<string, unknown>;
  optimal_allocation: {
    optimal_shares: number;
    optimal_weight: number;
    optimal_score: number;
    reasoning: string;
    composite_breakdown: Record<string, number>;
    all_trials: { weight: number; shares: number; composite_score: number; volatility: number; sharpe: number; internal_beta: number; correlation: number }[];
  };
  effective_shares: number;
  candidate_price: number;
}

export interface PortfolioProfile {
  fundamentals: Record<string, number | null>;
  holdings_quality: { ticker: string; quality_score?: number; garp_score?: number }[];
  concentration: {
    sectors: Record<string, number>;
    countries: Record<string, number>;
    currencies: Record<string, number>;
    hhi: number;
    top_holding_pct: number;
  };
  frontier: {
    portfolio_position: { volatility: number; historical_return: number } | null;
    min_variance_point: { volatility: number; historical_return: number } | null;
    frontier_points: { volatility: number; historical_return: number }[];
    individual_holdings: { ticker: string; volatility: number; historical_return: number }[];
  };
  weights: Record<string, number>;
}

export interface CorrelationMatrix {
  matrix: Record<string, Record<string, number>>;
  tickers: string[];
}

export interface ScreenerResult {
  ticker: string;
  quality_score: number;
  garp_score: number;
  cheap_quality_score: number;
  forward_pe: number | null;
  peg_ratio: number | null;
  sector: string | null;
}

// --- API calls ---

export async function analyzePortfolio(portfolio: Holding[], period = "5y", age?: number): Promise<PortfolioAnalysis> {
  const body: Record<string, unknown> = { portfolio, period };
  if (age != null) body.age = age;
  return fetchJson(`${BASE}/api/risk/analyze-portfolio`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function analyzeCandidate(
  portfolio: Holding[],
  candidate: { ticker: string; shares_to_add?: number },
  period = "5y",
): Promise<CandidateAnalysis> {
  return fetchJson(`${BASE}/api/risk/analyze-candidate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ portfolio, candidate, period }),
  });
}

export async function getPortfolioProfile(holdings: Holding[], period = "5y"): Promise<PortfolioProfile> {
  return fetchJson(`${BASE}/api/portfolio/profile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ holdings, period }),
  });
}

export async function getCorrelation(tickers: string[], period = "5y"): Promise<CorrelationMatrix> {
  const params = new URLSearchParams();
  tickers.forEach((t) => params.append("tickers", t));
  params.set("period", period);
  return fetchJson(`${BASE}/api/portfolio/correlation?${params}`);
}

export async function getScreenerStream(
  limit = 20,
  minQuality = 50,
  universes: string[] = ["us"],
  onProgress?: (pct: number, phase: string) => void,
): Promise<ScreenerResult[]> {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("min_quality", String(minQuality));
  for (const u of universes) params.append("universe", u);

  const res = await fetch(`${BASE}/api/market-data/screener/cheap-quality?${params}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: ScreenerResult[] | null = null;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Parse SSE events from buffer
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      let eventType = "";
      let data = "";
      for (const line of part.split("\n")) {
        if (line.startsWith("event: ")) eventType = line.slice(7);
        else if (line.startsWith("data: ")) data = line.slice(6);
      }
      if (!data) continue;
      if (eventType === "progress" && onProgress) {
        const p = JSON.parse(data) as { pct: number; phase: string };
        onProgress(p.pct, p.phase);
      } else if (eventType === "result") {
        result = JSON.parse(data) as ScreenerResult[];
      }
    }
  }

  return result ?? [];
}

export interface SectorImpactResult {
  sector: string;
  sector_etf: string | null;
  scenario_move: number;
  portfolio_exposure: {
    sector_weight: number;
    portfolio_beta_to_sector: number;
    projected_portfolio_impact: number;
    projected_dollar_impact: number;
  };
  affected_holdings: {
    ticker: string;
    sector: string;
    weight: number;
    beta_to_sector_etf: number;
    projected_loss: number;
    projected_loss_dollars: number;
  }[];
  unaffected_holdings: {
    ticker: string;
    sector: string;
    weight: number;
    correlation_to_sector: number;
  }[];
}

export async function getSectorImpact(
  portfolio: Holding[],
  sector: string,
  scenarioMove: number,
  period = "5y",
): Promise<SectorImpactResult> {
  return fetchJson(`${BASE}/api/risk/sector-impact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ portfolio, sector, scenario_move: scenarioMove, period }),
  });
}

export async function getTickerInfo(ticker: string): Promise<Record<string, unknown>> {
  return fetchJson(`${BASE}/api/market-data/tickers/${ticker}/info`);
}

export async function getBatchBeta(
  portfolio: Holding[],
  candidates: string[],
  period = "5y",
): Promise<Record<string, { internal_beta: number; correlation: number }>> {
  return fetchJson(`${BASE}/api/risk/batch-beta`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ portfolio, candidates, period }),
  });
}

export async function getRecommendations(holdings: Holding[], period = "5y"): Promise<Recommendation[]> {
  const data = await fetchJson<{ recommendations: Recommendation[] }>(`${BASE}/api/risk/recommendations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ portfolio: holdings, period }),
  });
  return data.recommendations;
}
