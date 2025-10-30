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

const fetchSearchResults = async (
  query: string,
  type: SearchResultType,
  limit: number,
  offset: number
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
  const response = await fetch(`${baseUrl}/api/v1/search?${params.toString()}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Failed to load search results.");
  }

  return (await response.json()) as SearchResponse;
};

export function useSearchResults(query: string, type: SearchResultType, limit = 6, offset = 0) {
  const trimmed = query.trim();
  return useQuery({
    queryKey: ["search", trimmed, type, limit, offset],
    queryFn: () => fetchSearchResults(trimmed, type, limit, offset),
    enabled: trimmed.length > 0,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
}
