import { useQuery } from "@tanstack/react-query";

export type NewsSentiment = "positive" | "negative" | "neutral";

export type NewsItem = {
  id: string;
  title: string;
  sentiment: NewsSentiment;
  source: string;
  publishedAt: string;
};

export type NewsTopic = {
  name: string;
  change: string;
  sentiment: NewsSentiment;
};

type NewsInsights = {
  news: NewsItem[];
  topics: NewsTopic[];
};

const resolveApiBase = () => {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!base) {
    return "";
  }
  return base.endsWith("/") ? base.slice(0, -1) : base;
};

const fetchNewsInsights = async (): Promise<NewsInsights> => {
  const baseUrl = resolveApiBase();
  const response = await fetch(`${baseUrl}/api/v1/news/insights`);
  if (!response.ok) {
    throw new Error("뉴스 인사이트 데이터를 불러오지 못했습니다.");
  }

  const payload = await response.json();
  return {
    news: (payload?.news ?? []) as NewsItem[],
    topics: (payload?.topics ?? []) as NewsTopic[]
  };
};

export function useNewsInsights() {
  return useQuery({
    queryKey: ["news", "insights"],
    queryFn: fetchNewsInsights
  });
}
