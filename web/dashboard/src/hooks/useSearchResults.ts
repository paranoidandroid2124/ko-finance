"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { resolveApiBase } from "@/lib/apiBase";

export type SearchResultType = "filing" | "news" | "table" | "chart";

export type SearchResultActions = {
  compareLocked?: boolean;
  alertLocked?: boolean;
  exportLocked?: boolean;
};

export type SearchEvidenceCounts = {
  filings?: number;
  news?: number;
  tables?: number;
  charts?: number;
};

export type SearchResult = {
  id: string;
  type: SearchResultType;
  title: string;
  category: string;
  filedAt?: string | null;
  latestIngestedAt?: string | null;
  sourceReliability?: number | null;
  evidenceCounts?: SearchEvidenceCounts | null;
  actions?: SearchResultActions | null;
};

export type SearchTotals = {
  filing: number;
  news: number;
  table: number;
  chart: number;
};

export type SearchResponse = {
  query: string;
  total: number;
  totals: SearchTotals;
  results: SearchResult[];
};

export type SearchRequestFilters = {
  dateFrom?: string | null;
  dateTo?: string | null;
  sectors?: string[];
  watchlistOnly?: boolean;
};

const fetchSearchResults = async (
  query: string,
  type: SearchResultType,
  limit: number,
  offset: number,
  filters?: SearchRequestFilters
): Promise<SearchResponse> => {
  const baseUrl = resolveApiBase();
  const params = new URLSearchParams({
    limit: limit.toString(),
    offset: offset.toString(),
  });
  if (query) {
    params.set("q", query);
  }
  if (type) {
    params.append("types", type);
  }
  if (filters?.dateFrom) {
    params.set("date_from", filters.dateFrom);
  }
  if (filters?.dateTo) {
    params.set("date_to", filters.dateTo);
  }
  if (filters?.sectors && filters.sectors.length > 0) {
    filters.sectors.forEach((sector) => params.append("sector", sector));
  }
  if (filters?.watchlistOnly) {
    params.set("watchlist_only", "true");
  }
  const response = await fetch(`${baseUrl}/api/v1/search?${params.toString()}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Failed to load search results.");
  }

  return (await response.json()) as SearchResponse;
};

export function useSearchResults(
  query: string,
  type: SearchResultType,
  limit = 6,
  offset = 0,
  filters?: SearchRequestFilters
) {
  const trimmed = query.trim();
  const sectorKey = filters?.sectors?.slice().sort().join("|") ?? "";
  return useQuery({
    queryKey: ["search", trimmed, type, limit, offset, filters?.dateFrom ?? null, filters?.dateTo ?? null, sectorKey, filters?.watchlistOnly ?? false],
    queryFn: () => fetchSearchResults(trimmed, type, limit, offset, filters),
    enabled: trimmed.length > 0,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
}
