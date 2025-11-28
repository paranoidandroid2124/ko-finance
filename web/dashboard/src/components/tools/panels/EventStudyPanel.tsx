"use client";

import { useEffect, useMemo, useState } from "react";

import { GenericToolPlaceholder } from "@/components/tools/panels/GenericToolPlaceholder";
import { useToolStore } from "@/store/toolStore";

type CommanderToolProps = {
  params?: Record<string, unknown>;
  decision?: unknown;
};

type EventStudySeriesPoint = { t?: number; date?: string; aar?: number; caar?: number };

type EventStudyResult = {
  ticker?: string | null;
  eventDate?: string | null;
  windowLabel?: string | null;
  winRate?: number | null;
  sampleSize?: number | null;
  caar?: number | null;
  aarSeries?: EventStudySeriesPoint[];
  caarSeries?: EventStudySeriesPoint[];
  summary?: string | null;
};

const formatPct = (value?: number | null) =>
  typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "N/A";

export function EventStudyPanel({ params }: CommanderToolProps) {
  const ticker = typeof params?.ticker === "string" ? params.ticker.toUpperCase() : "";
  const eventDate = typeof params?.eventDate === "string" ? params.eventDate : undefined;
  const windowKey = typeof params?.window === "string" ? params.window : "D-5~D+5";
  const [data, setData] = useState<EventStudyResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const publishToolSnapshot = useToolStore((state) => state.publishToolSnapshot);
  const sessionId = useToolStore((state) => state.entry?.sessionId ?? null);

  useEffect(() => {
    if (!ticker) {
      setError("티커가 필요합니다.");
      setData(null);
      return;
    }
    let mounted = true;
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    const run = async () => {
      try {
        const response = await fetch("/api/v1/tools/event-study", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ticker,
            event_date: eventDate,
            window_key: windowKey,
          }),
          signal: controller.signal,
        });
        if (!response.ok) {
          const detail = await response.text();
          throw new Error(detail || `HTTP ${response.status}`);
        }
        const payload = (await response.json()) as Partial<EventStudyResult>;
        if (!mounted) return;
        const normalized: EventStudyResult = {
          ticker,
          eventDate: payload.eventDate ?? eventDate ?? null,
          windowLabel: payload.windowLabel ?? windowKey,
          winRate: payload.winRate ?? null,
          sampleSize: payload.sampleSize ?? null,
          caar: payload.caar ?? null,
          aarSeries: Array.isArray(payload.aarSeries) ? payload.aarSeries : [],
          caarSeries: Array.isArray(payload.caarSeries) ? payload.caarSeries : [],
          summary: payload.summary ?? null,
        };
        setData(normalized);
        publishToolSnapshot({
          sessionId,
          summary: `[이벤트 스터디] ${ticker} ${windowKey} 창에서 CAAR ${formatPct(normalized.caar)} / 승률 ${formatPct(normalized.winRate)} (${normalized.sampleSize ?? 0}개 표본)`,
          attachments: [
            {
              type: "event_study",
              title: `${ticker} 이벤트 스터디`,
              data: {
                caar: normalized.caar,
                winRate: normalized.winRate,
                sampleSize: normalized.sampleSize,
                window: normalized.windowLabel,
              },
            },
          ],
        });
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "이벤트 스터디를 불러오지 못했습니다.");
        setData(null);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    void run();
    return () => {
      mounted = false;
      controller.abort();
    };
  }, [ticker, eventDate, windowKey, publishToolSnapshot, sessionId]);

  const chartRows = useMemo(() => {
    const aar = data?.aarSeries ?? [];
    const caar = data?.caarSeries ?? [];
    if (!aar.length && !caar.length) return [];
    const byT = new Map<number, { t: number; aar?: number; caar?: number }>();
    aar.forEach((point) => {
      if (typeof point.t !== "number") return;
      byT.set(point.t, { t: point.t, aar: point.aar ?? null ?? point.caar });
    });
    caar.forEach((point) => {
      if (typeof point.t !== "number") return;
      const existing = byT.get(point.t) ?? { t: point.t };
      existing.caar = point.caar ?? point.aar ?? null;
      byT.set(point.t, existing);
    });
    return Array.from(byT.values()).sort((a, b) => a.t - b.t);
  }, [data]);

  if (!ticker) {
    return (
      <GenericToolPlaceholder
        title="이벤트 스터디"
        description="티커가 전달되지 않았습니다. 커맨더에게 티커를 포함해 다시 요청하세요."
      />
    );
  }

  if (loading) {
    return <GenericToolPlaceholder title="이벤트 스터디" description="분석 중입니다..." />;
  }

  if (error) {
    return <GenericToolPlaceholder title="이벤트 스터디" description={error} hint="조건을 바꿔 다시 시도하세요." />;
  }

  if (!data) {
    return <GenericToolPlaceholder title="이벤트 스터디" description="결과가 비어 있습니다." />;
  }

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
        <p className="text-xs uppercase tracking-[0.4em] text-indigo-200">Event Study</p>
        <p className="mt-2 text-lg font-semibold text-white">
          {data.ticker} · {data.windowLabel}
        </p>
        <p className="mt-1 text-sm text-slate-300">이벤트 이후 수익률 패턴 요약</p>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <MetricCard label="CAAR" value={formatPct(data.caar)} />
        <MetricCard label="승률" value={formatPct(data.winRate)} />
        <MetricCard label="표본 수" value={data.sampleSize ? `${data.sampleSize}건` : "N/A"} />
      </div>

      {data.summary ? (
        <div className="rounded-2xl border border-white/5 bg-white/5 p-4 text-sm text-slate-200">{data.summary}</div>
      ) : null}

      {chartRows.length ? (
        <div className="overflow-auto rounded-2xl border border-white/5 bg-white/5">
          <table className="min-w-full text-sm text-slate-200">
            <thead className="bg-white/5 text-left text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-3 py-2">T</th>
                <th className="px-3 py-2">AAR</th>
                <th className="px-3 py-2">CAAR</th>
              </tr>
            </thead>
            <tbody>
              {chartRows.map((row) => (
                <tr key={row.t} className="border-t border-white/5">
                  <td className="px-3 py-2">{row.t}</td>
                  <td className="px-3 py-2">{formatPct(row.aar)}</td>
                  <td className="px-3 py-2">{formatPct(row.caar)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-white/10 bg-white/5 p-4 text-sm text-slate-300">
          시계열 데이터가 없어 표 형태로 표시합니다. 더 넓은 이벤트 창으로 다시 요청해 보세요.
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <p className="text-xs uppercase tracking-[0.25em] text-indigo-200">{label}</p>
      <p className="mt-2 text-xl font-semibold text-white">{value}</p>
    </div>
  );
}
