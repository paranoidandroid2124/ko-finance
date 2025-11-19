"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { CommanderRouteDecision } from "@/lib/chatApi";
import { useToolStore } from "@/store/toolStore";

type EventStudyPanelProps = {
  params?: Record<string, unknown>;
  decision?: CommanderRouteDecision | null;
};

type EventStudyMemoryWrite = {
  toolId?: string;
  topic: string;
  question?: string | null;
  answer?: string | null;
  highlights?: string[];
  metadata?: Record<string, unknown>;
};

type EventStudyResponse = {
  summary: {
    win_rate: number;
    avg_return: number;
  };
  chart_data: {
    day: number;
    car: number;
  }[];
  history: {
    date: string;
    type: string;
    return: number;
  }[];
  memory_write?: EventStudyMemoryWrite;
};

const tooltipFormatter = (value: number) => [`${value.toFixed(2)}%`, "CAR"];

export function EventStudyPanel({ params }: EventStudyPanelProps) {
  const [data, setData] = useState<EventStudyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const ticker = typeof params?.ticker === "string" ? params?.ticker : "005930";
  const setMemoryDraft = useToolStore((state) => state.setMemoryDraft);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);

    const controller = new AbortController();
    const fetchEventStudy = async () => {
      try {
        const response = await fetch("/api/v1/tools/event-study", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ticker,
            event_type: params?.event_type ?? "earnings",
            period_days: params?.period_days ?? 5,
          }),
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const payload = (await response.json()) as EventStudyResponse;
        if (!mounted) {
          return;
        }
        setData(payload);
        if (payload.memory_write) {
          setMemoryDraft({
            toolId: payload.memory_write.toolId ?? "event_study",
            topic: payload.memory_write.topic,
            question: payload.memory_write.question ?? undefined,
            answer: payload.memory_write.answer ?? undefined,
            highlights: payload.memory_write.highlights ?? [],
            metadata: payload.memory_write.metadata ?? {},
          });
        } else {
          setMemoryDraft(null);
        }
      } catch (fetchError) {
        if (!mounted) {
          return;
        }
        setError(fetchError instanceof Error ? fetchError.message : "알 수 없는 오류가 발생했습니다.");
        setData(null);
        setMemoryDraft(null);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    void fetchEventStudy();

    return () => {
      mounted = false;
      controller.abort();
    };
  }, [ticker, params?.event_type, params?.period_days, setMemoryDraft]);

  const summaryCards = useMemo(() => {
    if (!data) {
      return [
        { label: "승률", value: "-", detail: "데이터 수신 중" },
        { label: "평균 수익률", value: "-", detail: "데이터 수신 중" },
      ];
    }
    return [
      {
        label: "승률",
        value: `${Math.round(data.summary.win_rate * 100)}%`,
        detail: "양의 CAR 이벤트 비중",
      },
      {
        label: "평균 수익률",
        value: `${(data.summary.avg_return * 100).toFixed(1)}%`,
        detail: "이벤트 기준 T+5일",
      },
    ];
  }, [data]);

  const chartData = data?.chart_data.map((row) => ({
    ...row,
    label: row.day === 0 ? "T0" : `T${row.day > 0 ? "+" : ""}${row.day}`,
    carPct: row.car * 100,
  }));

  const history = data?.history ?? [];

  return (
    <div className="flex h-full flex-col gap-6 overflow-hidden">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-2">
        {summaryCards.map((item) => (
          <div
            key={item.label}
            className="rounded-xl border border-gray-200 bg-white/90 p-4 shadow-sm dark:border-gray-700 dark:bg-white/5"
          >
            <p className="text-sm text-gray-500 dark:text-gray-400">{item.label}</p>
            <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{item.value}</p>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{item.detail}</p>
          </div>
        ))}
      </div>

      <div className="flex-1 rounded-2xl border border-gray-200 bg-white/90 p-4 shadow-sm dark:border-gray-700 dark:bg-white/5">
        <div className="mb-2 flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
          <span>누적 초과 수익률 (CAR)</span>
          {ticker ? <span className="font-medium text-gray-700 dark:text-gray-200">{ticker}</span> : null}
        </div>
        <div className="h-[260px] w-full">
          {loading ? (
            <div className="flex h-full items-center justify-center text-sm text-gray-500">
              계산 중입니다...
            </div>
          ) : error ? (
            <div className="flex h-full items-center justify-center text-sm text-red-500">
              데이터를 불러오지 못했습니다: {error}
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 24, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="4 4" stroke="#E5E7EB" />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 12 }}
                  stroke="#9CA3AF"
                  tickMargin={6}
                />
                <YAxis
                  tickFormatter={(value) => `${value.toFixed(1)}%`}
                  tick={{ fontSize: 12 }}
                  stroke="#9CA3AF"
                  domain={["auto", "auto"]}
                />
                <Tooltip
                  formatter={tooltipFormatter}
                  labelFormatter={(label) => `Event ${label}`}
                  contentStyle={{ fontSize: 12 }}
                />
                <ReferenceLine x="T0" stroke="#FDA4AF" strokeDasharray="3 3" />
                <Line
                  type="monotone"
                  dataKey="carPct"
                  stroke="#2563EB"
                  strokeWidth={3}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="rounded-2xl border border-gray-200 bg-white/90 p-4 shadow-sm dark:border-gray-700 dark:bg-white/5">
        <div className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-200">
          과거 이벤트 히스토리
        </div>
        {loading ? (
          <div className="flex h-24 items-center justify-center text-xs text-gray-500">
            이벤트 목록을 불러오는 중입니다...
          </div>
        ) : history.length === 0 ? (
          <div className="flex h-24 items-center justify-center text-xs text-gray-400">
            표시할 이벤트가 없습니다.
          </div>
        ) : (
          <div className="divide-y divide-gray-100 text-sm dark:divide-gray-800">
            {history.map((event) => (
              <div key={event.date} className="flex items-center justify-between py-2">
                <div>
                  <p className="font-medium text-gray-900 dark:text-white">{event.date}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{event.type}</p>
                </div>
                <p className={event.return < 0 ? "text-red-500" : "text-emerald-500"}>
                  {(event.return * 100).toFixed(1)}%
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
