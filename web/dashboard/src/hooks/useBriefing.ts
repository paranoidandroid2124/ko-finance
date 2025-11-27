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
  const response = await fetch(`${baseUrl}/api/v1/feed/proactive/briefings?limit=1`, {
    credentials: "include",
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`failed to load briefing (${response.status})`);
  }
  const data = await response.json();
  const first = Array.isArray(data?.items) && data.items.length > 0 ? data.items[0] : null;
  if (!first) {
    return { id: "", sourceType: "proactive", title: "", items: [] };
  }
  return {
    id: first.id ?? "",
    sourceType: "proactive",
    generatedAt: first.createdAt ?? null,
    title: first.title ?? "",
    summary: first.summary ?? null,
    items: Array.isArray(first.items) ? first.items : [],
    meta: first.meta ?? undefined,
  };
}

export function useBriefing() {
  return useQuery<BriefingPayload, Error>({
    queryKey: ["briefing", "latest"],
    queryFn: fetchBriefing,
    staleTime: 60_000,
    retry: false,
  });
}
