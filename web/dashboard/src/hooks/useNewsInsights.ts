import { useQuery } from "@tanstack/react-query";

export type NewsSentiment = "positive" | "negative" | "neutral";

export type NewsItem = {
  id: string;
  title: string;
  sentiment: NewsSentiment;
  source: string;
  publishedAt: string;
  sector: string;
  sentimentScore: number | null;
  publishedAtIso: string;
  url: string;
  summary?: string | null;
};

export type NewsTopic = {
  name: string;
  change: string;
  sentiment: NewsSentiment;
  topArticleId?: string;
  topArticleTitle?: string;
  topArticleUrl?: string;
  topArticleSource?: string;
  topArticlePublishedAt?: string;
};

type NewsInsights = {
  news: NewsItem[];
  topics: NewsTopic[];
};

export type NewsFilterOptions = {
  sectors: string[];
  negativeOnly: boolean;
  excludeNeutral: boolean;
  window: "1h" | "24h" | "7d";
};

const resolveApiBase = () => {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!base) {
    return "";
  }
  return base.endsWith("/") ? base.slice(0, -1) : base;
};

const windowToHours: Record<NewsFilterOptions["window"], number> = {
  "1h": 1,
  "24h": 24,
  "7d": 24 * 7,
};

const fetchNewsInsights = async (filters: NewsFilterOptions): Promise<NewsInsights> => {
  const baseUrl = resolveApiBase();
  const params = new URLSearchParams();

  const uniqueSectors = Array.from(new Set(filters.sectors.map((sector) => sector.trim()).filter(Boolean)));
  uniqueSectors.forEach((sector) => params.append("sectors", sector));

  if (filters.negativeOnly) {
    params.append("negative_only", "true");
  }
  if (filters.excludeNeutral) {
    params.append("exclude_neutral", "true");
  }

  const windowHours = windowToHours[filters.window] ?? windowToHours["24h"];
  params.append("window_hours", windowHours.toString());

  const queryString = params.toString();
  const url = queryString ? `${baseUrl}/api/v1/news/insights?${queryString}` : `${baseUrl}/api/v1/news/insights`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error("뉴스 인사이트 데이터를 불러오지 못했습니다.");
  }

  const payload = await response.json();
  return {
    news: (payload?.news ?? []) as NewsItem[],
    topics: (payload?.topics ?? []) as NewsTopic[],
  };
};

export function useNewsInsights(filters: NewsFilterOptions) {
  const sectorKey = [...filters.sectors].sort().join("|") || "all";
  return useQuery({
    queryKey: ["news", "insights", sectorKey, filters.negativeOnly, filters.excludeNeutral, filters.window],
    queryFn: () => fetchNewsInsights(filters),
  });
}
