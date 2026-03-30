/** Centralized metric labels — single source of truth. */

export const RISK_LABELS: Record<string, string> = {
  sharpe: "Sharpe Ratio",
  sortino: "Sortino",
  volatility: "Volatility",
  annual_return: "Annual Return",
  var_95: "VaR (95%)",
  cvar_95: "CVaR (95%)",
  max_drawdown_pct: "Max Drawdown",
  max_drawdown_dollars: "Drawdown ($)",
  recovery_days: "Recovery Days",
};
