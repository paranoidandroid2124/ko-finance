"use client";

import { useQuery } from "@tanstack/react-query";

import type { TimelineSparklinePoint } from "@/components/company/TimelineSparkline";
import { resolveApiBase } from "@/lib/apiBase";

const toNumberOrNull = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const toString = (value: unknown): string => {
  if (typeof value === "string") {
    return value;
  }
  return String(value);
};

const mapTimelinePoints = (entries: unknown): TimelineSparklinePoint[] => {
  if (!Array.isArray(entries)) {
    return [];
  }
  return entries.reduce<TimelineSparklinePoint[]>((acc, item) => {
    if (typeof item !== "object" || item === null) {
      return acc;
    }

    const record = item as Record<string, unknown>;
    const dateValue = record.date ?? record.computed_for ?? record.computedFor;
    if (!dateValue) {
      return acc;
    }

    const eventTypeRaw =
      typeof record.event_type === "string"
        ? record.event_type
        : typeof record.eventType === "string"
          ? record.eventType
          : null;

    const evidenceRaw = record.evidence_urn_ids ?? record.evidenceUrnIds;
    const evidenceUrnIds = Array.isArray(evidenceRaw)
      ? (evidenceRaw as unknown[])
          .map((value) => (typeof value === "string" ? value : String(value)))
          .filter((value): value is string => value.length > 0)
      : undefined;

    const point: TimelineSparklinePoint = {
      date: toString(dateValue),
      sentimentZ: toNumberOrNull(record.sentiment_z ?? record.sentimentZ),
      priceClose: toNumberOrNull(record.price_close ?? record.priceClose),
      volume: toNumberOrNull(record.volume),
      eventType: eventTypeRaw,
      evidenceUrnIds,
    };

    acc.push(point);
    return acc;
  }, []);
};

type CompanyTimelineResponse = {
  window_days: number;
  total_points: number;
  downsampled_points: number;
  points: TimelineSparklinePoint[];
};

const mapResponse = (payload: unknown): CompanyTimelineResponse => {
  if (typeof payload !== "object" || payload === null) {
    return {
      window_days: 0,
      total_points: 0,
      downsampled_points: 0,
      points: [],
    };
  }
  const record = payload as Record<string, unknown>;
  return {
    window_days: Number(record.window_days ?? record.windowDays ?? 0),
    total_points: Number(record.total_points ?? record.totalPoints ?? 0),
    downsampled_points: Number(record.downsampled_points ?? record.downsampledPoints ?? 0),
    points: mapTimelinePoints(record.points),
  };
};

const fetchCompanyTimeline = async (identifier: string, windowDays = 180): Promise<CompanyTimelineResponse> => {
  const baseUrl = resolveApiBase();
  const response = await fetch(
    `${baseUrl}/api/v1/companies/${encodeURIComponent(identifier)}/timeline?window_days=${windowDays}`,
    {
      cache: "no-store",
    },
  );
  if (!response.ok) {
    throw new Error("타임라인 데이터를 가져오지 못했습니다.");
  }
  const payload = await response.json();
  return mapResponse(payload);
};

export function useCompanyTimeline(identifier: string, windowDays = 180) {
  return useQuery({
    queryKey: ["companies", identifier, "timeline", windowDays],
    queryFn: () => fetchCompanyTimeline(identifier, windowDays),
    enabled: Boolean(identifier),
  });
}
