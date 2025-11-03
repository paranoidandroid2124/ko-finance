import { useQuery } from "@tanstack/react-query";

import { resolveApiBase } from "@/lib/apiBase";

export type HeatmapBucket = {
  label: string;
  start: string;
  end: string;
};

export type HeatmapArticle = {
  id: string;
  title: string;
  url: string;
  source?: string;
  sentiment?: number | null;
  summary?: string | null;
  publishedAt?: string | null;
  publishedAtIso?: string | null;
};

export type HeatmapPoint = {
  sector_index: number;
  bucket_index: number;
  sentiment: number | null;
  article_count: number;
  articles?: HeatmapArticle[];
};

export type NewsHeatmapData = {
  sectors: string[];
  buckets: HeatmapBucket[];
  points: HeatmapPoint[];
};

type HeatmapParams = {
  windowMinutes: number;
};

const fetchHeatmap = async ({ windowMinutes }: HeatmapParams): Promise<NewsHeatmapData> => {
  const baseUrl = resolveApiBase();
  const params = new URLSearchParams({
    window_minutes: Math.max(15, windowMinutes).toString(),
  });
  const response = await fetch(`${baseUrl}/api/v1/news/sentiment/heatmap?${params.toString()}`);
  if (!response.ok) {
    throw new Error("뉴스 감성 히트맵 데이터를 불러오지 못했습니다.");
  }
  const payload = (await response.json()) as NewsHeatmapData;
  return {
    sectors: payload?.sectors ?? [],
    buckets: payload?.buckets ?? [],
    points: payload?.points ?? [],
  };
};

export function useNewsHeatmap(params: HeatmapParams) {
  return useQuery({
    queryKey: ["news", "heatmap", params.windowMinutes],
    queryFn: () => fetchHeatmap(params),
  });
}
