"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { Loader2 } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { FilterChip } from "@/components/ui/FilterChip";
import { EmptyState } from "@/components/ui/EmptyState";
import {
  useEventStudyMetrics,
  useEventStudyWindows,
  type EventStudyEvent,
  type EventStudyWindowPreset,
} from "@/hooks/useEventStudy";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

type EventType = "BUYBACK" | "SEO" | "DIVIDEND" | "RESTATEMENT" | "CONVERTIBLE" | "CONTRACT";

const EVENT_TYPE_OPTIONS: Array<{ value: EventType; label: string }> = [
  { value: "BUYBACK", label: "자사주 매입·소각" },
  { value: "SEO", label: "유상증자(SEO)" },
  { value: "DIVIDEND", label: "배당" },
  { value: "RESTATEMENT", label: "정정 공시" },
  { value: "CONVERTIBLE", label: "CB/BW 발행" },
  { value: "CONTRACT", label: "대형 계약" },
];

const CAP_BUCKET_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "ALL", label: "전체" },
  { value: "LARGE", label: "대형" },
  { value: "MID", label: "중형" },
  { value: "SMALL", label: "소형" },
];

const MARKET_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "KOSPI", label: "KOSPI" },
  { value: "KOSDAQ", label: "KOSDAQ" },
];

const SIGNIFICANCE_OPTIONS = [0.05, 0.1, 0.2];

const formatPercent = (value: number, digits = 2) => `${value >= 0 ? "+" : ""}${(value * 100).toFixed(digits)}%`;
const formatNullablePercent = (value?: number | null, digits = 2) => (value == null ? "—" : formatPercent(value, digits));
const formatNumber = (value?: number | null) =>
  value == null ? "—" : new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 }).format(value);

const buildCaarOption = (points: Array<{ t: number; value: number }>, label: string) => ({
  tooltip: { trigger: "axis" },
  grid: { left: 32, right: 12, top: 16, bottom: 32 },
  xAxis: {
    type: "category",
    data: points.map((point) => point.t),
    name: "Event Day",
  },
  yAxis: {
    type: "value",
    axisLabel: {
      formatter: (value: number) => `${(value * 100).toFixed(1)}%`,
    },
  },
  series: [
    {
      name: `CAAR ${label}`,
      type: "line",
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 3 },
      data: points.map((point) => Number(point.value.toFixed(6))),
    },
  ],
});

const buildHistogramOption = (bins: Array<{ bin: number; range: [number, number]; count: number }> = []) => ({
  tooltip: {
    trigger: "item",
    formatter: (params: { data?: { range?: [number, number]; value?: number } }) => {
      if (!params?.data?.range) return "";
      const [start, end] = params.data.range;
      const count = params.data.value ?? 0;
      return `${formatPercent(start, 2)} ~ ${formatPercent(end, 2)} · ${count}건`;
    },
  },
  grid: { left: 24, right: 12, top: 12, bottom: 24 },
  xAxis: {
    type: "category",
    data: bins.map((bin) => `${formatPercent(bin.range[0], 1)} ~ ${formatPercent(bin.range[1], 1)}`),
    axisLabel: { rotate: 35 },
  },
  yAxis: { type: "value" },
  series: [
    {
      type: "bar",
      barWidth: "70%",
      data: bins.map((bin) => ({ value: bin.count, range: bin.range })),
    },
  ],
});


export default function EventStudyPage() {
  const [tickerInput, setTickerInput] = useState("");
  const [eventType, setEventType] = useState<EventType>("BUYBACK");
  const [capBucket, setCapBucket] = useState("ALL");
  const [selectedMarkets, setSelectedMarkets] = useState<string[]>(["KOSPI", "KOSDAQ"]);
  const [windowKey, setWindowKey] = useState<string | null>(null);
  const [significance, setSignificance] = useState(0.1);
  const [searchTerm, setSearchTerm] = useState("");

  const { data: windowData, isLoading: isWindowLoading } = useEventStudyWindows();
  const resolvedWindowKey = windowKey ?? windowData?.defaultKey;
  const normalizedTicker = tickerInput.trim().toUpperCase();

  const metricsParams = useMemo(
    () => ({
      windowKey: resolvedWindowKey ?? undefined,
      eventType,
      ticker: normalizedTicker,
      sig: significance,
      capBuckets: capBucket === "ALL" ? undefined : [capBucket],
      markets: selectedMarkets,
      search: searchTerm.trim() || undefined,
    }),
    [capBucket, eventType, normalizedTicker, resolvedWindowKey, searchTerm, selectedMarkets, significance],
  );

  const metricsEnabled = Boolean(resolvedWindowKey && normalizedTicker);
  const {
    data: metrics,
    isLoading: isMetricsLoading,
    isFetching: isMetricsFetching,
    isError: isMetricsError,
    error: metricsError,
  } = useEventStudyMetrics(metricsParams, { enabled: metricsEnabled });

  const windowOptions: EventStudyWindowPreset[] = windowData?.windows ?? [];
  const events: EventStudyEvent[] = metrics?.events.events ?? [];
  const hasData = Boolean(metrics && metrics.n > 0);

  return (
    <AppShell>
      <div className="space-y-8">
        <section className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-text-secondaryLight dark:text-text-secondaryDark">
                티커 (필수)
              </label>
              <input
                className="rounded-lg border border-border-light bg-background-light px-3 py-2 text-sm outline-none ring-primary focus:ring-2 dark:border-border-dark dark:bg-background-dark"
                value={tickerInput}
                onChange={(event) => setTickerInput(event.target.value)}
                placeholder="예: 005930"
              />
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-text-secondaryLight dark:text-text-secondaryDark">
                윈도우 프리셋
              </label>
              <select
                className="rounded-lg border border-border-light bg-background-light px-3 py-2 text-sm dark:border-border-dark dark:bg-background-dark"
                disabled={isWindowLoading || !windowOptions.length}
                value={resolvedWindowKey ?? ""}
                onChange={(event) => setWindowKey(event.target.value)}
              >
                {windowOptions.map((option) => (
                  <option key={option.key} value={option.key}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-text-secondaryLight dark:text-text-secondaryDark">
                검색어 (기업/이벤트)
              </label>
              <input
                className="rounded-lg border border-border-light bg-background-light px-3 py-2 text-sm outline-none ring-primary focus:ring-2 dark:border-border-dark dark:bg-background-dark"
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder="기업명·키워드 등을 입력하세요"
              />
            </div>
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <div className="flex flex-wrap gap-2">
              {EVENT_TYPE_OPTIONS.map((option) => (
                <FilterChip key={option.value} active={eventType === option.value} onClick={() => setEventType(option.value)}>
                  {option.label}
                </FilterChip>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              {CAP_BUCKET_OPTIONS.map((option) => (
                <FilterChip key={option.value} active={capBucket === option.value} onClick={() => setCapBucket(option.value)}>
                  시가총액 {option.label}
                </FilterChip>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              {MARKET_OPTIONS.map((option) => {
                const active = selectedMarkets.includes(option.value);
                return (
                  <FilterChip
                    key={option.value}
                    active={active}
                    onClick={() =>
                      setSelectedMarkets((prev) =>
                        prev.includes(option.value)
                          ? prev.filter((value) => value !== option.value)
                          : [...prev, option.value],
                      )
                    }
                  >
                    {option.label}
                  </FilterChip>
                );
              })}
            </div>
            <div className="flex flex-wrap gap-2">
              {SIGNIFICANCE_OPTIONS.map((option) => (
                <FilterChip key={option} active={significance === option} onClick={() => setSignificance(option)}>
                  유의수준 {Math.round(option * 100)}%
                </FilterChip>
              ))}
            </div>
          </div>
        </section>

        {!normalizedTicker ? (
          <EmptyState
            title="분석할 티커를 입력해주세요"
            description="좌측 상단에 티커를 입력하면 이벤트 효과와 CAAR/HIT 지표를 바로 확인할 수 있습니다."
          />
        ) : isMetricsLoading ? (
          <div className="flex h-64 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
          </div>
        ) : isMetricsError ? (
          <EmptyState title="지표를 불러오지 못했어요" description={(metricsError as Error)?.message ?? "잠시 후 다시 시도해주세요."} />
        ) : !hasData ? (
          <EmptyState title="일치하는 이벤트가 없어요" description="필터 조건을 조정하거나 분석 기간을 확장해 보세요." />
        ) : (
          <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <MetricCard title="표본 수" value={formatNumber(metrics?.n)} description="해당 조건에 포함된 이벤트 수" />
              <MetricCard title="Hit Rate" value={formatNullablePercent(metrics?.hitRate)} description="양(+)의 CAR 비중" />
              <MetricCard title="평균 CAAR" value={formatNullablePercent(metrics?.meanCaar)} description="윈도우 종료 시점의 평균 CAR" />
              <MetricCard title="p-value" value={metrics ? metrics.pValue.toFixed(4) : "—"} description="단일표본 z-test 결과" />
            </div>

            <div className="grid gap-6 md:grid-cols-5">
              <div className="rounded-2xl border border-border-light bg-background-cardLight p-4 shadow-card dark:border-border-dark dark:bg-background-cardDark md:col-span-3">
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <p className="text-xs uppercase text-text-secondaryLight dark:text-text-secondaryDark">CAAR</p>
                    <p className="text-lg font-semibold">{metrics?.windowLabel}</p>
                  </div>
                  {isMetricsFetching ? <Loader2 className="h-4 w-4 animate-spin text-primary" /> : null}
                </div>
                {metrics?.caar.length ? (
                  <ReactECharts notMerge style={{ height: 280 }} option={buildCaarOption(metrics.caar, metrics.windowLabel)} />
                ) : (
                  <EmptyState title="데이터 없음" description="CAAR 시계열을 계산할 수 있는 이벤트가 부족합니다." />
                )}
              </div>
              <div className="rounded-2xl border border-border-light bg-background-cardLight p-4 shadow-card dark:border-border-dark dark:bg-background-cardDark md:col-span-2">
                <div className="mb-3">
                  <p className="text-xs uppercase text-text-secondaryLight dark:text-text-secondaryDark">Distribution</p>
                  <p className="text-lg font-semibold">CAAR Histogram</p>
                </div>
                {metrics?.dist.length ? (
                  <ReactECharts notMerge style={{ height: 280 }} option={buildHistogramOption(metrics.dist)} />
                ) : (
                  <EmptyState title="분포 데이터 없음" description="해당 조건을 만족하는 이벤트가 없습니다." />
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-border-light bg-background-cardLight p-4 shadow-card dark:border-border-dark dark:bg-background-cardDark">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase text-text-secondaryLight dark:text-text-secondaryDark">Event Breakdown</p>
                  <p className="text-lg font-semibold">총 이벤트 {formatNumber(metrics?.events.total)}</p>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-border-light text-xs uppercase text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
                      <th className="px-2 py-2">날짜</th>
                      <th className="px-2 py-2">기업</th>
                      <th className="px-2 py-2">CAAR</th>
                      <th className="px-2 py-2">피크 시점</th>
                      <th className="px-2 py-2">원문</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((event) => (
                      <tr key={event.receiptNo} className="border-b border-border-light last:border-0 dark:border-border-dark">
                        <td className="px-2 py-2 text-text-secondaryLight dark:text-text-secondaryDark">{formatEventDate(event.eventDate)}</td>
                        <td className="px-2 py-2 font-semibold">
                          <div>{event.corpName ?? "—"}</div>
                          <div className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{event.ticker}</div>
                        </td>
                        <td className="px-2 py-2">{formatNullablePercent(event.caar)}</td>
                        <td className="px-2 py-2">{event.aarPeakDay == null ? "—" : `T${event.aarPeakDay >= 0 ? "+" : ""}${event.aarPeakDay}`}</td>
                        <td className="px-2 py-2">
                          {event.viewerUrl ? (
                            <a
                              href={event.viewerUrl}
                              target="_blank"
                              rel="noreferrer"
                              className="text-primary underline-offset-2 hover:underline"
                            >
                              공시 보기
                            </a>
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}

function MetricCard({ title, value, description }: { title: string; value: string; description?: string }) {
  return (
    <div className="rounded-2xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <p className="text-xs uppercase text-text-secondaryLight dark:text-text-secondaryDark">{title}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
      {description ? (
        <p className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">{description}</p>
      ) : null}
    </div>
  );
}

function formatEventDate(value?: string | null) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit" });
  } catch {
    return value;
  }
}

