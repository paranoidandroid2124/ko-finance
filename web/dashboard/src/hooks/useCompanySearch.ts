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

const toOptionalString = (value: unknown): string | null => {
  if (typeof value === "string") {
    return value || null;
  }
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return null;
};

export const normalizeCompanySearchResult = (input: unknown): CompanySearchResult => {
  if (!input || typeof input !== "object") {
    return {};
  }
  const record = input as Record<string, unknown>;
  return {
    corpCode: toOptionalString(record.corpCode ?? record.corp_code),
    ticker: toOptionalString(record.ticker),
    corpName: toOptionalString(record.corpName ?? record.corp_name),
    latestReportName: toOptionalString(record.latestReportName ?? record.latest_report_name),
    latestFiledAt: toOptionalString(record.latestFiledAt ?? record.latest_filed_at),
    highlight: toOptionalString(record.highlight),
  };
};

export const fetchCompanySearch = async (query: string, limit: number): Promise<CompanySearchResult[]> => {
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
  return payload.map((item) => normalizeCompanySearchResult(item));
};

export function useCompanySearch(query: string, limit = 8) {
  const trimmed = query.trim();
  return useQuery({
    queryKey: ["companies", "search", trimmed, limit],
    queryFn: () => fetchCompanySearch(trimmed, limit),
    enabled: trimmed.length >= 1
  });
}

export const resolveCompanyIdentifier = async (identifier: string): Promise<CompanySearchResult | null> => {
  const trimmed = identifier.trim();
  if (!trimmed) {
    return null;
  }
  const candidates = await fetchCompanySearch(trimmed, 6);
  if (candidates.length === 0) {
    return null;
  }
  const upper = trimmed.toUpperCase();
  const lower = trimmed.toLowerCase();
  const directMatch = candidates.find((item) => {
    const ticker = item.ticker?.toUpperCase();
    const corpCode = item.corpCode?.toUpperCase();
    const name = item.corpName?.toLowerCase();
    return ticker === upper || corpCode === upper || name === lower;
  });
  return directMatch ?? candidates[0] ?? null;
};
