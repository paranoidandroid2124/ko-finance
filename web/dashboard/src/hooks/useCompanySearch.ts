"use client";

import { useQuery } from "@tanstack/react-query";
import { resolveApiBase } from "@/lib/apiBase";

export type CompanySearchResult = {
  corpCode?: string | null;
  ticker?: string | null;
  corpName?: string | null;
  latestReportName?: string | null;
  latestFiledAt?: string | null;
  highlight?: string | null;
};

const fetchCompanySearch = async (query: string, limit: number): Promise<CompanySearchResult[]> => {
  const baseUrl = resolveApiBase();
  const params = new URLSearchParams({ q: query, limit: limit.toString() });
  const response = await fetch(`${baseUrl}/api/v1/companies/search?${params.toString()}`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error("회사 검색 결과를 불러오지 못했습니다.");
  }

  const payload = await response.json();
  if (!Array.isArray(payload)) {
    return [];
  }
  return payload;
};

export function useCompanySearch(query: string, limit = 8) {
  const trimmed = query.trim();
  return useQuery({
    queryKey: ["companies", "search", trimmed, limit],
    queryFn: () => fetchCompanySearch(trimmed, limit),
    enabled: trimmed.length >= 1
  });
}
