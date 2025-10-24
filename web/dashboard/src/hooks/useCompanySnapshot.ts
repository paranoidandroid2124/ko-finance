"use client";

import { useQuery } from "@tanstack/react-query";

const resolveApiBase = () => {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!base) {
    return "";
  }
  return base.endsWith("/") ? base.slice(0, -1) : base;
};

export type FilingHeadline = {
  receiptNo?: string | null;
  reportName?: string | null;
  title?: string | null;
  filedAt?: string | null;
  viewerUrl?: string | null;
};

export type SummaryBlock = {
  insight?: string | null;
  who?: string | null;
  what?: string | null;
  when?: string | null;
  where?: string | null;
  why?: string | null;
  how?: string | null;
};

export type KeyMetric = {
  metricCode: string;
  label: string;
  value?: number | null;
  unit?: string | null;
  fiscalYear?: number | null;
  fiscalPeriod?: string | null;
};

export type EventItem = {
  id: string;
  eventType: string;
  eventName?: string | null;
  eventDate?: string | null;
  resolutionDate?: string | null;
  reportName?: string | null;
  derivedMetrics: Record<string, unknown>;
};

export type TopicWeight = {
  topic: string;
  count: number;
  weight: number;
};

export type NewsWindowInsight = {
  scope: string;
  ticker?: string | null;
  windowDays: number;
  computedFor: string;
  articleCount: number;
  avgSentiment?: number | null;
  sentimentZ?: number | null;
  noveltyKl?: number | null;
  topicShift?: number | null;
  domesticRatio?: number | null;
  domainDiversity?: number | null;
  topTopics: TopicWeight[];
};

export type CompanySnapshot = {
  corpCode?: string | null;
  ticker?: string | null;
  corpName?: string | null;
  latestFiling?: FilingHeadline | null;
  summary?: SummaryBlock | null;
  keyMetrics: KeyMetric[];
  majorEvents: EventItem[];
  newsSignals: NewsWindowInsight[];
};

const mapTopicWeights = (entries: any[] | null | undefined): TopicWeight[] => {
  if (!entries || !Array.isArray(entries)) {
    return [];
  }
  return entries
    .map((entry) => ({
      topic: String(entry.topic ?? entry.name ?? ""),
      count: Number(entry.count ?? 0),
      weight: Number(entry.weight ?? 0),
    }))
    .filter((entry) => entry.topic.length > 0);
};

const mapNewsInsights = (records: any[] | null | undefined): NewsWindowInsight[] => {
  if (!records || !Array.isArray(records)) {
    return [];
  }

  return records.map((record) => ({
    scope: record.scope,
    ticker: record.ticker,
    windowDays: Number(record.window_days ?? record.windowDays ?? 0),
    computedFor: record.computed_for ?? record.computedFor,
    articleCount: Number(record.article_count ?? record.articleCount ?? 0),
    avgSentiment: record.avg_sentiment ?? record.avgSentiment,
    sentimentZ: record.sentiment_z ?? record.sentimentZ,
    noveltyKl: record.novelty_kl ?? record.noveltyKl,
    topicShift: record.topic_shift ?? record.topicShift,
    domesticRatio: record.domestic_ratio ?? record.domesticRatio,
    domainDiversity: record.domain_diversity ?? record.domainDiversity,
    topTopics: mapTopicWeights(record.top_topics ?? record.topTopics),
  }));
};

const mapSnapshotPayload = (payload: any): CompanySnapshot => ({
  corpCode: payload?.corp_code ?? payload?.corpCode ?? null,
  ticker: payload?.ticker ?? null,
  corpName: payload?.corp_name ?? payload?.corpName ?? null,
  latestFiling: payload?.latest_filing ?? payload?.latestFiling ?? null,
  summary: payload?.summary ?? null,
  keyMetrics: Array.isArray(payload?.key_metrics ?? payload?.keyMetrics)
    ? (payload?.key_metrics ?? payload?.keyMetrics).map((metric: any) => ({
        metricCode: metric.metric_code ?? metric.metricCode ?? "",
        label: metric.label ?? "",
        value: typeof metric.value === "number" ? metric.value : metric.value ?? null,
        unit: metric.unit ?? null,
        fiscalYear: metric.fiscal_year ?? metric.fiscalYear ?? null,
        fiscalPeriod: metric.fiscal_period ?? metric.fiscalPeriod ?? null,
      }))
    : [],
  majorEvents: Array.isArray(payload?.major_events ?? payload?.majorEvents)
    ? (payload?.major_events ?? payload?.majorEvents).map((event: any) => ({
        id: event.id,
        eventType: event.event_type ?? event.eventType ?? "",
        eventName: event.event_name ?? event.eventName ?? null,
        eventDate: event.event_date ?? event.eventDate ?? null,
        resolutionDate: event.resolution_date ?? event.resolutionDate ?? null,
        reportName: event.report_name ?? event.reportName ?? null,
        derivedMetrics: event.derived_metrics ?? event.derivedMetrics ?? {},
      }))
    : [],
  newsSignals: mapNewsInsights(payload?.news_signals ?? payload?.newsSignals),
});

const fetchCompanySnapshot = async (identifier: string): Promise<CompanySnapshot> => {
  const baseUrl = resolveApiBase();
  const response = await fetch(`${baseUrl}/api/v1/companies/${encodeURIComponent(identifier)}/snapshot`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("회사 스냅샷 정보를 불러오지 못했습니다.");
  }

  const payload = await response.json();
  return mapSnapshotPayload(payload);
};

export function useCompanySnapshot(identifier: string) {
  return useQuery({
    queryKey: ["companies", identifier, "snapshot"],
    queryFn: () => fetchCompanySnapshot(identifier),
    enabled: Boolean(identifier),
  });
}
