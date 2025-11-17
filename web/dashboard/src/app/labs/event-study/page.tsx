"use client";

import dynamic from "next/dynamic";
import { notFound } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Search, Sparkles } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { FilterChip } from "@/components/ui/FilterChip";
import { EventStudyExportButton } from "@/components/event-study/EventStudyExportButton";
import { useEventStudyEvents, useEventStudySummary, type EventStudyEvent, type EventStudySummaryItem } from "@/hooks/useEventStudy";
import { usePlanStore } from "@/store/planStore";
import { buildEventStudyExportParams } from "@/lib/eventStudyExport";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

type EventType = "BUYBACK" | "SEO" | "DIVIDEND" | "RESTATEMENT" | "CONVERTIBLE" | "CONTRACT";
type Market = "KOSPI" | "KOSDAQ";
type CapBucket = "all" | "large" | "mid" | "small";

const EVENT_TYPE_OPTIONS: Array<{ value: EventType; label: string }> = [
  { value: "BUYBACK", label: "자사주 매입/소각" },
  { value: "SEO", label: "유상증자" },
  { value: "DIVIDEND", label: "배당" },
  { value: "RESTATEMENT", label: "정정 공시" },
  { value: "CONVERTIBLE", label: "CB/BW" },
  { value: "CONTRACT", label: "대규모 계약" },
];

const MARKET_OPTIONS: Array<{ value: Market; label: string }> = [
  { value: "KOSPI", label: "KOSPI" },
  { value: "KOSDAQ", label: "KOSDAQ" },
];

const CAP_OPTIONS: Array<{ value: CapBucket; label: string; hint: string }> = [
  { value: "all", label: "전체", hint: "모든 시총" },
  { value: "large", label: "대형", hint: "상위 30%" },
  { value: "mid", label: "중형", hint: "중간 40%" },
  { value: "small", label: "소형", hint: "하위 30%" },
];

const WINDOW_OPTIONS = [
  { key: "-5_5", label: "[-5,+5]", start: -5, end: 5 },
  { key: "-5_20", label: "[-5,+20]", start: -5, end: 20 },
  { key: "-10_30", label: "[-10,+30]", start: -10, end: 30 },
] as const;

const formatPercent = (value: number) => `${value >= 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;
const formatNullablePercent = (value?: number | null) => (value == null ? "—" : formatPercent(value));
const formatInteger = (value: number) => new Intl.NumberFormat("ko-KR").format(value);

export default function EventStudyLabPage() {
  if (process.env.NEXT_PUBLIC_ENABLE_LABS !== "true") {
    notFound();
  }

  const [searchInput, setSearchInput] = useState("");
  const [eventTypes, setEventTypes] = useState<EventType[]>(["BUYBACK", "DIVIDEND"]);
  const [markets, setMarkets] = useState<Market[]>(["KOSPI", "KOSDAQ"]);
  const [capBucket, setCapBucket] = useState<CapBucket>("all");
  const [windowKey, setWindowKey] = useState<typeof WINDOW_OPTIONS[number]["key"]>(WINDOW_OPTIONS[1].key);
  const [significanceThreshold, setSignificanceThreshold] = useState(0.1);
  const exportEntitlementEnabled = usePlanStore((state) => state.featureFlags.reportsEventExport);

  const selectedWindow = WINDOW_OPTIONS.find((option) => option.key === windowKey) ?? WINDOW_OPTIONS[0];

  const summaryParams = useMemo(
    () => ({
      start: selectedWindow.start,
      end: selectedWindow.end,
      scope: "market",
      sig: significanceThreshold,
      eventTypes,
      capBuckets: capBucket === "all" ? undefined : [capBucket.toUpperCase()],
    }),
    [capBucket, eventTypes, selectedWindow.end, selectedWindow.start, significanceThreshold],
  );
  const eventsParams = useMemo(
    () => ({
      windowEnd: selectedWindow.end,
      limit: 100,
      offset: 0,
      eventTypes,
      markets,
      capBuckets: capBucket === "all" ? undefined : [capBucket.toUpperCase()],
      search: searchInput.trim() || undefined,
    }),
    [capBucket, eventTypes, markets, searchInput, selectedWindow.end],
  );
  const buildExportParams = useCallback(() => {
    const currentWindow = WINDOW_OPTIONS.find((option) => option.key === windowKey) ?? WINDOW_OPTIONS[0];
    return buildEventStudyExportParams({
      windowStart: currentWindow.start,
      windowEnd: currentWindow.end,
      scope: "market",
      significance: significanceThreshold,
      eventTypes,
      markets,
      capBuckets: capBucket === "all" ? undefined : [capBucket],
      search: searchInput,
      limit: eventsParams.limit ?? 100,
    });
  }, [capBucket, eventTypes, eventsParams.limit, markets, searchInput, significanceThreshold, windowKey]);

  const { data: summaryData, isLoading: isSummaryLoading } = useEventStudySummary(summaryParams);
  const {
    data: eventsData,
    isLoading: isEventsLoading,
    isFetching: isEventsFetching,
  } = useEventStudyEvents(eventsParams);

  const summaryResults = summaryData?.results ?? [];
  const totalSample = summaryResults.reduce((acc, item) => acc + item.n, 0);
  const weightedMeanCaar =
    totalSample === 0
      ? 0
      : summaryResults.reduce((acc, item) => acc + item.meanCaar * item.n, 0) / totalSample;
  const weightedHitRate =
    totalSample === 0
      ? 0
      : summaryResults.reduce((acc, item) => acc + item.hitRate * item.n, 0) / totalSample;
  const weightedPValue = (() => {
    const weightedRows = summaryResults.filter((item) => typeof item.pValue === "number");
    if (!weightedRows.length) {
      return null;
    }
    const sampleWeight = weightedRows.reduce((acc, item) => acc + item.n, 0);
    if (sampleWeight === 0) {
      return null;
    }
    const aggregated = weightedRows.reduce((acc, item) => acc + (item.pValue ?? 0) * item.n, 0);
    return aggregated / sampleWeight;
  })();
  const visibleEvents = useMemo<EventStudyEvent[]>(() => eventsData?.events ?? [], [eventsData]);
  const selectedEventTypeLabels = EVENT_TYPE_OPTIONS.filter((option) => eventTypes.includes(option.value)).map((option) => option.label);
  const selectedMarketLabels = MARKET_OPTIONS.filter((option) => markets.includes(option.value)).map((option) => option.label);
  const selectedCapMeta = CAP_OPTIONS.find((option) => option.value === capBucket);
  const definitionBadges = [
    { label: "윈도우", value: selectedWindow.label },
    { label: "유의수준", value: `p ≤ ${significanceThreshold.toFixed(2)}` },
    {
      label: "시가총액",
      value: selectedCapMeta ? `${selectedCapMeta.label}${selectedCapMeta.hint ? ` · ${selectedCapMeta.hint}` : ""}` : "전체",
    },
    {
      label: "시장",
      value: selectedMarketLabels.length ? selectedMarketLabels.join(", ") : "선택 안 함",
    },
  ];

  const [focusedEventType, setFocusedEventType] = useState<string | null>(null);
  useEffect(() => {
    if (!summaryResults.length) {
      setFocusedEventType(null);
      return;
    }
    if (focusedEventType && summaryResults.some((item) => item.eventType === focusedEventType)) {
      return;
    }
    setFocusedEventType(summaryResults[0]?.eventType ?? null);
  }, [focusedEventType, summaryResults]);

  const focusedSummary = summaryResults.find((item) => item.eventType === focusedEventType) ?? summaryResults[0];

  const caarOption = useMemo(() => createCaarOption(summaryResults, selectedWindow), [selectedWindow, summaryResults]);
  const histogramOption = useMemo(() => createHistogramOption(focusedSummary), [focusedSummary]);

  const toggleEventType = (value: EventType) => {
    setEventTypes((previous) => {
      if (previous.includes(value)) {
        if (previous.length === 1) {
          return previous;
        }
        return previous.filter((item) => item !== value);
      }
      return [...previous, value];
    });
  };

  const toggleMarket = (value: Market) => {
    setMarkets((previous) => {
      if (previous.includes(value)) {
        const next = previous.filter((item) => item !== value);
        return next.length === 0 ? previous : next;
      }
      return [...previous, value];
    });
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <header className="flex flex-col gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-primary/80 dark:text-primary.dark/80">Labs</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">이벤트 스터디 (전 종목)</h1>
            <p className="mt-2 text-base text-text-secondaryLight dark:text-text-secondaryDark">
              전일 공시를 자동으로 정규화하고 KOSPI/KOSDAQ EOD 수익률과 비교합니다. 원하는 종목을 검색하거나 필터로 좁혀
              AAR(평균 초과수익)/CAAR(누적 초과수익)·히트율을 바로 확인할 수 있어요.
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-dashed border-border-light/80 bg-white/60 px-4 py-3 text-sm text-text-secondaryLight shadow-sm dark:border-border-dark/70 dark:bg-white/5 dark:text-text-secondaryDark">
            <div className="flex items-start gap-3">
              <Sparkles className="mt-0.5 h-4 w-4 text-primary dark:text-primary.dark" />
              <span>
                전 종목 기준 이벤트 스터디 API(`/api/v1/event-study/*`)를 직접 호출해 렌더합니다. 필터를 조정하면 서버 표본이 즉시 다시
                계산됩니다.
              </span>
            </div>
            {exportEntitlementEnabled ? (
              <EventStudyExportButton
                buildParams={buildExportParams}
                variant="secondary"
                size="sm"
                className="rounded-full"
              >
                필터 기준 PDF
              </EventStudyExportButton>
            ) : (
              <span className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">Pro 플랜에서 PDF Export를 사용할 수 있어요.</span>
            )}
          </div>
        </header>

        <section className="rounded-3xl border border-border-light bg-white/90 p-6 shadow-sm dark:border-border-dark dark:bg-background-cardDark">
          <div className="flex flex-col gap-6">
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="relative">
                <label className="mb-1 block text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">
                  종목 검색 (티커·회사명)
                </label>
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondaryLight dark:text-text-secondaryDark" />
                  <input
                    type="search"
                    placeholder="예: 삼성전자, 005930, NAVER"
                    className="w-full rounded-2xl border border-border-light bg-background-light/60 px-10 py-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30 dark:border-border-dark dark:bg-background-dark/80"
                    value={searchInput}
                    onChange={(event) => setSearchInput(event.target.value)}
                  />
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">
                    윈도우
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {WINDOW_OPTIONS.map((option) => (
                      <FilterChip
                        key={option.key}
                        active={windowKey === option.key}
                        onClick={() => setWindowKey(option.key)}
                      >
                        {option.label}
                      </FilterChip>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">
                    유의수준 (p-value)
                  </label>
                  <div className="flex items-center gap-3">
                    <input
                      type="number"
                      min={0.01}
                      max={0.2}
                      step={0.01}
                      value={significanceThreshold.toFixed(2)}
                      onChange={(event) => {
                        const raw = parseFloat(event.target.value);
                        const normalized = Number.isNaN(raw) ? 0.01 : Math.min(Math.max(raw, 0.01), 0.2);
                        setSignificanceThreshold(parseFloat(normalized.toFixed(2)));
                      }}
                      className="w-24 rounded-2xl border border-border-light bg-background-light/60 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30 dark:border-border-dark dark:bg-background-dark/80"
                    />
                    <span className="text-sm font-semibold text-primary dark:text-primary.dark">p ≤ {significanceThreshold.toFixed(2)}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">이벤트 유형</p>
                <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  {eventTypes.length ? `${eventTypes.length}개 선택됨` : "0개 선택"}
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                {EVENT_TYPE_OPTIONS.map((option) => (
                  <FilterChip key={option.value} active={eventTypes.includes(option.value)} onClick={() => toggleEventType(option.value)}>
                    {option.label}
                  </FilterChip>
                ))}
              </div>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">시장</p>
                <div className="flex flex-wrap gap-2">
                  {MARKET_OPTIONS.map((option) => (
                    <FilterChip key={option.value} active={markets.includes(option.value)} onClick={() => toggleMarket(option.value)}>
                      {option.label}
                    </FilterChip>
                  ))}
                </div>
              </div>
              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">시가총액</p>
                <div className="flex flex-wrap gap-2">
                  {CAP_OPTIONS.map((option) => (
                    <FilterChip key={option.value} active={capBucket === option.value} onClick={() => setCapBucket(option.value)}>
                      {option.label}
                      <span className="ml-1 text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">{option.hint}</span>
                    </FilterChip>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-3xl border border-border-light bg-gradient-to-br from-white via-white to-background-light/80 p-6 shadow-sm dark:border-border-dark dark:bg-background-cardDark">
          <div className="flex flex-col gap-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-text-secondaryLight dark:text-text-secondaryDark">
                  Event Definition
                </p>
                <h2 className="mt-1 text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark">선택한 필터 요약</h2>
                <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                  {selectedEventTypeLabels.length
                    ? `${selectedEventTypeLabels.join(", ")} 등 ${eventTypes.length}개의 이벤트 유형을 기반으로 분석합니다.`
                    : "이벤트 유형을 선택하면 조건에 맞는 공시 이벤트가 집계됩니다."}
                </p>
              </div>
              <div className="rounded-2xl border border-border-light/60 bg-white/70 px-4 py-2 text-sm font-semibold text-text-secondaryLight dark:border-border-dark/60 dark:bg-background-dark/70 dark:text-text-secondaryDark">
                표본 <span className="text-text-primaryLight dark:text-text-primaryDark">{formatInteger(totalSample)}</span>건
              </div>
            </div>
            <div className="grid gap-4 lg:grid-cols-[2fr,3fr]">
              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">주요 조건</p>
                <div className="flex flex-wrap gap-2">
                  {definitionBadges.map((item) => (
                    <DefinitionBadge key={item.label} label={item.label} value={item.value} />
                  ))}
                </div>
              </div>
              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">선택 이벤트 유형</p>
                {selectedEventTypeLabels.length ? (
                  <div className="grid gap-2 md:grid-cols-2">
                    {selectedEventTypeLabels.map((label) => (
                      <div
                        key={label}
                        className="rounded-2xl border border-border-light/70 bg-white/70 px-4 py-2 text-sm font-medium text-text-primaryLight shadow-sm dark:border-border-dark/70 dark:bg-background-dark/70 dark:text-text-primaryDark"
                      >
                        {label}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-border-light/70 px-4 py-6 text-sm text-text-secondaryLight dark:border-border-dark/60 dark:text-text-secondaryDark">
                    이벤트 유형을 최소 1개 이상 선택하면 조건에 맞는 통계가 노출됩니다.
                  </div>
                )}
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <SummaryCard title="표본" description="필터를 조정하면 표본이 즉시 업데이트됩니다.">
            {isSummaryLoading ? <Loader2 className="h-6 w-6 animate-spin text-primary" /> : <span>{totalSample}</span>}
          </SummaryCard>
          <SummaryCard
            title="평균 누적 초과수익 (CAAR)"
            description={`${selectedWindow.label} 윈도우 · p ≤ ${significanceThreshold.toFixed(2)}`}
          >
            {isSummaryLoading ? <Loader2 className="h-6 w-6 animate-spin text-primary" /> : <span>{formatPercent(weightedMeanCaar)}</span>}
          </SummaryCard>
          <SummaryCard title="히트율" description="양의 누적 초과수익 비중">
            {isSummaryLoading ? <Loader2 className="h-6 w-6 animate-spin text-primary" /> : <span>{formatPercent(weightedHitRate)}</span>}
          </SummaryCard>
          <SummaryCard title="평균 p-value" description="표본 가중 평균">
            {isSummaryLoading ? (
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            ) : weightedPValue == null ? (
              <span>—</span>
            ) : (
              <span>{weightedPValue.toFixed(2)}</span>
            )}
          </SummaryCard>
        </section>

        <section className="rounded-3xl border border-border-light bg-white/90 p-5 shadow-sm dark:border-border-dark dark:bg-background-cardDark">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">이벤트 유형별 반응</p>
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                {selectedWindow.label} 구간 기준 CAAR·Hit Rate·p-value를 한 번에 비교합니다.
              </p>
            </div>
            <div className="rounded-full border border-border-light/70 px-3 py-1 text-xs font-semibold text-text-secondaryLight dark:border-border-dark/70 dark:text-text-secondaryDark">
              p ≤ {significanceThreshold.toFixed(2)}
            </div>
          </div>
          <div className="mt-4">
            {isSummaryLoading ? (
              <ChartLoading />
            ) : (
              <EventTypeSummaryTable rows={summaryResults} windowLabel={selectedWindow.label} significance={significanceThreshold} />
            )}
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <ChartCard title="누적 초과수익 (CAAR) 추이" description="이벤트 유형별 누적 평균 초과수익">
            {isSummaryLoading ? (
              <ChartLoading />
            ) : caarOption ? (
              <ReactECharts option={caarOption} style={{ height: 320 }} />
            ) : (
              <ChartEmpty message="표시할 누적 초과수익 (CAAR) 데이터가 없습니다." />
            )}
          </ChartCard>
          <ChartCard
            title="누적 초과수익 (CAAR) 분포"
            description={focusedSummary ? `${getEventTypeLabel(focusedSummary.eventType)} 이벤트 기준` : "데이터 없음"}
            action={
              summaryResults.length > 1 ? (
                <div className="flex flex-wrap gap-2">
                  {summaryResults.map((item) => (
                    <FilterChip
                      key={item.eventType}
                      active={item.eventType === focusedEventType}
                      onClick={() => setFocusedEventType(item.eventType)}
                    >
                      {getEventTypeLabel(item.eventType)}
                    </FilterChip>
                  ))}
                </div>
              ) : null
            }
          >
            {isSummaryLoading ? (
              <ChartLoading />
            ) : histogramOption ? (
              <ReactECharts option={histogramOption} style={{ height: 320 }} />
            ) : (
              <ChartEmpty message="분포 데이터를 불러오지 못했습니다." />
            )}
          </ChartCard>
        </section>

        <section className="rounded-3xl border border-border-light bg-white shadow-sm dark:border-border-dark dark:bg-background-cardDark">
          <div className="border-b border-border-light px-6 py-4 dark:border-border-dark">
            <h2 className="text-base font-semibold">최근 이벤트</h2>
            <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
              필터와 검색어가 적용된 이벤트 목록입니다. 누적 초과수익 (CAAR)은 선택한 윈도우 종료일 기준으로 계산됩니다.
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border-light text-sm dark:divide-border-dark">
              <thead className="bg-background-light/60 dark:bg-background-dark/60">
                <tr>
                  <th className="px-6 py-3 text-left font-medium text-text-secondaryLight dark:text-text-secondaryDark">회사</th>
                  <th className="px-6 py-3 text-left font-medium text-text-secondaryLight dark:text-text-secondaryDark">일자</th>
                  <th className="px-6 py-3 text-left font-medium text-text-secondaryLight dark:text-text-secondaryDark">시장</th>
                  <th className="px-6 py-3 text-left font-medium text-text-secondaryLight dark:text-text-secondaryDark">이벤트 유형</th>
                  <th className="px-6 py-3 text-left font-medium text-text-secondaryLight dark:text-text-secondaryDark">
                    +{selectedWindow.end}D 누적 초과수익 (CAAR)
                  </th>
                  <th className="px-6 py-3 text-left font-medium text-text-secondaryLight dark:text-text-secondaryDark">피크 AAR</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-light dark:divide-border-dark">
                {isEventsLoading ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-8 text-center text-text-secondaryLight dark:text-text-secondaryDark">
                      데이터를 불러오는 중입니다…
                    </td>
                  </tr>
                ) : visibleEvents.length ? (
                  visibleEvents.map((event) => (
                    <tr key={event.receiptNo} className="hover:bg-primary/5 dark:hover:bg-primary.dark/10">
                      <td className="px-6 py-4">
                        <div className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{event.corpName}</div>
                        <div className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{event.ticker}</div>
                      </td>
                      <td className="px-6 py-4">{event.eventDate ?? "—"}</td>
                      <td className="px-6 py-4">{event.market ?? "N/A"}</td>
                      <td className="px-6 py-4">{EVENT_TYPE_OPTIONS.find((option) => option.value === event.eventType)?.label ?? event.eventType}</td>
                      <td className="px-6 py-4 font-semibold">{formatNullablePercent(event.caar)}</td>
                      <td className="px-6 py-4">
                        {event.aarPeakDay != null ? (
                          <>
                            t = <span className="font-semibold">{event.aarPeakDay >= 0 ? `+${event.aarPeakDay}` : event.aarPeakDay}</span>일
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="px-6 py-8 text-center text-text-secondaryLight dark:text-text-secondaryDark">
                      조건에 맞는 이벤트가 없습니다. 다른 필터를 선택해 주세요.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            {isEventsFetching && !isEventsLoading ? (
              <div className="flex items-center justify-center gap-2 border-t border-border-light px-6 py-3 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                최신 데이터를 동기화하는 중입니다…
              </div>
            ) : null}
          </div>
        </section>
      </div>
    </AppShell>
  );
}

type SummaryCardProps = {
  title: string;
  description: string;
  children: React.ReactNode;
};

function SummaryCard({ title, description, children }: SummaryCardProps) {
  return (
    <div className="rounded-3xl border border-border-light bg-white/80 p-5 shadow-sm dark:border-border-dark dark:bg-background-cardDark">
      <p className="text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">{title}</p>
      <div className="mt-1 text-3xl font-semibold text-text-primaryLight dark:text-text-primaryDark">{children}</div>
      <p className="mt-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">{description}</p>
    </div>
  );
}

type ChartCardProps = {
  title: string;
  description?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
};

function ChartCard({ title, description, action, children }: ChartCardProps) {
  return (
    <div className="rounded-3xl border border-border-light bg-white/90 p-5 shadow-sm dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">{title}</p>
          {description ? (
            <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{description}</p>
          ) : null}
        </div>
        {action}
      </div>
      <div className="mt-4 min-h-[320px]">{children}</div>
    </div>
  );
}

function ChartLoading() {
  return (
    <div className="flex h-full items-center justify-center text-text-secondaryLight dark:text-text-secondaryDark">
      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
      데이터를 불러오는 중입니다…
    </div>
  );
}

function ChartEmpty({ message }: { message: string }) {
  return <div className="flex h-full items-center justify-center text-sm text-text-secondaryLight dark:text-text-secondaryDark">{message}</div>;
}

function getEventTypeLabel(code: string) {
  return EVENT_TYPE_OPTIONS.find((option) => option.value === code)?.label ?? code;
}

type DefinitionBadgeProps = {
  label: string;
  value: string;
};

function DefinitionBadge({ label, value }: DefinitionBadgeProps) {
  return (
    <div className="flex items-center gap-2 rounded-full border border-border-light/70 bg-white/70 px-3 py-1.5 text-[11px] font-semibold text-text-secondaryLight shadow-sm dark:border-border-dark/70 dark:bg-background-dark/60 dark:text-text-secondaryDark">
      <span className="text-text-primaryLight dark:text-text-primaryDark">{label}</span>
      <span className="font-normal text-text-secondaryLight dark:text-text-secondaryDark">{value}</span>
    </div>
  );
}

function createCaarOption(summary: EventStudySummaryItem[], window: typeof WINDOW_OPTIONS[number]) {
  if (!summary.length) {
    return null;
  }
  return {
    tooltip: {
      trigger: "axis",
      formatter: (params: Array<{ seriesName: string; value: [number, number] }>) =>
        params
          .map((item) => `${item.seriesName}: <strong>${formatPercent(item.value[1])}</strong> (t=${item.value[0]})`)
          .join("<br/>"),
    },
    legend: {
      data: summary.map((item) => getEventTypeLabel(item.eventType)),
      textStyle: { color: "#94a3b8" },
    },
    grid: { top: 40, left: 40, right: 20, bottom: 30 },
    xAxis: {
      type: "value",
      min: window.start,
      max: window.end,
      axisLine: { lineStyle: { color: "#334155" } },
      axisLabel: { color: "#94a3b8" },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      splitLine: { lineStyle: { color: "rgba(148,163,184,0.2)" } },
      axisLabel: {
        color: "#94a3b8",
        formatter: (value: number) => `${(value * 100).toFixed(1)}%`,
      },
    },
    series: summary.map((item) => ({
      name: getEventTypeLabel(item.eventType),
      type: "line",
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 3 },
      data: item.caar.map((point) => [point.t, point.value]),
    })),
  };
}

function createHistogramOption(summary?: EventStudySummaryItem) {
  if (!summary || !summary.dist?.length) {
    return null;
  }
  const categories = summary.dist.map((bin) => `${formatPercent(bin.range[0])} ~ ${formatPercent(bin.range[1])}`);
  const counts = summary.dist.map((bin) => bin.count);
  return {
    tooltip: {
      trigger: "item",
      formatter: ({ name, value }: { name: string; value: number }) => `${name}: <strong>${value}건</strong>`,
    },
    grid: { top: 20, left: 30, right: 10, bottom: 40 },
    xAxis: {
      type: "category",
      data: categories,
      axisLabel: { rotate: 45, color: "#94a3b8" },
      axisLine: { lineStyle: { color: "#334155" } },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#94a3b8" },
      splitLine: { lineStyle: { color: "rgba(148,163,184,0.2)" } },
    },
    series: [
      {
        type: "bar",
        data: counts,
        itemStyle: { color: "#5B7BFF", borderRadius: [6, 6, 0, 0] },
      },
    ],
  };
}

type EventTypeSummaryTableProps = {
  rows: EventStudySummaryItem[];
  windowLabel: string;
  significance: number;
};

function EventTypeSummaryTable({ rows, windowLabel, significance }: EventTypeSummaryTableProps) {
  if (!rows.length) {
    return (
      <div className="rounded-2xl border border-dashed border-border-light/70 px-4 py-6 text-center text-sm text-text-secondaryLight dark:border-border-dark/70 dark:text-text-secondaryDark">
        조건에 맞는 이벤트 유형 통계가 없습니다. 필터를 조정해 보세요.
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-border-light text-sm dark:divide-border-dark">
        <thead className="bg-background-light/60 text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:bg-background-dark/40 dark:text-text-secondaryDark">
          <tr>
            <th className="px-4 py-3 text-left">이벤트 유형</th>
            <th className="px-4 py-3 text-right">표본</th>
            <th className="px-4 py-3 text-right">{windowLabel} CAAR</th>
            <th className="px-4 py-3 text-right">Hit Rate</th>
            <th className="px-4 py-3 text-right">신뢰구간</th>
            <th className="px-4 py-3 text-right">p-value</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-light dark:divide-border-dark">
          {rows.map((row) => (
            <tr key={`${row.eventType}-${row.capBucket ?? "all"}`} className="hover:bg-primary/5 dark:hover:bg-primary.dark/10">
              <td className="px-4 py-3 font-medium text-text-primaryLight dark:text-text-primaryDark">{getEventTypeLabel(row.eventType)}</td>
              <td className="px-4 py-3 text-right font-semibold text-text-primaryLight dark:text-text-primaryDark">{formatInteger(row.n)}</td>
              <td className="px-4 py-3 text-right">{formatPercent(row.meanCaar)}</td>
              <td className="px-4 py-3 text-right">{formatPercent(row.hitRate)}</td>
              <td className="px-4 py-3 text-right text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                {formatPercent(row.ciLo)} ~ {formatPercent(row.ciHi)}
              </td>
              <td className="px-4 py-3 text-right">
                <SignificanceBadge value={row.pValue} threshold={significance} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type SignificanceBadgeProps = {
  value?: number;
  threshold: number;
};

function SignificanceBadge({ value, threshold }: SignificanceBadgeProps) {
  if (value == null) {
    return <span className="text-text-secondaryLight dark:text-text-secondaryDark">—</span>;
  }
  const isSignificant = value <= threshold;
  return (
    <span
      className={`inline-flex items-center justify-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${
        isSignificant
          ? "bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-200"
          : "bg-slate-200/60 text-slate-600 dark:bg-slate-700/60 dark:text-slate-200"
      }`}
    >
      {value.toFixed(2)}
      {isSignificant ? " · 유의" : ""}
    </span>
  );
}
