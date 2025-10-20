import { useQuery } from "@tanstack/react-query";

export type DashboardTrend = "up" | "down" | "flat";

export type DashboardMetric = {
  title: string;
  value: string;
  delta: string;
  trend: DashboardTrend;
  description: string;
};

export type DashboardAlert = {
  id: string;
  title: string;
  body: string;
  timestamp: string;
  tone: "positive" | "negative" | "neutral" | "warning";
};

export type DashboardNewsItem = {
  id: string;
  title: string;
  sentiment: "positive" | "negative" | "neutral";
  source: string;
  publishedAt: string;
};

type DashboardOverview = {
  metrics: DashboardMetric[];
  alerts: DashboardAlert[];
  news: DashboardNewsItem[];
};

const MOCK_METRICS: DashboardMetric[] = [
  { title: "공시 처리", value: "86건", delta: "+12%", trend: "up", description: "24시간 내 분석 완료" },
  { title: "뉴스 감성지수", value: "62.4", delta: "-4.7", trend: "down", description: "15분 윈도우 평균" },
  { title: "RAG 세션", value: "128", delta: "+8.5%", trend: "up", description: "Guardrail 통과율 97%" },
  { title: "알림 전송", value: "412", delta: "0%", trend: "flat", description: "텔레그램/이메일 합산" }
];

const MOCK_ALERTS: DashboardAlert[] = [
  {
    id: "1",
    title: "부정 뉴스 증가",
    body: "반도체 섹터 감성 -12%p (15분)",
    timestamp: "5분 전",
    tone: "negative"
  },
  {
    id: "2",
    title: "신규 공시",
    body: "삼성전자 분기보고서 업로드",
    timestamp: "12분 전",
    tone: "neutral"
  },
  {
    id: "3",
    title: "RAG self-check",
    body: "guardrail 경고 1건",
    timestamp: "18분 전",
    tone: "warning"
  }
];

const MOCK_NEWS: DashboardNewsItem[] = [
  {
    id: "news-1",
    title: "AI 반도체 수요 둔화 우려",
    sentiment: "negative",
    source: "연합뉴스",
    publishedAt: "10분 전"
  },
  {
    id: "news-2",
    title: "친환경 에너지 투자 확대",
    sentiment: "positive",
    source: "매일경제",
    publishedAt: "25분 전"
  },
  {
    id: "news-3",
    title: "원자재 가격 변동성 확대",
    sentiment: "neutral",
    source: "조선비즈",
    publishedAt: "40분 전"
  }
];

const fetchDashboardOverview = async (): Promise<DashboardOverview> => ({
  metrics: MOCK_METRICS,
  alerts: MOCK_ALERTS,
  news: MOCK_NEWS
});

export function useDashboardOverview() {
  return useQuery({
    queryKey: ["dashboard", "overview"],
    queryFn: fetchDashboardOverview
  });
}
