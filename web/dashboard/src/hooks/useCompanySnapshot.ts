"use client";

import { useQuery } from "@tanstack/react-query";

const resolveApiBase = () => {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!base) {
    return "";
  }
  return base.endsWith("/") ? base.slice(0, -1) : base;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const toStringOrNull = (value: unknown): string | null => {
  if (value == null) {
    return null;
  }
  return typeof value === "string" ? value : String(value);
};

const toNumberOrNull = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const toNumberOrZero = (value: unknown): number => toNumberOrNull(value) ?? 0;

const toRecordOrEmpty = (value: unknown): Record<string, unknown> =>
  isRecord(value) ? value : {};

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

const mapTopicWeights = (entries: unknown): TopicWeight[] => {
  if (!Array.isArray(entries)) {
    return [];
  }

  return entries
    .map((entry) => {
      if (!isRecord(entry)) {
        return null;
      }
      const topic = toStringOrNull(entry.topic ?? entry.name)?.trim() ?? "";
      if (!topic) {
        return null;
      }
      return {
        topic,
        count: toNumberOrZero(entry.count),
        weight: toNumberOrZero(entry.weight),
      };
    })
    .filter((entry): entry is TopicWeight => Boolean(entry));
};

const mapNewsInsights = (records: unknown): NewsWindowInsight[] => {
  if (!Array.isArray(records)) {
    return [];
  }

  return records
    .map((raw) => {
      if (!isRecord(raw)) {
        return null;
      }

      return {
        scope: toStringOrNull(raw.scope) ?? "",
        ticker: toStringOrNull(raw.ticker),
        windowDays: toNumberOrZero(raw.window_days ?? raw.windowDays),
        computedFor: toStringOrNull(raw.computed_for ?? raw.computedFor) ?? "",
        articleCount: toNumberOrZero(raw.article_count ?? raw.articleCount),
        avgSentiment: toNumberOrNull(raw.avg_sentiment ?? raw.avgSentiment),
        sentimentZ: toNumberOrNull(raw.sentiment_z ?? raw.sentimentZ),
        noveltyKl: toNumberOrNull(raw.novelty_kl ?? raw.noveltyKl),
        topicShift: toNumberOrNull(raw.topic_shift ?? raw.topicShift),
        domesticRatio: toNumberOrNull(raw.domestic_ratio ?? raw.domesticRatio),
        domainDiversity: toNumberOrNull(raw.domain_diversity ?? raw.domainDiversity),
        topTopics: mapTopicWeights(raw.top_topics ?? raw.topTopics),
      };
    })
    .filter((entry): entry is NewsWindowInsight => Boolean(entry));
};

const mapFilingHeadline = (value: unknown): FilingHeadline | null => {
  if (!isRecord(value)) {
    return null;
  }
  return {
    receiptNo: toStringOrNull(value.receipt_no ?? value.receiptNo),
    reportName: toStringOrNull(value.report_name ?? value.reportName),
    title: toStringOrNull(value.title),
    filedAt: toStringOrNull(value.filed_at ?? value.filedAt),
    viewerUrl: toStringOrNull(value.viewer_url ?? value.viewerUrl),
  };
};

const mapSummaryBlock = (value: unknown): SummaryBlock | null => {
  if (!isRecord(value)) {
    return null;
  }
  return {
    insight: toStringOrNull(value.insight),
    who: toStringOrNull(value.who),
    what: toStringOrNull(value.what),
    when: toStringOrNull(value.when),
    where: toStringOrNull(value.where),
    why: toStringOrNull(value.why),
    how: toStringOrNull(value.how),
  };
};

const mapKeyMetrics = (entries: unknown): KeyMetric[] => {
  if (!Array.isArray(entries)) {
    return [];
  }
  return entries
    .map((entry) => {
      if (!isRecord(entry)) {
        return null;
      }
      const metricCode = toStringOrNull(entry.metric_code ?? entry.metricCode) ?? "";
      const label = toStringOrNull(entry.label) ?? "";
      return {
        metricCode,
        label,
        value: toNumberOrNull(entry.value),
        unit: toStringOrNull(entry.unit),
        fiscalYear: toNumberOrNull(entry.fiscal_year ?? entry.fiscalYear),
        fiscalPeriod: toStringOrNull(entry.fiscal_period ?? entry.fiscalPeriod),
      };
    })
    .filter((metric): metric is KeyMetric => Boolean(metric));
};

const mapEvents = (entries: unknown): EventItem[] => {
  if (!Array.isArray(entries)) {
    return [];
  }
  return entries
    .map((entry) => {
      if (!isRecord(entry)) {
        return null;
      }
      const id = toStringOrNull(entry.id);
      const eventType = toStringOrNull(entry.event_type ?? entry.eventType);
      if (!id || !eventType) {
        return null;
      }
      return {
        id,
        eventType,
        eventName: toStringOrNull(entry.event_name ?? entry.eventName),
        eventDate: toStringOrNull(entry.event_date ?? entry.eventDate),
        resolutionDate: toStringOrNull(entry.resolution_date ?? entry.resolutionDate),
        reportName: toStringOrNull(entry.report_name ?? entry.reportName),
        derivedMetrics: toRecordOrEmpty(entry.derived_metrics ?? entry.derivedMetrics),
      };
    })
    .filter((event): event is EventItem => Boolean(event));
};

const mapSnapshotPayload = (payload: unknown): CompanySnapshot => {
  const record = toRecordOrEmpty(payload);
  return {
    corpCode: toStringOrNull(record.corp_code ?? record.corpCode),
    ticker: toStringOrNull(record.ticker),
    corpName: toStringOrNull(record.corp_name ?? record.corpName),
    latestFiling: mapFilingHeadline(record.latest_filing ?? record.latestFiling),
    summary: mapSummaryBlock(record.summary),
    keyMetrics: mapKeyMetrics(record.key_metrics ?? record.keyMetrics),
    majorEvents: mapEvents(record.major_events ?? record.majorEvents),
    newsSignals: mapNewsInsights(record.news_signals ?? record.newsSignals),
  };
};

const fetchCompanySnapshot = async (identifier: string): Promise<CompanySnapshot> => {
  const baseUrl = resolveApiBase();
  const response = await fetch(
    `${baseUrl}/api/v1/companies/${encodeURIComponent(identifier)}/snapshot`,
    {
      cache: "no-store",
    }
  );

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
