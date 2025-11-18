"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { resolveApiBase } from "@/lib/apiBase";

export type EventStudyPoint = { t: number; value: number };

export type EventStudySummaryItem = {
  eventType: string;
  scope: string;
  window: string;
  asOf: string;
  capBucket?: string;
  n: number;
  hitRate: number;
  meanCaar: number;
  ciLo: number;
  ciHi: number;
  pValue: number;
  aar: EventStudyPoint[];
  caar: EventStudyPoint[];
  dist: Array<{ bin: number; range: [number, number]; count: number }>;
};

export type EventStudySummaryResponse = {
  start: number;
  end: number;
  scope: string;
  significance: number;
  results: EventStudySummaryItem[];
};

export type EventStudyEvent = {
  receiptNo: string;
  corpCode?: string | null;
  corpName?: string | null;
  ticker?: string | null;
  eventType: string;
  market?: string | null;
  eventDate?: string | null;
  amount?: number | null;
  ratio?: number | null;
  method?: string | null;
  score?: number | null;
  caar?: number | null;
  aarPeakDay?: number | null;
  viewerUrl?: string | null;
  capBucket?: string | null;
  marketCap?: number | null;
  salience?: number | null;
  isRestatement?: boolean;
};

export type EventStudyEventsResponse = {
  total: number;
  limit: number;
  offset: number;
  windowEnd: number;
  events: EventStudyEvent[];
};

export type EventStudyEventDocument = {
  title?: string | null;
  viewerUrl?: string | null;
  publishedAt?: string | null;
  source?: string | null;
};

export type EventStudyEventLink = {
  label: string;
  url: string;
  kind: string;
};

export type EventStudyEventEvidence = {
  urnId?: string | null;
  quote?: string | null;
  section?: string | null;
  pageNumber?: number | null;
  viewerUrl?: string | null;
  documentTitle?: string | null;
  documentUrl?: string | null;
};

export type EventStudyEventSeriesPoint = {
  t: number;
  ar?: number | null;
  car?: number | null;
};

export type EventStudyEventDetailResponse = {
  receiptNo: string;
  corpCode?: string | null;
  corpName?: string | null;
  ticker?: string | null;
  eventType: string;
  eventDate?: string | null;
  market?: string | null;
  scope: string;
  window: string;
  viewerUrl?: string | null;
  capBucket?: string | null;
  marketCap?: number | null;
  sectorSlug?: string | null;
  sectorName?: string | null;
  subtype?: string | null;
  confidence?: number | null;
  salience?: number | null;
  isRestatement: boolean;
  series: EventStudyEventSeriesPoint[];
  documents: EventStudyEventDocument[];
  links: EventStudyEventLink[];
  evidence: EventStudyEventEvidence[];
};

export type EventStudyWindowPreset = {
  key: string;
  label: string;
  description?: string | null;
  start: number;
  end: number;
};

export type EventStudyWindowListResponse = {
  windows: EventStudyWindowPreset[];
  defaultKey: string;
};

export type EventStudyMetricsQuery = {
  windowKey?: string;
  eventType: string;
  ticker: string;
  sig?: number;
  capBuckets?: string[];
  markets?: string[];
  startDate?: string;
  endDate?: string;
  search?: string;
  limit?: number;
  offset?: number;
};

export type EventStudyMetricsResponse = {
  windowKey: string;
  windowLabel: string;
  start: number;
  end: number;
  eventType: string;
  ticker?: string | null;
  capBucket?: string | null;
  scope: string;
  significance: number;
  n: number;
  hitRate: number;
  meanCaar: number;
  ciLo: number;
  ciHi: number;
  pValue: number;
  aar: EventStudyPoint[];
  caar: EventStudyPoint[];
  dist: Array<{ bin: number; range: [number, number]; count: number }>;
  events: EventStudyEventsResponse;
};

export type EventStudyBoardFilters = {
  startDate: string;
  endDate: string;
  eventTypes: string[];
  sectorSlugs: string[];
  capBuckets: string[];
  markets: string[];
  minMarketCap?: number | null;
  maxMarketCap?: number | null;
  minSalience?: number | null;
  includeRestatement: boolean;
  search?: string | null;
};

export type EventStudyHeatmapBucket = {
  eventType: string;
  bucketStart: string;
  bucketEnd: string;
  avgCaar?: number | null;
  count: number;
  restatementRatio?: number | null;
};

export type EventStudyBoardResponse = {
  window: EventStudyWindowPreset;
  filters: EventStudyBoardFilters;
  summary: EventStudySummaryItem[];
  heatmap: EventStudyHeatmapBucket[];
  events: EventStudyEventsResponse;
  restatementHighlights: EventStudyEvent[];
  asOf: string;
};

export type EventStudySummaryQuery = {
  start: number;
  end: number;
  scope?: string;
  sig?: number;
  eventTypes?: string[];
  capBuckets?: string[];
};

export type EventStudyEventsQuery = {
  limit?: number;
  offset?: number;
  windowEnd: number;
  eventTypes?: string[];
  markets?: string[];
  capBuckets?: string[];
  search?: string;
  startDate?: string;
  endDate?: string;
};

export type EventStudyBoardQuery = {
  startDate?: string;
  endDate?: string;
  windowKey?: string;
  eventTypes?: string[];
  sectorSlugs?: string[];
  capBuckets?: string[];
  markets?: string[];
  minMarketCap?: number;
  maxMarketCap?: number;
  minSalience?: number;
  includeRestatement?: boolean;
  search?: string;
  sig?: number;
  limit?: number;
  offset?: number;
};

const appendListParam = (params: URLSearchParams, key: string, values?: string[]) => {
  for (const value of values ?? []) {
    if (!value) continue;
    params.append(key, value);
  }
};

const fetchEventStudySummary = async (query: EventStudySummaryQuery): Promise<EventStudySummaryResponse> => {
  const params = new URLSearchParams();
  params.set("start", String(query.start));
  params.set("end", String(query.end));
  if (query.scope) {
    params.set("scope", query.scope);
  }
  if (typeof query.sig === "number") {
    params.set("sig", String(query.sig));
  }
  appendListParam(params, "eventTypes", query.eventTypes);
  appendListParam(
    params,
    "capBuckets",
    query.capBuckets?.map((value) => value.toUpperCase()),
  );

  const response = await fetch(`${resolveApiBase()}/api/v1/event-study/summary?${params.toString()}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("이벤트 스터디 요약을 불러오지 못했습니다.");
  }
  return (await response.json()) as EventStudySummaryResponse;
};

const fetchEventStudyEvents = async (query: EventStudyEventsQuery): Promise<EventStudyEventsResponse> => {
  const params = new URLSearchParams();
  params.set("windowEnd", String(query.windowEnd));
  params.set("limit", String(query.limit ?? 50));
  params.set("offset", String(query.offset ?? 0));
  appendListParam(params, "eventTypes", query.eventTypes);
  appendListParam(params, "markets", query.markets);
  appendListParam(
    params,
    "capBuckets",
    query.capBuckets?.map((value) => value.toUpperCase()),
  );
  if (query.search) {
    params.set("search", query.search);
  }
  if (query.startDate) {
    params.set("startDate", query.startDate);
  }
  if (query.endDate) {
    params.set("endDate", query.endDate);
  }

  const response = await fetch(`${resolveApiBase()}/api/v1/event-study/events?${params.toString()}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("이벤트 목록을 불러오지 못했습니다.");
  }
  return (await response.json()) as EventStudyEventsResponse;
};

const fetchEventStudyBoard = async (query: EventStudyBoardQuery): Promise<EventStudyBoardResponse> => {
  const params = new URLSearchParams();
  if (query.startDate) {
    params.set("startDate", query.startDate);
  }
  if (query.endDate) {
    params.set("endDate", query.endDate);
  }
  if (query.windowKey) {
    params.set("windowKey", query.windowKey);
  }
  appendListParam(params, "eventTypes", query.eventTypes);
  appendListParam(params, "sectorSlugs", query.sectorSlugs);
  appendListParam(params, "capBuckets", query.capBuckets);
  appendListParam(params, "markets", query.markets);
  if (typeof query.minMarketCap === "number") {
    params.set("minMarketCap", String(query.minMarketCap));
  }
  if (typeof query.maxMarketCap === "number") {
    params.set("maxMarketCap", String(query.maxMarketCap));
  }
  if (typeof query.minSalience === "number") {
    params.set("minSalience", String(query.minSalience));
  }
  if (query.includeRestatement === false) {
    params.set("includeRestatement", "false");
  }
  if (query.search) {
    params.set("search", query.search);
  }
  if (typeof query.sig === "number") {
    params.set("sig", String(query.sig));
  }
  params.set("limit", String(query.limit ?? 50));
  params.set("offset", String(query.offset ?? 0));

  const response = await fetch(`${resolveApiBase()}/api/v1/event-study/board?${params.toString()}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("이벤트 스터디 보드를 불러오지 못했습니다.");
  }
  return (await response.json()) as EventStudyBoardResponse;
};

const fetchEventStudyEventDetail = async (
  receiptNo: string,
  query?: { windowKey?: string },
): Promise<EventStudyEventDetailResponse> => {
  const params = new URLSearchParams();
  if (query?.windowKey) {
    params.set("windowKey", query.windowKey);
  }
  params.set("includeEvidence", "true");
  const response = await fetch(
    `${resolveApiBase()}/api/v1/event-study/events/${encodeURIComponent(receiptNo)}?${params.toString()}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error("이벤트 상세 정보를 불러오지 못했습니다.");
  }
  return (await response.json()) as EventStudyEventDetailResponse;
};

const fetchEventStudyWindows = async (): Promise<EventStudyWindowListResponse> => {
  const response = await fetch(`${resolveApiBase()}/api/v1/event-study/windows`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("이벤트 윈도우 프리셋을 불러오지 못했습니다.");
  }
  return (await response.json()) as EventStudyWindowListResponse;
};

const fetchEventStudyMetrics = async (query: EventStudyMetricsQuery): Promise<EventStudyMetricsResponse> => {
  const params = new URLSearchParams();
  if (query.windowKey) {
    params.set("windowKey", query.windowKey);
  }
  params.set("eventType", query.eventType);
  params.set("ticker", query.ticker);
  if (typeof query.sig === "number") {
    params.set("sig", String(query.sig));
  }
  appendListParam(
    params,
    "capBuckets",
    query.capBuckets?.map((value) => value.toUpperCase()),
  );
  appendListParam(params, "markets", query.markets);
  if (query.startDate) {
    params.set("startDate", query.startDate);
  }
  if (query.endDate) {
    params.set("endDate", query.endDate);
  }
  if (query.search) {
    params.set("search", query.search);
  }
  params.set("limit", String(query.limit ?? 50));
  params.set("offset", String(query.offset ?? 0));

  const response = await fetch(`${resolveApiBase()}/api/v1/event-study/metrics?${params.toString()}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("이벤트 스터디 메트릭을 불러오지 못했습니다.");
  }
  return (await response.json()) as EventStudyMetricsResponse;
};

export const useEventStudySummary = (
  params: EventStudySummaryQuery,
  options?: { enabled?: boolean },
) => {
  return useQuery<EventStudySummaryResponse>({
    queryKey: ["event-study-summary", params],
    queryFn: () => fetchEventStudySummary(params),
    staleTime: 60_000,
    enabled: options?.enabled ?? true,
  });
};

export const useEventStudyEvents = (
    params: EventStudyEventsQuery,
    options?: { enabled?: boolean },
) => {
    return useQuery<EventStudyEventsResponse>({
    queryKey: ["event-study-events", params],
    queryFn: () => fetchEventStudyEvents(params),
    staleTime: 30_000,
        placeholderData: keepPreviousData,
        enabled: options?.enabled ?? true,
    });
};

export const useEventStudyWindows = () => {
  return useQuery<EventStudyWindowListResponse>({
    queryKey: ["event-study-windows"],
    queryFn: fetchEventStudyWindows,
    staleTime: 30 * 60 * 1000,
  });
};

export const useEventStudyMetrics = (
  params: EventStudyMetricsQuery,
  options?: { enabled?: boolean },
) => {
  return useQuery<EventStudyMetricsResponse>({
    queryKey: ["event-study-metrics", params],
    queryFn: () => fetchEventStudyMetrics(params),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
    enabled: options?.enabled ?? true,
  });
};

export const useEventStudyBoard = (
  params: EventStudyBoardQuery,
  options?: { enabled?: boolean },
) => {
  return useQuery<EventStudyBoardResponse>({
    queryKey: ["event-study-board", params],
    queryFn: () => fetchEventStudyBoard(params),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
    enabled: options?.enabled ?? true,
  });
};

export const useEventStudyEventDetail = (
  receiptNo: string | null,
  params?: { windowKey?: string },
  options?: { enabled?: boolean },
) => {
  return useQuery<EventStudyEventDetailResponse>({
    queryKey: ["event-study-event-detail", receiptNo, params],
    queryFn: () => fetchEventStudyEventDetail(receiptNo as string, params),
    enabled: Boolean(receiptNo) && (options?.enabled ?? true),
  });
};

export type EventStudyExportParams = {
  windowStart: number;
  windowEnd: number;
  scope?: string;
  significance?: number;
  eventTypes?: string[];
  markets?: string[];
  capBuckets?: string[];
  startDate?: string | null;
  endDate?: string | null;
  search?: string;
  limit?: number;
  requestedBy?: string | null;
};

export type EventStudyExportResponse = {
  taskId: string;
  pdfPath: string;
  pdfObject?: string | null;
  pdfUrl?: string | null;
  packagePath?: string | null;
  packageObject?: string | null;
  packageUrl?: string | null;
  manifestPath?: string | null;
};

export const exportEventStudyReport = async (params: EventStudyExportParams): Promise<EventStudyExportResponse> => {
  const payload = {
    ...params,
    capBuckets: params.capBuckets?.map((value) => value.toUpperCase()),
  };
  const response = await fetch(`${resolveApiBase()}/api/v1/event-study/export`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "이벤트 스터디 리포트를 내보내지 못했습니다.");
  }
  return (await response.json()) as EventStudyExportResponse;
};
