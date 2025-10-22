import { useQuery } from "@tanstack/react-query";

export type HeatmapBucket = {
  label: string;
  start: string;
  end: string;
};

export type HeatmapPoint = {
  sector_index: number;
  bucket_index: number;
  sentiment: number | null;
  article_count: number;
};

export type NewsHeatmapData = {
  sectors: string[];
  buckets: HeatmapBucket[];
  points: HeatmapPoint[];
};

const resolveApiBase = () => {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!base) {
    return "";
  }
  return base.endsWith("/") ? base.slice(0, -1) : base;
};

const fetchHeatmap = async (): Promise<NewsHeatmapData> => {
  const baseUrl = resolveApiBase();
  const response = await fetch(`${baseUrl}/api/v1/news/sentiment/heatmap`);
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

export function useNewsHeatmap() {
  return useQuery({
    queryKey: ["news", "heatmap"],
    queryFn: fetchHeatmap,
  });
}
