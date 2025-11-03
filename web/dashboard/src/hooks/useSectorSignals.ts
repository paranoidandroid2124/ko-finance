import { useQuery } from "@tanstack/react-query";

import { resolveApiBase } from "@/lib/apiBase";

type SectorRef = {
  id: number;
  slug: string;
  name: string;
};

export type SectorTopArticle = {
  id: string;
  title: string;
  summary?: string | null;
  url: string;
  targetUrl?: string | null;
  tone?: number | null;
  publishedAt: string;
};

export type SectorSignalPoint = {
  sector: SectorRef;
  sentimentZ: number;
  volumeZ: number;
  deltaSentiment7d: number | null;
  sentimentMean: number | null;
  volumeSum: number | null;
  topArticle?: SectorTopArticle | null;
};

export type SectorSignalsResponse = {
  asOf: string;
  windowDays: number;
  points: SectorSignalPoint[];
};

async function fetchSectorSignals(windowDays: number): Promise<SectorSignalsResponse> {
  const baseUrl = resolveApiBase();
  const response = await fetch(`${baseUrl}/api/v1/sectors/signals?window=${windowDays}`);
  if (!response.ok) {
    throw new Error("섹터 신호 데이터를 불러오지 못했습니다.");
  }
  const payload = (await response.json()) as SectorSignalsResponse;
  payload.points = payload.points ?? [];
  return payload;
}

export function useSectorSignals(windowDays = 7) {
  return useQuery({
    queryKey: ["sectors", "signals", windowDays],
    queryFn: () => fetchSectorSignals(windowDays),
    staleTime: 60 * 1000,
  });
}

export type { SectorRef };
