"use client";

import { useEffect, useState } from "react";
import { ThesisUiState, defaultThesisUiState } from "@/types/thesis";

export function useThesisState(intervalMs: number = 1000) {
  const [data, setData] = useState<ThesisUiState>(defaultThesisUiState);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function fetchState() {
    try {
      const res = await fetch("/api/state", { cache: "no-store" });

      if (!res.ok) {
        throw new Error(`Failed to fetch state: ${res.status}`);
      }

      const json = await res.json();
      setData(json);
      setError(null);
    } catch (err) {
      console.error("Error fetching thesis state:", err);
      setError("Unable to load backend state");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchState();
    const id = setInterval(fetchState, intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);

  return { data, loading, error };
}