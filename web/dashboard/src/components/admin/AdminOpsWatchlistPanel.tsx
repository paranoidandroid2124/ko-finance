"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, CalendarClock, RefreshCw } from "lucide-react";

import { KpiCard, type KpiCardProps } from "@/components/ui/KpiCard";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { FilterChip } from "@/components/ui/FilterChip";
import { EventMatchList } from "@/components/watchlist/EventMatchList";
import { useWatchlistRadar, useAlertEventMatches } from "@/hooks/useAlerts";
import { useAlertPresetUsage } from "@/hooks/useAdminConfig";
import type { AlertEventMatch, WatchlistRadarItem } from "@/lib/alertsApi";
import { formatDateTime } from "@/lib/date";
import type { ToastInput } from "@/store/toastStore";

const WINDOW_OPTIONS = [
  { minutes: 180, label: "최근 3시간" },
  { minutes: 720, label: "최근 12시간" },
  { minutes: 1440, label: "최근 24시간" },
  { minutes: 10_080, label: "최근 7일" },
];

const CHANNEL_LABEL_MAP: Record<string, string> = {
  slack: "Slack",
  email: "이메일",
};

const EMPTY_ITEMS: WatchlistRadarItem[] = [];

export type AdminOpsWatchlistPanelProps = {
  adminActor: string;
  toast: (input: ToastInput) => void;
};

const resolveTopChannel = (channels: Record<string, number> | undefined | null) => {
  if (!channels) {
    return null;
  }
  const entries = Object.entries(channels)
    .map(([channel, count]) => ({ channel, count }))
    .filter((entry) => entry.count > 0);
  if (entries.length === 0) {
    return null;
  }
  entries.sort((a, b) => {
    if (b.count === a.count) {
      return a.channel.localeCompare(b.channel);
    }
    return b.count - a.count;
  });
  return entries[0];
};

export function AdminOpsWatchlistPanel({ adminActor: _adminActor, toast }: AdminOpsWatchlistPanelProps) {
  const [windowMinutes, setWindowMinutes] = useState<number>(720);
  const watchlistRequest = useMemo(
    () => ({
      windowMinutes,
      limit: 80,
    }),
    [windowMinutes],
  );

  const { data, isLoading, isFetching, error, refetch } = useWatchlistRadar(watchlistRequest);
  const { data: eventMatchesData, isLoading: isEventMatchLoading } = useAlertEventMatches({ limit: 10 });
  const { data: presetUsageData, isLoading: isPresetUsageLoading } = useAlertPresetUsage(14, true);
  const summary = data?.summary;
  const items = data?.items ?? EMPTY_ITEMS;
  const generatedAtLabel =
    formatDateTime(data?.generatedAt, { includeSeconds: true, fallback: "생성 시각 미상" });
  const eventMatches = eventMatchesData?.matches ?? [];

  const numberFormatter = useMemo(() => new Intl.NumberFormat("ko-KR"), []);
  const topTickerLabel = (summary?.topTickers ?? []).slice(0, 3).join(", ");
  const topChannel = resolveTopChannel(summary?.topChannels);
  const topFailureChannel = resolveTopChannel(summary?.channelFailures);
  const failedCount = summary?.failedDeliveries ?? 0;

  const summaryCards: KpiCardProps[] = useMemo(
    () => [
      {
        title: "전달된 알림",
        value: `${numberFormatter.format(summary?.totalDeliveries ?? 0)}건`,
        delta:
          summary && summary.totalEvents > 0
            ? `+${numberFormatter.format(summary.totalEvents)} 이벤트`
            : "이벤트 집계 없음",
        trend: (summary?.totalDeliveries ?? 0) > 0 ? "up" : "flat",
        description: `최근 ${WINDOW_OPTIONS.find((opt) => opt.minutes === windowMinutes)?.label ?? "선택 윈도우"}
동안 Slack·이메일로 전송된 워치리스트 알림 수입니다.`,
      },
      {
        title: "커버된 종목",
        value: `${numberFormatter.format(summary?.uniqueTickers ?? 0)}개`,
        delta: topTickerLabel ? `Top: ${topTickerLabel}` : "주요 종목 없음",
        trend: (summary?.uniqueTickers ?? 0) > 0 ? "up" : "flat",
        description: "워치리스트 룰이 울린 기업/종목을 개수 기준으로 집계했어요.",
      },
      {
        title: "히트 룰 · 채널",
        value: summary?.topRules?.[0] ?? "주요 룰 없음",
        delta: topChannel
          ? `${CHANNEL_LABEL_MAP[topChannel.channel] ?? topChannel.channel} · ${numberFormatter.format(topChannel.count)}회`
          : "채널 집계 없음",
        trend: "flat",
        description: "가장 많이 울린 룰과 채널을 확인해 워크플로우를 점검해 보세요.",
      },
      {
        title: "전송 실패",
        value: `${numberFormatter.format(failedCount)}건`,
        delta: topFailureChannel
          ? `${CHANNEL_LABEL_MAP[topFailureChannel.channel] ?? topFailureChannel.channel} · ${numberFormatter.format(topFailureChannel.count)}회`
          : "최근 실패 없음",
        trend: failedCount > 0 ? "down" : "flat",
        description: "Slack·이메일 채널의 전송 실패 건수를 집중 모니터링합니다.",
      },
    ],
    [failedCount, numberFormatter, summary, topChannel, topFailureChannel, topTickerLabel, windowMinutes],
  );

  const failingItems = useMemo(
    () =>
      items
        .filter((item) => (item.deliveryStatus ?? "").toLowerCase() === "failed")
        .slice(0, 8),
    [items],
  );

  const failureSummary = useMemo(() => {
    const failures = summary?.channelFailures ?? {};
    return Object.entries(failures)
      .map(([channel, count]) => ({
        channel,
        count,
      }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);
  }, [summary?.channelFailures]);

  const handleRefresh = () => {
    void refetch();
    toast({
      intent: "info",
      message: "워치리스트 레이더를 새로고침합니다.",
    });
  };

  return (
    <section className="space-y-4 rounded-xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <header className="space-y-1 border-b border-border-light pb-3 dark:border-border-dark">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">워치리스트 실패 모니터링</h3>
            <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
              운영자가 확인해야 할 워치리스트 알림 현황과 실패 기록을 모아 보여줍니다.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleRefresh}
              className="inline-flex items-center gap-2 rounded-lg border border-border-light px-3 py-1.5 text-sm font-semibold text-text-primaryLight transition hover:border-primary/50 hover:text-primary dark:border-border-dark dark:text-text-primaryDark dark:hover:border-primary.dark/50 dark:hover:text-primary.dark"
            >
              <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} aria-hidden />
              새로고침
            </button>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          <CalendarClock className="h-4 w-4" aria-hidden />
          <span>윈도우: {WINDOW_OPTIONS.find((opt) => opt.minutes === windowMinutes)?.label ?? "사용자 지정"}</span>
          <span> · </span>
          <span>생성 {generatedAtLabel}</span>
        </div>
      </header>

      <section className="flex flex-wrap items-center gap-2">
        {WINDOW_OPTIONS.map((option) => (
          <FilterChip
            key={option.minutes}
            active={option.minutes === windowMinutes}
            onClick={() => setWindowMinutes(option.minutes)}
          >
            {option.label}
          </FilterChip>
        ))}
      </section>

      {error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
          워치리스트 레이더 데이터를 불러오는 데 실패했습니다. 네트워크 상태를 확인한 후 다시 시도해 주세요.
        </div>
      ) : null}

      {isLoading ? (
        <section className="grid gap-3 md:grid-cols-2">
          <SkeletonBlock lines={4} />
          <SkeletonBlock lines={4} />
          <SkeletonBlock lines={4} />
          <SkeletonBlock lines={4} />
        </section>
      ) : (
        <section className="grid gap-3 md:grid-cols-2">
          {summaryCards.map((card) => (
            <KpiCard key={card.title} {...card} />
          ))}
        </section>
      )}

      <section className="rounded-xl border border-border-light bg-background-base p-4 shadow-card dark:border-border-dark dark:bg-background-cardDark">
        {isPresetUsageLoading ? (
          <SkeletonBlock lines={3} />
        ) : (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
                프리셋 온보딩 · 최근 {presetUsageData?.windowDays ?? 14}일
              </p>
              <h4 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">
                총 {numberFormatter.format(presetUsageData?.totalLaunches ?? 0)}회 생성
              </h4>
              <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                Top Preset:{" "}
                {presetUsageData?.presets?.[0]
                  ? `${presetUsageData.presets[0].name ?? presetUsageData.presets[0].presetId} (${numberFormatter.format(presetUsageData.presets[0].count)}회)`
                  : "데이터 없음"}
              </p>
              {presetUsageData?.presets?.[0]?.lastUsedAt ? (
                <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
                  최근 실행: {formatDateTime(presetUsageData.presets[0].lastUsedAt, { includeTime: false })}
                </p>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              {Object.entries(presetUsageData?.presets?.[0]?.channelTotals ?? {}).map(([channel, count]) => (
                <span
                  key={`preset-channel-${channel}`}
                  className="inline-flex items-center gap-1 rounded-full border border-border-light px-2 py-0.5 dark:border-border-dark"
                >
                  {CHANNEL_LABEL_MAP[channel] ?? channel}
                  <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                    {numberFormatter.format(count)}
                  </span>
                </span>
              ))}
              {presetUsageData?.bundles?.[0] ? (
                <span className="inline-flex items-center gap-1 rounded-full border border-border-light px-2 py-0.5 dark:border-border-dark">
                  번들 {presetUsageData.bundles[0].label ?? presetUsageData.bundles[0].bundle}
                  <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                    {numberFormatter.format(presetUsageData.bundles[0].count)}
                  </span>
                </span>
              ) : null}
            </div>
          </div>
        )}
      </section>

      {failedCount > 0 ? (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden />
          <div className="space-y-1">
            <p className="font-semibold">
              최근 전송 실패 {numberFormatter.format(failedCount)}건이 감지되었습니다. 재시도가 필요해요.
            </p>
            {topFailureChannel ? (
              <p className="text-xs">
                가장 많이 실패한 채널: {CHANNEL_LABEL_MAP[topFailureChannel.channel] ?? topFailureChannel.channel} (
                {numberFormatter.format(topFailureChannel.count)}회)
              </p>
            ) : null}
          </div>
        </div>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-[2fr,1fr]">
        <div className="space-y-3 rounded-xl border border-border-light bg-background-base p-4 shadow-card dark:border-border-dark dark:bg-background-cardDark">
          <h4 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">채널별 실패 집계</h4>
          {failureSummary.length === 0 ? (
            <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">최근 실패 데이터가 없습니다.</p>
          ) : (
            <ul className="space-y-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
              {failureSummary.map((entry) => (
                <li key={entry.channel} className="flex items-center justify-between rounded-lg border border-border-light px-3 py-2 dark:border-border-dark">
                  <span>{CHANNEL_LABEL_MAP[entry.channel] ?? entry.channel}</span>
                  <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                    {numberFormatter.format(entry.count)}회
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="space-y-3 rounded-xl border border-border-light bg-background-base p-4 shadow-card dark:border-border-dark dark:bg-background-cardDark">
          <h4 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">최근 실패 이벤트</h4>
          {failingItems.length === 0 ? (
            <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
              최근 윈도우 안에서 실패한 알림이 없습니다.
            </p>
          ) : (
            <ul className="space-y-3">
              {failingItems.map((item) => (
                <li key={item.deliveryId} className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                      {item.ruleName ?? "이름 없는 룰"}
                    </span>
                    <span>{formatDateTime(item.deliveredAt, { includeSeconds: true, fallback: "시간 미상" })}</span>
                  </div>
                  <div className="mt-1 space-y-1 text-text-secondaryLight dark:text-text-secondaryDark">
                    <p>{item.ticker ? `${item.ticker} · ${item.company ?? "기업 미상"}` : "티커 없음"}</p>
                    <p>채널: {CHANNEL_LABEL_MAP[item.channel ?? ""] ?? item.channel ?? "미상"}</p>
                    {item.deliveryError ? (
                      <p className="text-amber-700 dark:text-amber-200">오류: {item.deliveryError}</p>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <AdminEventMatchPanel matches={eventMatches} loading={isEventMatchLoading} />

      <div className="rounded-xl border border-border-light bg-background-base p-4 text-sm text-text-secondaryLight shadow-card dark:border-border-dark dark:bg-background-cardDark dark:text-text-secondaryDark">
        <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">전체 로그 보기</p>
        <p className="mt-1 text-xs leading-relaxed">
          더 자세한 히스토리는 워치리스트 레이더 페이지에서 확인하거나 Slack 재전송 버튼을 사용해 주세요.
          <span className="ml-1">
            <a href="/alerts" className="font-semibold text-primary underline dark:text-primary.dark">
              사용자 화면 열기
            </a>
          </span>
        </p>
      </div>
    </section>
  );
}

type AdminEventMatchPanelProps = {
  matches: AlertEventMatch[];
  loading: boolean;
};

const AdminEventMatchPanel = ({ matches, loading }: AdminEventMatchPanelProps) => (
  <div className="space-y-2 rounded-xl border border-border-light bg-background-base p-4 dark:border-border-dark dark:bg-background-baseDark">
    <div className="flex items-center justify-between">
      <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">최근 이벤트 매칭</p>
      <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">최근 {matches.length}건</span>
    </div>
    <EventMatchList
      matches={matches}
      loading={loading}
      limit={8}
      emptyMessage="최근 매칭된 이벤트가 없습니다. 공시 이벤트가 감지되면 이곳에 로그가 쌓입니다."
    />
  </div>
);
