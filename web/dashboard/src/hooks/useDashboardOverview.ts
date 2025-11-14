import { useQuery } from "@tanstack/react-query";

import { resolveApiBase } from "@/lib/apiBase";

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

export type DashboardWatchlistSummary = {
  ruleId: string;
  name: string;
  eventCount: number;
  tickers: string[];
  channels: string[];
  lastTriggeredAt?: string | null;
  lastHeadline?: string | null;
  detailUrl?: string | null;
};

export type DashboardEventItem = {
  id: string;
  ticker?: string | null;
  corpName?: string | null;
  title: string;
  eventType?: string | null;
  filedAt?: string | null;
  severity: "info" | "warning" | "critical" | "neutral";
  targetUrl?: string | null;
};

export type DashboardQuickLink = {
  label: string;
  href: string;
  type: "search" | "company" | "board";
};

type DashboardOverview = {
  metrics: DashboardMetric[];
  alerts: DashboardAlert[];
  news: DashboardNewsItem[];
  watchlists: DashboardWatchlistSummary[];
  events: DashboardEventItem[];
  quickLinks: DashboardQuickLink[];
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
    news: (payload?.news ?? []) as DashboardNewsItem[],
    watchlists: (payload?.watchlists ?? []) as DashboardWatchlistSummary[],
    events: (payload?.events ?? []) as DashboardEventItem[],
    quickLinks: (payload?.quickLinks ?? []) as DashboardQuickLink[]
  };
};

export function useDashboardOverview() {
  return useQuery({
    queryKey: ["dashboard", "overview"],
    queryFn: fetchDashboardOverview
  });
}
