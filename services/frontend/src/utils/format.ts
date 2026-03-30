/**
 * Centralized formatting utilities.
 * Every number display in the app should use one of these.
 */

export function fmtPct(value: number | null | undefined, decimals = 2): string {
  if (value == null || !isFinite(value)) return "—";
  return `${(value * 100).toFixed(decimals)}%`;
}

export function fmtDollar(value: number | null | undefined): string {
  if (value == null || !isFinite(value)) return "—";
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(2)}M`;
  return `${sign}$${abs.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export function fmtDollarCompact(value: number | null | undefined): string {
  if (value == null || !isFinite(value)) return "—";
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(1)}T`;
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(1)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

export function fmtNum(value: number | null | undefined, decimals = 2): string {
  if (value == null || !isFinite(value)) return "—";
  return value.toFixed(decimals);
}

export function fmtScore(value: number | null | undefined): string {
  if (value == null) return "—";
  return value.toFixed(0);
}

/** Format a risk metric by its key name. */
export function fmtMetric(key: string, value: unknown): string {
  if (value == null || typeof value !== "number" || !isFinite(value)) return "—";
  if (key.includes("pct") || key === "volatility" || key === "annual_return" || key === "max_drawdown")
    return fmtPct(value);
  if (key.includes("dollar") || key === "var_95" || key === "cvar_95")
    return fmtDollar(value);
  if (key === "recovery_days") return `${Math.round(value)}`;
  if (key === "sharpe" || key === "sortino") return fmtNum(value, 3);
  return fmtNum(value);
}

/** Format a multiplier (e.g. P/B ratio) as "1.23x". */
export function fmtMultiple(value: number | null | undefined): string {
  if (value == null || !isFinite(value)) return "—";
  return `${value.toFixed(2)}x`;
}

/** snake_case to Title Case. */
export function titleize(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
