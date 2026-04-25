import { createContext, useContext, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getScreenerStream } from "../api/client";
import type { ScreenerResult } from "../api/client";

interface ScreenerContextValue {
  data: ScreenerResult[] | undefined;
  progress: { pct: number; phase: string } | null;
  isLoading: boolean;
  error: Error | null;
  minQuality: number;
  setMinQuality: (v: number) => void;
  universes: string[];
  start: () => void;
}

const ScreenerContext = createContext<ScreenerContextValue | null>(null);

const UNIVERSES = ["us", "us_extra", "israel", "europe", "emerging"];

export function ScreenerProvider({ children }: { children: React.ReactNode }) {
  const [started, setStarted] = useState(false);
  const [minQuality, setMinQuality] = useState(80);
  const [progress, setProgress] = useState<{ pct: number; phase: string } | null>(null);

  const progressRef = useRef<(v: { pct: number; phase: string } | null) => void>(() => {});
  progressRef.current = setProgress;

  const cacheKey = `screener:${minQuality}:${UNIVERSES.join(",")}`;

  const query = useQuery({
    queryKey: ["screener", minQuality, UNIVERSES],
    queryFn: () => {
      const cached = sessionStorage.getItem(cacheKey);
      if (cached) return Promise.resolve(JSON.parse(cached) as ScreenerResult[]);

      progressRef.current({ pct: 0, phase: "info" });
      return getScreenerStream(200, minQuality, UNIVERSES, (pct, phase) => {
        progressRef.current({ pct, phase });
      }).then((results) => {
        sessionStorage.setItem(cacheKey, JSON.stringify(results));
        return results;
      }).finally(() => progressRef.current(null));
    },
    enabled: started,
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });

  return (
    <ScreenerContext.Provider value={{
      data: query.data,
      progress,
      isLoading: query.isLoading && query.fetchStatus !== "idle",
      error: query.error as Error | null,
      minQuality,
      setMinQuality: (v) => { setMinQuality(v); setStarted(true); },
      universes: UNIVERSES,
      start: () => setStarted(true),
    }}>
      {children}
    </ScreenerContext.Provider>
  );
}

export function useScreener() {
  const ctx = useContext(ScreenerContext);
  if (!ctx) throw new Error("useScreener must be used within ScreenerProvider");
  return ctx;
}
