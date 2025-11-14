"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { KpiCard } from "@/components/ui/KpiCard";
import { AlertFeed } from "@/components/ui/AlertFeed";
import { NewsList } from "@/components/ui/NewsList";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { FilingTrendChart } from "@/components/charts/FilingTrendChart";
import { useDashboardOverview } from "@/hooks/useDashboardOverview";
import { useSectorSignals } from "@/hooks/useSectorSignals";
import { SectorHotspotScatter } from "@/components/sectors/SectorHotspotScatter";
import { SectorSparkCard } from "@/components/sectors/SectorSparkCard";
import { GlobalSearchBar } from "@/components/search/GlobalSearchBar";

const EVENT_SEVERITY_CLASS: Record<string, string> = {
  info: "bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-200",
  warning: "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200",
  critical: "bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-200",
  neutral: "bg-slate-100 text-slate-600 dark:bg-slate-700/40 dark:text-slate-200",
};

const formatRelativeTime = (value?: string | null) => {
  if (!value) {
    return "방금 전";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "방금 전";
  }
  const diffMs = Date.now() - parsed.getTime();
  const minutes = Math.max(0, Math.round(diffMs / 60000));
  if (minutes < 1) {
    return "방금 전";
  }
  if (minutes < 60) {
    return `${minutes}분 전`;
  }
  const hours = Math.round(minutes / 60);
  if (hours < 24) {
    return `${hours}시간 전`;
  }
  const days = Math.round(hours / 24);
  return `${days}일 전`;
};

export default function DashboardPage() {
  const router = useRouter();
  const { data, isLoading, isError } = useDashboardOverview();
  const [searchInput, setSearchInput] = useState("");

  const metrics = data?.metrics ?? [];
  const alerts = data?.alerts ?? [];
  const newsItems = data?.news ?? [];
  const watchlists = data?.watchlists ?? [];
  const events = data?.events ?? [];
  const quickLinks = data?.quickLinks ?? [];
  const { data: sectorSignals, isLoading: isSectorLoading } = useSectorSignals();
  const sectorPoints = useMemo(() => sectorSignals?.points ?? [], [sectorSignals]);
  const dashboardSparkPoints = useMemo(() => {
    const sorted = [...sectorPoints].sort((a, b) => (b.sentimentZ ?? 0) - (a.sentimentZ ?? 0));
    const unique = new Map<number, (typeof sectorPoints)[number]>();
    sorted.forEach((point) => {
      if (!unique.has(point.sector.id)) {
        unique.set(point.sector.id, point);
      }
    });
    return Array.from(unique.values()).slice(0, 3);
  }, [sectorPoints]);

  const handleSearchSubmit = () => {
    const trimmed = searchInput.trim();
    const params = new URLSearchParams();
    if (trimmed) {
      params.set("q", trimmed);
    }
    const query = params.toString();
    router.push(query ? `/search?${query}` : "/search");
  };

  const handleAlertSelect = (alert: (typeof alerts)[number]) => {
    const target = alert?.targetUrl?.trim();
    if (!alert || !target) {
      return;
    }
    if (/^https?:\/\//i.test(target)) {
      window.open(target, "_blank", "noopener,noreferrer");
      return;
    }
    router.push(target as Parameters<typeof router.push>[0]);
  };

  const renderQuickLinks = () => {
    if (quickLinks.length === 0) {
      return (
        <div className="rounded-xl border border-dashed border-border-light px-4 py-3 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
          최근 검색 기록이 없습니다. 위 검색창에서 관심 종목을 찾아보세요.
        </div>
      );
    }
    return (
      <div className="flex flex-wrap gap-2">
        {quickLinks.map((link) => (
          <button
            key={`${link.type}-${link.href}`}
            type="button"
            onClick={() => router.push(link.href)}
            className="rounded-full border border-border-light px-3 py-1 text-xs font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
          >
            {link.label}
          </button>
        ))}
      </div>
    );
  };

  const renderWatchlistSummary = () => {
    if (watchlists.length === 0) {
      return (
        <EmptyState
          title="요약할 워치리스트가 없습니다"
          description="Watchlist 페이지에서 감시할 테마를 추가하면 이곳에서 요약됩니다."
          className="border-none p-0"
        />
      );
    }
    return (
      <ul className="space-y-4">
        {watchlists.map((item) => (
          <li key={item.ruleId} className="rounded-xl border border-border-light px-4 py-3 dark:border-border-dark">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">{item.name}</p>
                <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  {item.lastHeadline ?? "최근 알림 요약 없음"}
                </p>
              </div>
              <div className="text-right">
                <span className="text-2xl font-bold text-text-primaryLight dark:text-text-primaryDark">
                  {item.eventCount}
                </span>
                <p className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">알림</p>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
              {item.tickers.slice(0, 4).map((ticker) => (
                <span key={`${item.ruleId}-${ticker}`} className="rounded-full bg-background-cardLight px-2 py-0.5 dark:bg-background-cardDark">
                  {ticker}
                </span>
              ))}
              <span>{formatRelativeTime(item.lastTriggeredAt)}</span>
            </div>
            <button
              type="button"
              className="mt-3 text-xs font-semibold text-primary hover:underline dark:text-primary.dark"
              onClick={() => router.push(item.detailUrl ?? "/watchlist")}
            >
              상세 보기
            </button>
          </li>
        ))}
      </ul>
    );
  };

  const renderEventList = () => {
    if (events.length === 0) {
      return (
        <EmptyState
          title="오늘 감지된 이벤트가 없습니다"
          description="새로운 공시가 집계되면 의미 있는 이벤트가 여기에 나타납니다."
          className="border-none p-0"
        />
      );
    }
    return (
      <ul className="space-y-3">
        {events.map((event) => (
          <li key={event.id} className="rounded-xl border border-border-light px-4 py-3 dark:border-border-dark">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">{event.title}</p>
                <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  {event.corpName || event.ticker || "기업 미지정"} · {formatRelativeTime(event.filedAt)}
                </p>
              </div>
              <span
                className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                  EVENT_SEVERITY_CLASS[event.severity] ?? EVENT_SEVERITY_CLASS.info
                }`}
              >
                {event.eventType ?? "event"}
              </span>
            </div>
            {event.targetUrl ? (
              <button
                type="button"
                onClick={() => router.push(event.targetUrl!)}
                className="mt-2 text-xs font-semibold text-primary hover:underline dark:text-primary.dark"
              >
                공시 보기
              </button>
            ) : null}
          </li>
        ))}
      </ul>
    );
  };

  if (isError) {
    return (
      <AppShell>
        <ErrorState
          title="대시보드 데이터를 불러오지 못했습니다"
          description="API 연결 상태를 확인한 뒤 새로고침하거나 관리자에게 문의해주세요."
        />
      </AppShell>
    );
  }

  if (isLoading) {
    return (
      <AppShell>
        <div className="space-y-6">
          <div className="grid gap-4 xl:grid-cols-3">
            <SkeletonBlock className="h-40 xl:col-span-2" />
            <SkeletonBlock className="h-40" />
          </div>
          <div className="grid gap-4 lg:grid-cols-4">
            <SkeletonBlock className="h-32" />
            <SkeletonBlock className="h-32" />
            <SkeletonBlock className="h-32" />
            <SkeletonBlock className="h-32" />
          </div>
          <div className="grid gap-6 xl:grid-cols-3">
            <SkeletonBlock className="h-80 xl:col-span-2" />
            <div className="space-y-4">
              <SkeletonBlock className="h-60" />
              <SkeletonBlock className="h-60" />
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-8">
        <section className="grid gap-4 xl:grid-cols-3">
          <div className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark xl:col-span-2">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">빠른 검색</h2>
              <button
                type="button"
                className="text-xs font-semibold text-primary hover:underline dark:text-primary.dark"
                onClick={() => router.push("/search")}
              >
                전체 보기
              </button>
            </div>
            <GlobalSearchBar
              value={searchInput}
              onChange={setSearchInput}
              onSubmit={handleSearchSubmit}
              onOpenCommand={() => router.push("/search")}
              isLoading={false}
            />
            <div className="mt-4">{renderQuickLinks()}</div>
          </div>
          <div className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">워치리스트 요약</h2>
              <button
                type="button"
                className="text-xs font-semibold text-primary hover:underline dark:text-primary.dark"
                onClick={() => router.push("/watchlist")}
              >
                관리
              </button>
            </div>
            {renderWatchlistSummary()}
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-4">
          {metrics.length > 0 ? (
            metrics.map((item) => <KpiCard key={item.title} {...item} />)
          ) : (
            <EmptyState
              title="표시할 KPI가 없습니다"
              description="데이터 소스가 연결되면 관심 지표가 자동으로 채워집니다."
              className="lg:col-span-4"
            />
          )}
        </section>

        <section className="grid gap-6 xl:grid-cols-3">
          <div className="space-y-6 xl:col-span-2">
            <div className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">섹터 히트맵</h2>
                <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">7일 신호</span>
              </div>
              <SectorHotspotScatter points={sectorPoints} isLoading={isSectorLoading} />
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {dashboardSparkPoints.map((point) => (
                  <SectorSparkCard key={`dashboard-spark-${point.sector.id}`} point={point} />
                ))}
                {!isSectorLoading && dashboardSparkPoints.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-border-light p-4 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
                    아직 집계된 섹터 신호가 없습니다. 데이터 동기화를 확인해주세요.
                  </div>
                ) : null}
              </div>
            </div>
            <div className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">오늘의 이벤트</h2>
                <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">실시간 업데이트</span>
              </div>
              {renderEventList()}
            </div>
            <div className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">공시 추세</h2>
              </div>
              <FilingTrendChart />
            </div>
          </div>
          <div className="space-y-6">
            <div className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">최근 알림</h2>
                <button
                  type="button"
                  className="text-xs font-semibold text-primary hover:underline dark:text-primary.dark"
                  onClick={() => router.push("/watchlist")}
                >
                  Alert Center
                </button>
              </div>
              {alerts.length > 0 ? (
                <AlertFeed alerts={alerts} onSelect={handleAlertSelect} />
              ) : (
                <EmptyState
                  title="표시할 알림이 없습니다"
                  description="관심 기업을 추가하거나 경보 조건을 설정하면 이 영역에 표시됩니다."
                  className="border-none p-0"
                />
              )}
            </div>
            <div className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">뉴스 하이라이트</h2>
                <button
                  type="button"
                  className="text-xs font-semibold text-primary hover:underline dark:text-primary.dark"
                  onClick={() => router.push("/search?tab=news")}
                >
                  더보기
                </button>
              </div>
              {newsItems.length > 0 ? (
                <NewsList items={newsItems} />
              ) : (
                <EmptyState
                  title="최근 뉴스가 없습니다"
                  description="데이터 동기화가 완료되면 최신 뉴스 신호가 자동으로 채워집니다."
                  className="border-none p-0"
                />
              )}
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
