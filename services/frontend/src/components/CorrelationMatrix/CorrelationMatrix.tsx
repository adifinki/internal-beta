import type { CorrelationMatrix as CorrelationMatrixData } from "../../api/client";
import InfoTooltip from "../InfoTooltip";

interface Props {
  data: CorrelationMatrixData;
}

/**
 * Continuous gradient from green (diversifying) → neutral → red (concentrated).
 * Maps correlation [-1, +1] to a smooth color scale.
 */
function correlationStyle(v: number, isDiagonal: boolean): React.CSSProperties {
  if (isDiagonal) return { backgroundColor: "rgba(51,65,85,0.4)", color: "rgb(100,116,139)" };

  // Color scale anchored to what matters for PORTFOLIO DIVERSIFICATION:
  //   v ≤ 0.0  → bright green   (hedge / great diversifier)
  //   v = 0.4  → neutral gray   (acceptable, midpoint)
  //   v ≥ 0.75 → strong red     (highly correlated, problematic)
  //
  // Map v → [0,1] using 0.4 as the neutral midpoint:
  //   norm = 0 at v = -1 (full green)
  //   norm = 0.5 at v = 0.4 (neutral)
  //   norm = 1 at v = 1 (full red)
  const t = Math.max(-1, Math.min(1, v));
  const norm = (t + 1) / (2 * 1.4); // remap: -1→0, 0.4→0.5, 1→0.714... then clamp
  const n = Math.min(1, norm);       // clamp so v > 0.8 stays fully red

  let r: number, g: number, b: number, a: number;
  if (n <= 0.5) {
    // Green zone: vivid emerald (v=-1) → transparent gray (v=0.4)
    const p = n / 0.5;
    r = Math.round(5  + p * (30 - 5));
    g = Math.round(210 + p * (41 - 210));
    b = Math.round(110 + p * (55 - 110));
    a = 0.75 - p * 0.45;  // 0.75 at v=-1, 0.30 at v=0.4
  } else {
    // Red zone: transparent gray (v=0.4) → vivid red (v=1)
    const p = (n - 0.5) / 0.5;
    r = Math.round(60  + p * (220 - 60));   // 60 → 220 (bright red)
    g = Math.round(41  + p * (30  - 41));
    b = Math.round(55  + p * (30  - 55));
    a = 0.20 + p * 0.65;  // 0.20 at v=0.4, 0.85 at v=1 — strong red
  }

  const textColor =
    n <= 0.30 ? "rgb(52,211,153)"   // emerald-400: v ≤ 0.0
    : n >= 0.68 ? "rgb(252,165,165)" // red-300: v ≥ 0.7
    : "rgb(148,163,184)";            // slate-400: neutral zone

  return {
    backgroundColor: `rgba(${r},${g},${b},${a})`,
    color: textColor,
    fontWeight: (v >= 0.75 || v <= -0.3) ? 600 : 400,
  };
}

export default function CorrelationMatrix({ data }: Props) {
  const { tickers, matrix } = data;

  return (
    <div className="glass-card flex h-full flex-col">
      <h2 className="section-title mb-3">
        Correlation Matrix
        <InfoTooltip metricKey="correlation_matrix" />
      </h2>
      <div className="flex-1 overflow-x-auto">
        <table className="text-sm" style={{ minWidth: "max-content", margin: tickers.length <= 5 ? "0 auto" : undefined }}>
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-[#111318] p-2" />
              {tickers.map((t) => (
                <th key={t} className="px-3 pb-3 font-mono font-medium text-slate-400 text-center">
                  {t}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tickers.map((row) => (
              <tr key={row}>
                <td className="sticky left-0 z-10 bg-[#111318] pr-4 py-2 font-mono font-medium text-slate-400 text-right">{row}</td>
                {tickers.map((col) => {
                  const val = matrix[row]?.[col] ?? 0;
                  const diag = row === col;
                  return (
                    <td
                      key={col}
                      className="px-3 py-2.5 text-center font-mono rounded-lg"
                      style={correlationStyle(val, diag)}
                    >
                      {val.toFixed(2)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex flex-col items-center gap-1">
        <div
          className="h-2 w-48 rounded-full"
          style={{ background: "linear-gradient(to right, rgba(5,210,110,0.75), rgba(30,41,55,0.28) 57%, rgba(140,20,20,0.75))" }}
        />
        <div className="flex w-48 justify-between text-[10px] text-slate-500">
          <span>Diversifying</span>
          <span>Neutral</span>
          <span>Concentrated</span>
        </div>
      </div>
    </div>
  );
}
