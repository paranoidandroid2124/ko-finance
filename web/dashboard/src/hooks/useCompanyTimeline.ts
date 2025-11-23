"use client";

import { useQuery } from "@tanstack/react-query";
import { resolveApiBase } from "@/lib/apiBase";

export type CompanyTimelinePoint = {
  date: string;
  sentiment?: number | null;
  newsCount?: number | null;
  filingCount?: number | null;
  priceClose?: number | null;
  volume?: number | null;
  headline?: string | null;
  url?: string | null;
};

export type CompanyTimelineResponse = {
  window_days: number;
  total_points: number;
  downsampled_points: number;
  points: CompanyTimelinePoint[];
};

const fetchCompanyTimeline = async (identifier: string, windowDays: number): Promise<CompanyTimelineResponse> => {
  const baseUrl = resolveApiBase();
  const response = await fetch(
    `${baseUrl}/api/v1/companies/${encodeURIComponent(identifier)}/timeline?window_days=${windowDays}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error("회사 타임라인을 불러오지 못했습니다.");
  }
  return (await response.json()) as CompanyTimelineResponse;
};

export function useCompanyTimeline(identifier: string, windowDays = 120) {
  return useQuery({
    queryKey: ["companies", identifier, "timeline", windowDays],
    queryFn: () => fetchCompanyTimeline(identifier, windowDays),
    enabled: Boolean(identifier),
    staleTime: 60_000,
  });
}
