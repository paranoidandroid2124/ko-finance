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

const MOCK_NEWS: NewsItem[] = [
  {
    id: "n1",
    title: "AI 반도체 수요 둔화 우려",
    sentiment: "negative",
    source: "연합뉴스",
    publishedAt: "10분 전"
  },
  {
    id: "n2",
    title: "친환경 에너지 투자 확대",
    sentiment: "positive",
    source: "매일경제",
    publishedAt: "25분 전"
  },
  {
    id: "n3",
    title: "원자재 가격 변동성 확대",
    sentiment: "neutral",
    source: "조선비즈",
    publishedAt: "40분 전"
  },
  {
    id: "n4",
    title: "바이오 규제 완화 기대감",
    sentiment: "positive",
    source: "헤럴드경제",
    publishedAt: "1시간 전"
  }
];

const MOCK_TOPICS: NewsTopic[] = [
  { name: "AI 반도체", change: "-24.7%", sentiment: "negative" },
  { name: "친환경 에너지", change: "+18.5%", sentiment: "positive" },
  { name: "콘텐츠 플랫폼", change: "-12.2%", sentiment: "negative" },
  { name: "바이오 규제", change: "+9.4%", sentiment: "positive" }
];

const fetchNewsInsights = async (): Promise<NewsInsights> => ({
  news: MOCK_NEWS,
  topics: MOCK_TOPICS
});

export function useNewsInsights() {
  return useQuery({
    queryKey: ["news", "insights"],
    queryFn: fetchNewsInsights
  });
}
