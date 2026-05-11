import { useEffect, useRef, useState } from "react";
import { searchTickers, type TickerSearchResult } from "../api/client";

export function useTickerSearch(query: string) {
  const [results, setResults] = useState<TickerSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    // Clear previous timer
    if (timerRef.current) clearTimeout(timerRef.current);
    // Abort previous in-flight request
    if (abortRef.current) abortRef.current.abort();

    if (query.trim().length < 2) {
      setResults([]);
      setLoading(false);
      return;
    }

    setLoading(true);

    timerRef.current = setTimeout(async () => {
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const data = await searchTickers(query.trim(), controller.signal);
        setResults(data);
      } catch {
        // AbortError (user typed more) or network error — both are silent
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (abortRef.current) abortRef.current.abort();
    };
  }, [query]);

  return { results, loading };
}
