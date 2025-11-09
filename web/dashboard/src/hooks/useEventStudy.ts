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
};

export type EventStudyEventsResponse = {
  total: number;
  limit: number;
  offset: number;
  windowEnd: number;
  events: EventStudyEvent[];
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
