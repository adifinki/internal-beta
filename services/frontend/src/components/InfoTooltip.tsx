import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

const TOOLTIPS: Record<string, { desc: string; range: string; use: string }> = {
  sharpe: {
    desc: "Sharpe Ratio: risk-adjusted return = (return - risk-free rate) / volatility.",
    range: "Typically -1 to 3. Above 1.0 is good, above 2.0 is excellent.",
    use: "Higher is better. More return per unit of risk.",
  },
  sortino: {
    desc: "Sortino Ratio: like Sharpe, but only penalizes downside volatility (bad surprises), not upside. (return - risk-free rate) / downside deviation.",
    range: "Above 1.0 is good, above 2.0 is excellent. Generally higher than Sharpe for the same portfolio.",
    use: "Higher is better. Preferred over Sharpe when you care only about downside risk, not upside swings.",
  },
  volatility: {
    desc: "Annualized standard deviation of portfolio returns.",
    range: "5%–40% for equity portfolios. S&P 500 ≈ 15%.",
    use: "Lower is better. Measures how much the portfolio bounces.",
  },
  annual_return: {
    desc: "Annualized portfolio return based on historical data.",
    range: "S&P 500 averages ~10% long-term.",
    use: "Higher is better, but must weigh against risk. This is backward-looking, not a prediction.",
  },
  var_95: {
    desc: "Value at Risk (95%): maximum expected daily loss, 95% of the time.",
    range: "A negative dollar amount. More negative = more risk.",
    use: "Less negative (closer to $0) is better.",
  },
  cvar_95: {
    desc: "Conditional VaR (Expected Shortfall): average loss in the worst 5% of days.",
    range: "Always more negative than VaR.",
    use: "Less negative is better. Shows how bad the tail really gets.",
  },
  max_drawdown_pct: {
    desc: "Largest peak-to-trough decline in portfolio value.",
    range: "0% to -100%. Equity portfolios typically see -20% to -50%.",
    use: "Closer to 0% is better. Shows worst historical pain.",
  },
  max_drawdown_dollars: {
    desc: "Max drawdown expressed in dollars.",
    range: "Depends on portfolio size.",
    use: "Smaller absolute value is better.",
  },
  recovery_days: {
    desc: "Trading days from the worst trough back to the previous peak.",
    range: "0 to hundreds of days. 2020 crash recovered in ~5 months.",
    use: "Fewer days is better. Shows how quickly you'd recover.",
  },
  internal_beta: {
    desc: "Internal Beta measures how this stock moves relative to YOUR specific portfolio, not the S&P 500. This is unique to your holdings. β=1 means it moves 1:1 with your portfolio. β=0.5 means half the movement. β<0 means it moves opposite (natural hedge).",
    range: "β < 0 = hedge (rare, very valuable). β 0–0.5 = strong diversifier. β 0.5–0.8 = moderate. β 0.8–1.2 = moves with portfolio. β > 1.2 = amplifies risk.",
    use: "Lower β = more diversification benefit. Negative β hedges your portfolio.",
  },
  mctr_contribution: {
    desc: "Marginal Contribution to Risk: how much risk this position adds to the portfolio.",
    range: "0 to ~0.3 (as a decimal).",
    use: "Lower is better. A high MCTR means this stock is a big risk driver.",
  },
  correlation_to_portfolio: {
    desc: "Pearson correlation between the candidate's returns and your portfolio's returns.",
    range: "-1 (opposite) to +1 (identical movement). 0 = unrelated.",
    use: "Lower (or negative) = more diversification. Above 0.8 = barely diversifying.",
  },
  stress_comparison: {
    desc: "How your portfolio would have performed during real historical crashes, with and without the candidate.",
    range: "Shows return (%) and dollar loss for each scenario.",
    use: "Green delta = the candidate would have softened the blow. Red = would have made it worse.",
  },
  "2020_crash": {
    desc: "Feb 19 – Mar 23, 2020. COVID panic triggered the fastest bear market in history. S&P 500 fell ~34% in one month.",
    range: "Most equity portfolios lost 20%–40%.",
    use: "Tests how your portfolio handles a sudden, violent sell-off.",
  },
  "2022_shock": {
    desc: "Jan – Dec 2022. The Fed hiked rates aggressively to fight inflation. S&P 500 dropped ~19% over the year.",
    range: "Growth and tech stocks were hit hardest (some -50%+).",
    use: "Tests how your portfolio handles a slow, grinding downturn driven by rising rates.",
  },
  return_pct: {
    desc: "Your portfolio's total return during this stress window.",
    range: "Typically negative. More negative = bigger loss.",
    use: "Less negative (closer to 0%) is better.",
  },
  dollars: {
    desc: "Dollar loss on your portfolio during this stress window.",
    range: "Depends on portfolio size. Typically a large negative number.",
    use: "Smaller loss is better. Compare before vs. after adding the candidate.",
  },

  age_horizon: {
    desc: "Time-horizon guidance based on your age. The investment strategy for a 27-year-old (38-year runway) should look nothing like strategy at 60.",
    range: "Growth (<35): max equity, compound quality. Accumulation (35-49): equity-heavy, add ballast. Pre-retirement (50-59): protect capital. Distribution (60+): income + preservation.",
    use: "Use this as a sanity check: if the age-appropriate allocation differs significantly from yours, understand why before deviating.",
  },

  // --- Dashboard-specific tooltips ---
  mctr_section: {
    desc: "Marginal Contribution to Risk shows which holdings drive your portfolio's volatility. MCTR = (Σ·w)_i / σ.",
    range: "Bar length = % of total portfolio risk attributable to that holding.",
    use: "If one holding dominates the bar chart, it's your biggest risk driver. Consider trimming or diversifying.",
  },
  correlation_matrix: {
    desc: "Pairwise correlation between all your holdings. Shows how they move together.",
    range: "-1 (opposite) to +1 (identical). Red = highly correlated = low diversification.",
    use: "Red cells mean those two holdings provide little diversification benefit. Look for green/neutral pairs.",
  },
  efficient_frontier: {
    desc: "The curve of all optimal risk/return portfolios based on historical data. Shows where your portfolio sits.",
    range: "X-axis = volatility (risk), Y-axis = historical return. Closer to the curve = more efficient.",
    use: "If your portfolio dot is far below the curve, you're taking more risk than necessary for your return. This is backward-looking, not a prediction.",
  },
  concentration_section: {
    desc: "How your portfolio weight is distributed across sectors and countries.",
    range: "Each slice = % of portfolio. Larger slice = more concentrated.",
    use: "High concentration in one sector/country means you're exposed to sector-specific risks. Diversify if one sector > 40%.",
  },
  hhi: {
    desc: "Herfindahl-Hirschman Index: sum of squared position weights. Measures how concentrated your positions are.",
    range: "0 (infinitely diversified) to 10,000 (single stock). Below 1,500 = diversified, above 2,500 = concentrated.",
    use: "Lower is better. If HHI is high, your portfolio depends too much on a few holdings.",
  },
  top_holding: {
    desc: "Weight of your single largest position.",
    range: "0%–100%. Above 20% is a concentration flag.",
    use: "If one stock is >25% of your portfolio, a bad quarter for that stock hits your entire portfolio hard.",
  },
  quality_section: {
    desc: "Quality scores measure business fundamentals: ROIC, margins, FCF, earnings consistency, debt health.",
    range: "0–100. Above 70 = high quality, below 40 = low quality.",
    use: "High quality + low valuation (GARP) = the best candidates for long-term compounding.",
  },
  garp_section: {
    desc: "Growth At a Reasonable Price score. Measures if you're paying a fair price for growth (PEG, forward P/E, earnings growth).",
    range: "0–100. Above 70 = attractively priced growth. Below 30 = expensive for the growth offered.",
    use: "High GARP score means the market isn't fully pricing in the growth. Look for quality > 70 AND GARP > 60.",
  },
  thesis_status: {
    desc: "Standalone assessment of the business based on quality score thresholds.",
    range: "Strong (≥70), Monitor (50–69), Review (30–49), Broken (<30).",
    use: "Evaluates the business on its own merits, ignoring how it fits your portfolio.",
  },
  portfolio_fit: {
    desc: "How this holding fits your portfolio, combining quality, GARP, risk contribution (MCTR), weight, and correlation to other holdings.",
    range: "Core (high quality + good value), Diversifier (low risk contribution), Overweight (too much weight/risk), Redundant (correlated cluster), Trim (low quality + high risk).",
    use: "Core = keep. Diversifier = valuable for risk reduction. Overweight = consider reducing. Redundant = overlapping exposure. Trim = sell candidate. Hover for details.",
  },
  stress_section: {
    desc: "How your portfolio would have performed during real historical market crashes.",
    range: "Return % and dollar loss for each scenario.",
    use: "Shows your worst-case exposure. If the loss is more than you can stomach, reduce risk.",
  },
  drawdown_section: {
    desc: "The largest peak-to-trough decline your portfolio experienced historically.",
    range: "Drawdown %: typically -15% to -50% for equity portfolios. Recovery: days to get back to the prior peak.",
    use: "Ask yourself: could I hold through this drawdown without panic selling? If not, reduce volatility.",
  },
  portfolio_beta: {
    desc: "Weighted average market beta of your portfolio. β=1 means it moves with the S&P 500.",
    range: "0.5 (defensive) to 1.5+ (aggressive). S&P 500 = 1.0 by definition.",
    use: "β > 1.2 = your portfolio amplifies market swings. β < 0.8 = more defensive than the market.",
  },
  cheap_quality: {
    desc: "Combined score: high quality business (ROIC, margins, FCF) at a cheap valuation (low PEG, forward P/E).",
    range: "0–100. Higher = better quality-to-price ratio.",
    use: "Sort by this to find the best bang-for-buck stocks. Look for scores above 60.",
  },
  forward_pe: {
    desc: "Forward Price-to-Earnings ratio based on analyst estimates for next 12 months.",
    range: "S&P 500 average ≈ 18–22. Below 15 = cheap, above 30 = expensive.",
    use: "Lower is cheaper. Compare within the same sector: tech runs higher than utilities.",
  },
  peg_ratio: {
    desc: "Price/Earnings to Growth ratio. P/E divided by expected earnings growth rate.",
    range: "Below 1.0 = undervalued for the growth. 1.0–2.0 = fairly priced. Above 2.0 = expensive.",
    use: "Lower is better. A PEG < 1 means you're paying less than the growth rate justifies.",
  },
  scenario_analysis: {
    desc: "Estimates how your portfolio would react if a sector or macro factor moves by a given amount. For each holding, we compute its historical beta against a sector ETF proxy (e.g. XLK for Technology, XLV for Healthcare, TLT for Interest Rates). The portfolio-level impact uses the portfolio's overall beta to the proxy — this captures cross-sector correlations (e.g. a Communication Services stock that moves with Tech).",
    range: "This is an estimate, not a prediction. It assumes future correlations resemble the past, which may not hold during crises or regime changes. The sector ETF proxies are imperfect — individual stocks can behave differently from their sector. Use the per-holding breakdown to see which stocks drive the exposure.",
    use: "Use this to stress-test concentration you can't see. You may think you're diversified across sectors, but if all your holdings are correlated to Tech, a Tech crash hits your whole portfolio. Try different scenarios to find your blind spots.",
  },
  cheap_quality_screener: {
    desc: "Scans S&P 400 stocks for the intersection of high business quality (ROIC, margins, FCF, earnings consistency) and low valuation (PEG, forward P/E). These are stocks the market may be underpricing relative to their fundamentals.",
    range: "Results are sorted by a composite cheap-quality score (0–100). Higher = better quality-to-price ratio.",
    use: "Use this as a discovery tool: find candidates here, then analyze them against your portfolio in the Candidate Analysis tab. The Int. Beta column shows how each stock moves relative to your portfolio (lower = better diversifier).",
  },
};

const TOOLTIP_WIDTH = 288; // w-72
const TOOLTIP_GAP = 8; // mb-2

interface TooltipPos {
  top: number;
  left: number;
  above: boolean;
}

interface Props {
  metricKey: string;
}

export default function InfoTooltip({ metricKey }: Props) {
  const info = TOOLTIPS[metricKey];
  const iconRef = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState<TooltipPos | null>(null);

  useEffect(() => {
    if (!pos) return;
    function hide() {
      setPos(null);
    }
    window.addEventListener("scroll", hide, { passive: true });
    return () => window.removeEventListener("scroll", hide);
  }, [pos]);

  if (!info) return null;

  function showTooltip() {
    const rect = iconRef.current?.getBoundingClientRect();
    if (!rect) return;

    const above = rect.top > 160; // enough room above?
    let left = rect.left + rect.width / 2 - TOOLTIP_WIDTH / 2;
    // clamp so it stays inside the viewport
    left = Math.max(8, Math.min(left, window.innerWidth - TOOLTIP_WIDTH - 8));

    const top = above
      ? rect.top - TOOLTIP_GAP // will use translateY(-100%) in render
      : rect.bottom + TOOLTIP_GAP;

    setPos({ top, left, above });
  }

  const tooltip = pos
    ? createPortal(
        <div
          style={{
            position: "fixed",
            top: pos.above ? pos.top : pos.top,
            left: pos.left,
            width: TOOLTIP_WIDTH,
            transform: pos.above ? "translateY(-100%)" : undefined,
            zIndex: 9999,
            background: 'rgba(17,19,24,0.95)',
            backdropFilter: 'blur(20px)',
            border: '1px solid rgba(255,255,255,0.05)',
          }}
          className="rounded-2xl p-4 text-xs leading-relaxed text-slate-400 shadow-2xl tooltip-enter"
        >
          <p className="font-medium text-slate-300">{info.desc}</p>
          <p className="mt-2 text-slate-500">
            <span className="font-medium text-slate-400">Range:</span> {info.range}
          </p>
          <p className="mt-1 text-slate-500">
            <span className="font-medium text-slate-400">How to use:</span> {info.use}
          </p>
          <div
            className={`absolute left-1/2 -translate-x-1/2 border-4 border-transparent ${
              pos.above
                ? "top-full border-t-slate-800"
                : "bottom-full border-b-slate-800"
            }`}
          />
        </div>,
        document.body,
      )
    : null;

  return (
    <span
      className="ml-1.5 inline-flex cursor-help align-middle"
      onMouseEnter={showTooltip}
      onMouseLeave={() => setPos(null)}
    >
      <span
        ref={iconRef}
        className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full bg-white/[0.04] text-[9px] font-medium text-slate-600 hover:bg-white/[0.06] hover:text-slate-400 transition-all duration-200"
      >
        i
      </span>
      {tooltip}
    </span>
  );
}
