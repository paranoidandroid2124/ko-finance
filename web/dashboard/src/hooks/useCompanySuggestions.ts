"use client";

import { useQuery } from "@tanstack/react-query";

import { resolveApiBase } from "@/lib/apiBase";
import { normalizeCompanySearchResult, type CompanySearchResult } from "./useCompanySearch";

export type CompanySuggestions = {
  recentFilings: CompanySearchResult[];
  trendingNews: CompanySearchResult[];
};

const fetchCompanySuggestions = async (limit: number): Promise<CompanySuggestions> => {
  const baseUrl = resolveApiBase();
  const params = new URLSearchParams({ limit: limit.toString() });
  const response = await fetch(`${baseUrl}/api/v1/companies/suggestions?${params.toString()}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("회사 추천 데이터를 불러오지 못했습니다.");
  }

  const payload = await response.json();
  return {
    recentFilings: Array.isArray(payload?.recent_filings)
      ? payload.recent_filings.map((item: unknown) => normalizeCompanySearchResult(item))
      : [],
    trendingNews: Array.isArray(payload?.trending_news)
      ? payload.trending_news.map((item: unknown) => normalizeCompanySearchResult(item))
      : [],
  };
};

export function useCompanySuggestions(limit = 6) {
  return useQuery({
    queryKey: ["companies", "suggestions", limit],
    queryFn: () => fetchCompanySuggestions(limit),
  });
}
