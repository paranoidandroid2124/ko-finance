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
  targetUrl?: string | null;
};

export type DashboardNewsItem = {
  id: string;
  title: string;
  sentiment: "positive" | "negative" | "neutral";
  source: string;
  publishedAt: string;
  url: string;
};

type DashboardOverview = {
  metrics: DashboardMetric[];
  alerts: DashboardAlert[];
  news: DashboardNewsItem[];
};

const resolveApiBase = () => {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!base) {
    return "";
  }
  return base.endsWith("/") ? base.slice(0, -1) : base;
};

const fetchDashboardOverview = async (): Promise<DashboardOverview> => {
  const baseUrl = resolveApiBase();
  const response = await fetch(`${baseUrl}/api/v1/dashboard/overview`);

  if (!response.ok) {
    throw new Error("대시보드 개요 데이터를 불러오지 못했습니다");
  }

  const payload = await response.json();

  return {
    metrics: (payload?.metrics ?? []) as DashboardMetric[],
    alerts: (payload?.alerts ?? []) as DashboardAlert[],
    news: (payload?.news ?? []) as DashboardNewsItem[]
  };
};

export function useDashboardOverview() {
  return useQuery({
    queryKey: ["dashboard", "overview"],
    queryFn: fetchDashboardOverview
  });
}
