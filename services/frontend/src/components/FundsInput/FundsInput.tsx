import { useQuery } from "@tanstack/react-query";
import { getFundsCatalog } from "../../api/client";
import type { UnmappedRow, SelectionCoverage } from "../../api/client";

export const FUND_CATEGORIES = ["pension", "kupat_gemel_lehashkaa", "keren_hishtalmut"] as const;
export type FundCategory = (typeof FUND_CATEGORIES)[number];

const CATEGORY_LABELS: Record<FundCategory, string> = {
  pension: "Pension",
  kupat_gemel_lehashkaa: "Kupat Gemel LeHashkaa",
  keren_hishtalmut: "Keren Hishtalmut",
};

export interface FundSlotState {
  companyId: string;
  trackId: string;
  amountUsd: string;
}

export const EMPTY_FUND_SLOT: FundSlotState = { companyId: "", trackId: "", amountUsd: "" };

interface Props {
  slots: Record<FundCategory, FundSlotState>;
  onChange: (category: FundCategory, slot: FundSlotState) => void;
  unmapped: UnmappedRow[];
  coverage: SelectionCoverage[];
  holdingsError: boolean;
  holdingsLoading: boolean;
}

export default function FundsInput({ slots, onChange, unmapped, coverage, holdingsError, holdingsLoading }: Props) {
  const {
    data: catalog,
    isError: catalogError,
  } = useQuery({
    queryKey: ["fundsCatalog"],
    queryFn: getFundsCatalog,
    staleTime: Infinity,
  });

  return (
    <div className="space-y-4">
      {catalogError && (
        <div className="rounded-xl border border-red-500/20 bg-red-950/10 px-4 py-2.5 text-xs text-red-300">
          Couldn't load the fund catalog. Try refreshing the page.
        </div>
      )}

      {holdingsLoading && (
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-2.5 text-xs text-slate-400">
          Updating fund holdings...
        </div>
      )}

      {holdingsError && (
        <div className="rounded-xl border border-red-500/20 bg-red-950/10 px-4 py-2.5 text-xs text-red-300">
          Couldn't load your fund holdings. They aren't contributing to your portfolio right now - try again.
        </div>
      )}

      {FUND_CATEGORIES.map((category) => {
        const categoryData = catalog?.categories.find((c) => c.category === category);
        const slot = slots[category];
        const company = categoryData?.companies.find((c) => c.company_id === slot.companyId);

        return (
          <div key={category} className="glass-card">
            <h3 className="section-title mb-3">{CATEGORY_LABELS[category]}</h3>
            <div className="flex flex-col gap-3 sm:flex-row">
              <select
                value={slot.companyId}
                onChange={(e) => onChange(category, { companyId: e.target.value, trackId: "", amountUsd: slot.amountUsd })}
                className="flex-1 rounded-xl bg-white/[0.03] border border-white/[0.04] px-4 py-2.5 text-sm text-slate-200 outline-none transition-all duration-200 focus:border-white/[0.08]"
              >
                <option value="">Select company</option>
                {categoryData?.companies.map((c) => (
                  <option key={c.company_id} value={c.company_id}>{c.company_name}</option>
                ))}
              </select>
              <select
                value={slot.trackId}
                disabled={!company}
                onChange={(e) => onChange(category, { ...slot, trackId: e.target.value })}
                className="flex-1 rounded-xl bg-white/[0.03] border border-white/[0.04] px-4 py-2.5 text-sm text-slate-200 outline-none transition-all duration-200 focus:border-white/[0.08] disabled:opacity-40"
              >
                <option value="">Select fund track</option>
                {company?.tracks.map((t) => (
                  <option key={t.track_id} value={t.track_id}>{t.track_name}</option>
                ))}
              </select>
              <input
                type="number"
                min={0}
                placeholder="Amount (USD)"
                value={slot.amountUsd}
                onChange={(e) => onChange(category, { ...slot, amountUsd: e.target.value })}
                className="w-full sm:w-40 rounded-xl bg-white/[0.03] border border-white/[0.04] px-4 py-2.5 text-sm text-slate-200 placeholder-slate-600 outline-none transition-all duration-200 focus:border-white/[0.08] font-mono"
              />
            </div>
          </div>
        );
      })}

      {unmapped.length > 0 && (
        <div className="rounded-xl border border-amber-500/20 bg-amber-950/10 px-4 py-2.5 text-xs text-slate-400 space-y-1.5">
          <div>
            <span className="font-medium text-amber-300">Not counted toward stock holdings: </span>
            {unmapped.map((u, i) => (
              <span key={i}>
                {i > 0 && ", "}
                {(u.pct_of_fund * 100).toFixed(1)}% {u.label} ({u.company_name} - {u.track_name})
              </span>
            ))}
            {" "}- no tradeable proxy exists for these positions yet.
          </div>
          {coverage.length > 0 && (
            <div className="border-t border-amber-500/10 pt-1.5">
              {coverage.map((c, i) => {
                const pct = c.total_pct > 0 ? (c.mapped_pct / c.total_pct) * 100 : 0;
                return (
                  <div key={i}>
                    {pct.toFixed(0)}% of {c.company_name} - {c.track_name}'s disclosed allocation has a tradeable
                    proxy - ${c.mapped_amount_usd.toFixed(0)} of your ${c.amount_usd.toFixed(0)} contributes to your
                    holdings; the rest is shown above.
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
