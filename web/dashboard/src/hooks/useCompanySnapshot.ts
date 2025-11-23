"use client";

import { useQuery } from "@tanstack/react-query";

import { resolveApiBase } from "@/lib/apiBase";

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

export type CompanyFilingSummary = {
  id: string;
  receiptNo?: string | null;
  reportName?: string | null;
  title?: string | null;
  category?: string | null;
  filedAt?: string | null;
  viewerUrl?: string | null;
  summary?: SummaryBlock | null;
  sentiment?: string | null;
  sentimentReason?: string | null;
};

export type KeyMetric = {
  metricCode: string;
  label: string;
  value?: number | null;
  unit?: string | null;
  fiscalYear?: number | null;
  fiscalPeriod?: string | null;
};

export type RestatementHighlight = {
  receiptNo: string;
  title?: string | null;
  filedAt?: string | null;
  reportName?: string | null;
  metricCode?: string | null;
  metricLabel?: string | null;
  previousValue?: number | null;
  currentValue?: number | null;
  deltaPercent?: number | null;
  viewerUrl?: string | null;
  frequencyPercentile?: number | null;
};

export type EvidenceLink = {
  statementCode: string;
  statementLabel: string;
  metricCode: string;
  metricLabel: string;
  periodLabel: string;
  referenceNo: string;
  viewerUrl: string;
  value?: number | null;
  unit?: string | null;
};

export type FiscalAlignmentInsight = {
  latestAnnualPeriod?: string | null;
  latestQuarterPeriod?: string | null;
  yoyDeltaPercent?: number | null;
  ttmQuarterCoverage: number;
  alignmentStatus: "good" | "warning" | "missing";
  notes?: string | null;
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
  sourceReliability?: number | null;
  deduplicationClusterId?: string | null;
};

export type FinancialValue = {
  fiscalYear?: number | null;
  fiscalPeriod?: string | null;
  periodType: "annual" | "quarter" | "other";
  periodEndDate?: string | null;
  value?: number | null;
  unit?: string | null;
  currency?: string | null;
  referenceNo?: string | null;
};

export type FinancialStatementRow = {
  metricCode: string;
  label: string;
  values: FinancialValue[];
};

export type FinancialStatementBlock = {
  statementCode: string;
  label: string;
  rows: FinancialStatementRow[];
  description?: string | null;
};

export type CompanySnapshot = {
  corpCode?: string | null;
  ticker?: string | null;
  corpName?: string | null;
  latestFiling?: FilingHeadline | null;
  summary?: SummaryBlock | null;
  financialStatements: FinancialStatementBlock[];
  keyMetrics: KeyMetric[];
  majorEvents: EventItem[];
  newsSignals: NewsWindowInsight[];
  recentFilings: CompanyFilingSummary[];
  restatementHighlights: RestatementHighlight[];
  evidenceLinks: EvidenceLink[];
  fiscalAlignment?: FiscalAlignmentInsight | null;
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

  return records.reduce<NewsWindowInsight[]>((acc, raw) => {
    if (!isRecord(raw)) {
      return acc;
    }

    const scope = toStringOrNull(raw.scope);
    const computedFor = toStringOrNull(raw.computed_for ?? raw.computedFor);
    if (!scope || !computedFor) {
      return acc;
    }

    const insight: NewsWindowInsight = {
      scope,
      ticker: toStringOrNull(raw.ticker),
      windowDays: toNumberOrZero(raw.window_days ?? raw.windowDays),
      computedFor,
      articleCount: toNumberOrZero(raw.article_count ?? raw.articleCount),
      avgSentiment: toNumberOrNull(raw.avg_sentiment ?? raw.avgSentiment),
      sentimentZ: toNumberOrNull(raw.sentiment_z ?? raw.sentimentZ),
      noveltyKl: toNumberOrNull(raw.novelty_kl ?? raw.noveltyKl),
      topicShift: toNumberOrNull(raw.topic_shift ?? raw.topicShift),
      domesticRatio: toNumberOrNull(raw.domestic_ratio ?? raw.domesticRatio),
      domainDiversity: toNumberOrNull(raw.domain_diversity ?? raw.domainDiversity),
      topTopics: mapTopicWeights(raw.top_topics ?? raw.topTopics),
      sourceReliability: toNumberOrNull(raw.source_reliability ?? raw.sourceReliability),
      deduplicationClusterId: toStringOrNull(raw.deduplication_cluster_id ?? raw.deduplicationClusterId),
    };

    acc.push(insight);
    return acc;
  }, []);
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

const mapCompanyFilings = (entries: unknown): CompanyFilingSummary[] => {
  if (!Array.isArray(entries)) {
    return [];
  }
  return entries.reduce<CompanyFilingSummary[]>((acc, entry) => {
    if (!isRecord(entry)) {
      return acc;
    }
    const id = toStringOrNull(entry.id);
    if (!id) {
      return acc;
    }
    acc.push({
      id,
      receiptNo: toStringOrNull(entry.receipt_no ?? entry.receiptNo),
      reportName: toStringOrNull(entry.report_name ?? entry.reportName),
      title: toStringOrNull(entry.title),
      category: toStringOrNull(entry.category),
      filedAt: toStringOrNull(entry.filed_at ?? entry.filedAt),
      viewerUrl: toStringOrNull(entry.viewer_url ?? entry.viewerUrl),
      summary: mapSummaryBlock(entry.summary),
      sentiment: toStringOrNull(entry.sentiment),
      sentimentReason: toStringOrNull(entry.sentiment_reason ?? entry.sentimentReason),
    });
    return acc;
  }, []);
};

const mapKeyMetrics = (entries: unknown): KeyMetric[] => {
  if (!Array.isArray(entries)) {
    return [];
  }
  return entries.reduce<KeyMetric[]>((acc, entry) => {
    if (!isRecord(entry)) {
      return acc;
    }
    const metricCode = toStringOrNull(entry.metric_code ?? entry.metricCode);
    const label = toStringOrNull(entry.label);
    if (!metricCode || !label) {
      return acc;
    }
    const metric: KeyMetric = {
      metricCode,
      label,
      value: toNumberOrNull(entry.value),
      unit: toStringOrNull(entry.unit),
      fiscalYear: toNumberOrNull(entry.fiscal_year ?? entry.fiscalYear),
      fiscalPeriod: toStringOrNull(entry.fiscal_period ?? entry.fiscalPeriod),
    };
    acc.push(metric);
    return acc;
  }, []);
};

const mapEvents = (entries: unknown): EventItem[] => {
  if (!Array.isArray(entries)) {
    return [];
  }
  return entries.reduce<EventItem[]>((acc, entry) => {
    if (!isRecord(entry)) {
      return acc;
    }
    const id = toStringOrNull(entry.id);
    const eventType = toStringOrNull(entry.event_type ?? entry.eventType);
    if (!id || !eventType) {
      return acc;
    }
    const event: EventItem = {
      id,
      eventType,
      eventName: toStringOrNull(entry.event_name ?? entry.eventName),
      eventDate: toStringOrNull(entry.event_date ?? entry.eventDate),
      resolutionDate: toStringOrNull(entry.resolution_date ?? entry.resolutionDate),
      reportName: toStringOrNull(entry.report_name ?? entry.reportName),
      derivedMetrics: toRecordOrEmpty(entry.derived_metrics ?? entry.derivedMetrics),
    };
    acc.push(event);
    return acc;
  }, []);
};

const mapRestatementHighlights = (entries: unknown): RestatementHighlight[] => {
  if (!Array.isArray(entries)) {
    return [];
  }
  return entries.reduce<RestatementHighlight[]>((acc, entry) => {
    if (!isRecord(entry) || typeof entry.receipt_no !== "string") {
      return acc;
    }
    acc.push({
      receiptNo: entry.receipt_no,
      title: toStringOrNull(entry.title),
      filedAt: toStringOrNull(entry.filed_at ?? entry.filedAt),
      reportName: toStringOrNull(entry.report_name ?? entry.reportName),
      metricCode: toStringOrNull(entry.metric_code ?? entry.metricCode),
      metricLabel: toStringOrNull(entry.metric_label ?? entry.metricLabel),
      previousValue: toNumberOrNull(entry.previous_value ?? entry.previousValue),
      currentValue: toNumberOrNull(entry.current_value ?? entry.currentValue),
      deltaPercent: toNumberOrNull(entry.delta_percent ?? entry.deltaPercent),
      viewerUrl: toStringOrNull(entry.viewer_url ?? entry.viewerUrl),
      frequencyPercentile: toNumberOrNull(entry.frequency_percentile ?? entry.frequencyPercentile ?? entry.percentile),
    });
    return acc;
  }, []);
};

const mapEvidenceLinks = (entries: unknown): EvidenceLink[] => {
  if (!Array.isArray(entries)) {
    return [];
  }
  return entries.reduce<EvidenceLink[]>((acc, entry) => {
    if (!isRecord(entry)) {
      return acc;
    }
    const referenceNo = toStringOrNull(entry.reference_no ?? entry.referenceNo);
    const viewerUrl = toStringOrNull(entry.viewer_url ?? entry.viewerUrl);
    if (!referenceNo || !viewerUrl) {
      return acc;
    }
    acc.push({
      statementCode: toStringOrNull(entry.statement_code ?? entry.statementCode) ?? "statement",
      statementLabel: toStringOrNull(entry.statement_label ?? entry.statementLabel) ?? "재무제표",
      metricCode: toStringOrNull(entry.metric_code ?? entry.metricCode) ?? referenceNo,
      metricLabel: toStringOrNull(entry.metric_label ?? entry.metricLabel) ?? referenceNo,
      periodLabel: toStringOrNull(entry.period_label ?? entry.periodLabel) ?? "",
      referenceNo,
      viewerUrl,
      value: toNumberOrNull(entry.value),
      unit: toStringOrNull(entry.unit),
    });
    return acc;
  }, []);
};

const mapFiscalAlignment = (value: unknown): FiscalAlignmentInsight | null => {
  if (!isRecord(value)) {
    return null;
  }
  const status = toStringOrNull(value.alignment_status ?? value.alignmentStatus);
  if (status !== "good" && status !== "warning" && status !== "missing") {
    return null;
  }
  return {
    latestAnnualPeriod: toStringOrNull(value.latest_annual_period ?? value.latestAnnualPeriod),
    latestQuarterPeriod: toStringOrNull(value.latest_quarter_period ?? value.latestQuarterPeriod),
    yoyDeltaPercent: toNumberOrNull(value.yoy_delta_percent ?? value.yoyDeltaPercent),
    ttmQuarterCoverage: toNumberOrZero(value.ttm_quarter_coverage ?? value.ttmQuarterCoverage),
    alignmentStatus: status,
    notes: toStringOrNull(value.notes),
  };
};

const mapFinancialValues = (entries: unknown): FinancialValue[] => {
  if (!Array.isArray(entries)) {
    return [];
  }
  return entries.reduce<FinancialValue[]>((acc, entry) => {
    if (!isRecord(entry)) {
      return acc;
    }
    const periodType = toStringOrNull(entry.period_type ?? entry.periodType);
    const normalizedPeriod: FinancialValue["periodType"] =
      periodType === "annual" || periodType === "quarter" ? periodType : "other";

    acc.push({
      fiscalYear: toNumberOrNull(entry.fiscal_year ?? entry.fiscalYear),
      fiscalPeriod: toStringOrNull(entry.fiscal_period ?? entry.fiscalPeriod),
      periodType: normalizedPeriod,
      periodEndDate: toStringOrNull(entry.period_end_date ?? entry.periodEndDate),
      value: toNumberOrNull(entry.value),
      unit: toStringOrNull(entry.unit),
      currency: toStringOrNull(entry.currency),
      referenceNo: toStringOrNull(entry.reference_no ?? entry.referenceNo),
    });
    return acc;
  }, []);
};

const mapFinancialStatementRows = (entries: unknown): FinancialStatementRow[] => {
  if (!Array.isArray(entries)) {
    return [];
  }

  return entries.reduce<FinancialStatementRow[]>((acc, entry) => {
    if (!isRecord(entry)) {
      return acc;
    }
    const metricCode = toStringOrNull(entry.metric_code ?? entry.metricCode);
    const label = toStringOrNull(entry.label);
    if (!metricCode || !label) {
      return acc;
    }
    acc.push({
      metricCode,
      label,
      values: mapFinancialValues(entry.values),
    });
    return acc;
  }, []);
};

const mapFinancialStatements = (entries: unknown): FinancialStatementBlock[] => {
  if (!Array.isArray(entries)) {
    return [];
  }
  return entries.reduce<FinancialStatementBlock[]>((acc, entry) => {
    if (!isRecord(entry)) {
      return acc;
    }
    const statementCode = toStringOrNull(entry.statement_code ?? entry.statementCode);
    const label = toStringOrNull(entry.label);
    if (!statementCode || !label) {
      return acc;
    }
    acc.push({
      statementCode,
      label,
      description: toStringOrNull(entry.description),
      rows: mapFinancialStatementRows(entry.rows),
    });
    return acc;
  }, []);
};

const mapSnapshotPayload = (payload: unknown): CompanySnapshot => {
  const record = toRecordOrEmpty(payload);
  return {
    corpCode: toStringOrNull(record.corp_code ?? record.corpCode),
    ticker: toStringOrNull(record.ticker),
    corpName: toStringOrNull(record.corp_name ?? record.corpName),
    latestFiling: mapFilingHeadline(record.latest_filing ?? record.latestFiling),
    summary: mapSummaryBlock(record.summary),
    financialStatements: mapFinancialStatements(record.financial_statements ?? record.financialStatements),
    keyMetrics: mapKeyMetrics(record.key_metrics ?? record.keyMetrics),
    majorEvents: mapEvents(record.major_events ?? record.majorEvents),
    newsSignals: mapNewsInsights(record.news_signals ?? record.newsSignals),
    recentFilings: mapCompanyFilings(record.recent_filings ?? record.recentFilings),
    restatementHighlights: mapRestatementHighlights(record.restatement_highlights ?? record.restatementHighlights),
    evidenceLinks: mapEvidenceLinks(record.evidence_links ?? record.evidenceLinks),
    fiscalAlignment: mapFiscalAlignment(record.fiscal_alignment ?? record.fiscalAlignment),
  };
};

export const fetchCompanySnapshot = async (identifier: string): Promise<CompanySnapshot> => {
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
