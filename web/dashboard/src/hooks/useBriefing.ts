import { useQuery } from "@tanstack/react-query";

import { resolveApiBase } from "@/lib/apiBase";

export type BriefingItem = {
  title: string;
  summary?: string | null;
  ticker?: string | null;
  targetUrl?: string | null;
};

export type BriefingPayload = {
  id: string;
  sourceType: string;
  generatedAt?: string | null;
  title?: string | null;
  summary?: string | null;
  items: BriefingItem[];
  meta?: unknown;
};

async function fetchBriefing(): Promise<BriefingPayload> {
  const baseUrl = resolveApiBase();
  const response = await fetch(`${baseUrl}/api/v1/proactive-insights`, {
    credentials: "include",
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`failed to load briefing (${response.status})`);
  }
  return (await response.json()) as BriefingPayload;
}

export function useBriefing() {
  return useQuery<BriefingPayload, Error>({
    queryKey: ["briefing", "latest"],
    queryFn: fetchBriefing,
    staleTime: 60_000,
    retry: false,
  });
}
