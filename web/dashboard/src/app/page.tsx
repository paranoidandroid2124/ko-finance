"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { KpiCard } from "@/components/ui/KpiCard";
import { AlertFeed } from "@/components/ui/AlertFeed";
import { NewsList } from "@/components/ui/NewsList";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { FilingTrendChart } from "@/components/charts/FilingTrendChart";
import { useDashboardOverview, type DashboardWatchlistSummary } from "@/hooks/useDashboardOverview";
import { usePlanTrialCta } from "@/hooks/usePlanTrialCta";
import { useOnboardingStore } from "@/store/onboardingStore";
import { useSectorSignals, type SectorSignalPoint } from "@/hooks/useSectorSignals";
import { SectorHotspotScatter } from "@/components/sectors/SectorHotspotScatter";
import { SectorSparkCard } from "@/components/sectors/SectorSparkCard";
import { SectorDetailDrawer } from "@/components/sectors/SectorDetailDrawer";
import { GlobalSearchBar } from "@/components/search/GlobalSearchBar";
import { EventStudyExportButton } from "@/components/event-study/EventStudyExportButton";
import { usePlanStore } from "@/store/planStore";
import { buildEventStudyExportParams } from "@/lib/eventStudyExport";

const EVENT_SEVERITY_CLASS: Record<string, string> = {
  info: "bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-200",
  warning: "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200",
  critical: "bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-200",
  neutral: "bg-slate-100 text-slate-600 dark:bg-slate-700/40 dark:text-slate-200",
};

const HELP_CENTER_URL = "https://docs.kfinance.co/help";

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

const formatNumber = (value: number) => new Intl.NumberFormat("ko-KR").format(value);

export default function DashboardPage() {
  const router = useRouter();
  const { data, isLoading, isError } = useDashboardOverview();
  const [searchInput, setSearchInput] = useState("");
  const reportsEventExportEnabled = usePlanStore((state) => state.featureFlags.reportsEventExport);
  const buildDashboardExportParams = useCallback(
    () =>
      buildEventStudyExportParams({
        windowStart: -5,
        windowEnd: 20,
        scope: "market",
        significance: 0.1,
        search: searchInput,
        limit: 200,
      }),
    [searchInput],
  );

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
  const [sectorDetailPoint, setSectorDetailPoint] = useState<SectorSignalPoint | null>(null);
  const [isSectorDrawerOpen, setIsSectorDrawerOpen] = useState(false);
  const handleSelectSector = useCallback((point: SectorSignalPoint) => {
    setSectorDetailPoint(point);
    setIsSectorDrawerOpen(true);
  }, []);
  const closeSectorDrawer = useCallback(() => setIsSectorDrawerOpen(false), []);

  const uniqueTickerCount = useMemo(() => {
    const set = new Set<string>();
    watchlists.forEach((item) => {
      item.tickers.forEach((ticker) => set.add(ticker));
    });
    return set.size;
  }, [watchlists]);

  const heroStats = [
    { label: "워치리스트 룰", value: formatNumber(watchlists.length), helper: "활성 규칙" },
    { label: "모니터링 종목", value: formatNumber(uniqueTickerCount), helper: "중복 제거 기준" },
    { label: "오늘 감지된 이벤트", value: formatNumber(events.length), helper: "실시간 업데이트" },
    { label: "새 알림", value: formatNumber(alerts.length), helper: "24시간 이내" },
  ];

  const needsOnboarding = useOnboardingStore((state) => state.needsOnboarding);
  const onboardingDismissed = useOnboardingStore((state) => state.dismissed);
  const onboardingContent = useOnboardingStore((state) => state.content);
  const setNeedsOnboarding = useOnboardingStore((state) => state.setNeedsOnboarding);

  const onboardingHighlights = onboardingContent?.hero?.highlights ?? [];
  const showOnboardingCard = needsOnboarding && !onboardingDismissed;

  const { trialAvailable, trialActive, trialDurationDays, trialStarting, startTrialCta } = usePlanTrialCta();

  const handleStartTrial = async () => {
    try {
      await startTrialCta({ source: "dashboard-trial" });
    } catch (error) {
      console.error("failed to start trial", error);
    }
  };

  const openOnboarding = () => {
    setNeedsOnboarding(true);
  };

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
          action={
            <button
              type="button"
              onClick={() => router.push("/watchlist")}
              className="inline-flex items-center justify-center rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white shadow hover:bg-primary/90 dark:bg-primary.dark dark:hover:bg-primary.dark/90"
            >
              워치리스트 만들기
            </button>
          }
          className="border-none p-0"
        />
      );
    }
    const cards = watchlists.slice(0, 4);
    return (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((item) => (
          <WatchlistSummaryCard key={item.ruleId} item={item} onOpen={() => router.push(item.detailUrl ?? "/watchlist")} />
        ))}
        {watchlists.length > cards.length ? (
          <button
            type="button"
            onClick={() => router.push("/watchlist")}
            className="flex flex-col items-start justify-between rounded-2xl border border-dashed border-border-light px-4 py-4 text-left text-sm text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">More</p>
            <p className="mt-1 text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">
              나머지 {watchlists.length - cards.length}개 워치리스트 보기
            </p>
            <p className="text-xs">Watchlist 전체 페이지로 이동합니다.</p>
          </button>
        ) : null}
      </div>
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
        <section className="grid gap-4 lg:grid-cols-[3fr,2fr]">
          <div className="rounded-3xl border border-border-light bg-gradient-to-br from-primary/10 via-emerald-100 to-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-gradient-to-br dark:from-primary.dark/20 dark:via-slate-900 dark:to-background-cardDark">
            <div className="flex flex-col gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-primary dark:text-primary.dark">Watchlist Radar</p>
                <h1 className="mt-2 text-2xl font-semibold text-text-primaryLight dark:text-text-primaryDark">오늘 아침 워치리스트 현황</h1>
                <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                  감시 중인 기업과 새롭게 감지된 이벤트를 한 화면에서 확인하세요.
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {heroStats.map((stat) => (
                  <HeroStatCard key={stat.label} {...stat} />
                ))}
              </div>
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => router.push("/watchlist")}
                  className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-white shadow hover:bg-primary/90 dark:bg-primary.dark dark:hover:bg-primary.dark/90"
                >
                  워치리스트 관리
                </button>
            <button
              type="button"
              onClick={() => router.push("/labs/event-study")}
              className="rounded-full border border-border-light/80 px-4 py-2 text-sm font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
            >
              이벤트 스터디 보기
            </button>
            {reportsEventExportEnabled ? (
              <EventStudyExportButton
                buildParams={buildDashboardExportParams}
                variant="secondary"
                size="sm"
                className="rounded-full"
              >
                PDF 내보내기
              </EventStudyExportButton>
            ) : null}
          </div>
            </div>
          </div>
          <div className="rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">빠른 검색 &amp; 단축 링크</h2>
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
        </section>

        <section className="grid gap-4 md:grid-cols-2">
          <div className="rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-primary dark:text-primary.dark">Onboarding</p>
                <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">3분 튜토리얼</h2>
              </div>
              <span className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
                {showOnboardingCard ? "진행 필요" : "완료됨"}
              </span>
            </div>
            {showOnboardingCard ? (
              <>
                <ul className="space-y-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  {(onboardingHighlights.length ? onboardingHighlights : ["워치리스트 추가", "Slack/Email 알림 연결", "이벤트 스터디 살펴보기"]).map(
                    (item) => (
                      <li key={item} className="flex items-start gap-2">
                        <span className="mt-1 h-1.5 w-1.5 rounded-full bg-primary dark:bg-primary.dark" aria-hidden />
                        <span>{item}</span>
                      </li>
                    ),
                  )}
                </ul>
                <button
                  type="button"
                  onClick={openOnboarding}
                  className="mt-4 inline-flex items-center justify-center rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white shadow hover:bg-primary/90 dark:bg-primary.dark dark:hover:bg-primary.dark/90"
                >
                  튜토리얼 열기
                </button>
              </>
            ) : (
              <>
                <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                  온보딩이 완료되었습니다. 필요하면 언제든 도움말 센터에서 문서를 확인하세요.
                </p>
                <a
                  href={HELP_CENTER_URL}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-4 inline-flex items-center text-sm font-semibold text-primary hover:underline dark:text-primary.dark"
                >
                  Help Center 바로가기
                </a>
              </>
            )}
          </div>
          <div className="rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-primary dark:text-primary.dark">Pro Trial</p>
                <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">증거 번들 · Slack 다이제스트까지</h2>
              </div>
              <span className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">{trialActive ? "이용 중" : "대기 중"}</span>
            </div>
            {trialActive ? (
              <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                Pro 플랜 체험이 진행 중입니다. Slack/Email 다이제스트와 Evidence Bundle export를 마음껏 사용해보세요.
              </p>
            ) : trialAvailable ? (
              <>
                <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                  버튼 한 번으로 {trialDurationDays}일 동안 Pro 기능을 제한 없이 체험할 수 있습니다.
                </p>
                <button
                  type="button"
                  onClick={handleStartTrial}
                  disabled={trialStarting}
                  className="mt-4 inline-flex items-center justify-center rounded-xl bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {trialStarting ? "시작 준비 중..." : "무료 체험 시작"}
                </button>
              </>
            ) : (
              <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                체험이 모두 사용되었습니다. 필요한 경우 플랜·가격 페이지에서 업그레이드를 요청해주세요.
              </p>
            )}
            <a
              href={HELP_CENTER_URL}
              target="_blank"
              rel="noreferrer"
              className="mt-4 inline-flex items-center text-xs font-semibold text-primary hover:underline dark:text-primary.dark"
            >
              Help Center · 결제 FAQ
            </a>
          </div>
        </section>

        <section className="rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">나의 워치리스트 요약</h2>
              <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                룰별 최근 알림, 대표 종목, 사용 채널을 카드로 확인하세요.
              </p>
            </div>
            <button
              type="button"
              className="text-xs font-semibold text-primary hover:underline dark:text-primary.dark"
              onClick={() => router.push("/watchlist")}
            >
              Watchlist 전체 보기
            </button>
          </div>
          <div className="mt-6">{renderWatchlistSummary()}</div>
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
            <div className="rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">섹터 히트맵</h2>
                  <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">7일 기준 감성·이벤트 점수</p>
                </div>
                <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">실시간 업데이트</span>
              </div>
              <SectorHotspotScatter points={sectorPoints} isLoading={isSectorLoading} onSelect={handleSelectSector} />
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {dashboardSparkPoints.map((point) => (
                  <SectorSparkCard key={`dashboard-spark-${point.sector.id}`} point={point} onSelect={handleSelectSector} />
                ))}
                {!isSectorLoading && dashboardSparkPoints.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-border-light p-4 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
                    아직 집계된 섹터 신호가 없습니다. 데이터 동기화를 확인해주세요.
                  </div>
                ) : null}
              </div>
            </div>
            <div className="rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">오늘의 이벤트</h2>
                <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{events.length}건 감지</span>
              </div>
              {renderEventList()}
            </div>
            <div className="rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
              <div className="mb-4.flex items-center justify-between">
                <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">공시 추세</h2>
              </div>
              <FilingTrendChart />
            </div>
          </div>
          <div className="space-y-6">
            <div className="rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
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
            <div className="rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
              <div className="mb-4 flex.items-center justify-between">
                <h2 className="text-base.font-semibold text-text-primaryLight dark:text-text-primaryDark">뉴스 하이라이트</h2>
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
      <SectorDetailDrawer open={isSectorDrawerOpen} point={sectorDetailPoint} onClose={closeSectorDrawer} />
    </AppShell>
  );
}

type HeroStatCardProps = {
  label: string;
  value: string;
  helper?: string;
};

function HeroStatCard({ label, value, helper }: HeroStatCardProps) {
  return (
    <div className="rounded-2xl border border-white/40 bg-white/80 px-4 py-3 text-left shadow-sm dark:border-white/10 dark:bg-white/5">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-primary dark:text-primary.dark">{label}</p>
      <p className="mt-1 text-2xl font-bold text-text-primaryLight dark:text-text-primaryDark">{value}</p>
      {helper ? <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{helper}</p> : null}
    </div>
  );
}

type WatchlistSummaryCardProps = {
  item: DashboardWatchlistSummary;
  onOpen: () => void;
};

function WatchlistSummaryCard({ item, onOpen }: WatchlistSummaryCardProps) {
  const topTickers = item.tickers.slice(0, 4);
  const extraTickers = Math.max(item.tickers.length - topTickers.length, 0);
  const channelsLabel = item.channels.length ? item.channels.join(", ") : "채널 미설정";
  const headline = item.lastHeadline ?? "최근 알림 요약 없음";

  return (
    <div className="flex flex-col rounded-2xl border border-border-light bg-background-base p-4 text-sm shadow-sm dark:border-border-dark dark:bg-background-baseDark">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">{item.name}</p>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{headline}</p>
        </div>
        <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary dark:bg-primary.dark/20 dark:text-primary.dark">
          {formatNumber(item.eventCount)}건
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
        {topTickers.map((ticker) => (
          <span key={`${item.ruleId}-${ticker}`} className="rounded-full bg-background-cardLight px-2 py-0.5 dark:bg-background-cardDark">
            {ticker}
          </span>
        ))}
        {extraTickers > 0 ? <span>+{extraTickers}</span> : null}
      </div>
      <div className="mt-4 flex items-center justify-between text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
        <span>{channelsLabel}</span>
        <span>{formatRelativeTime(item.lastTriggeredAt)}</span>
      </div>
      <button
        type="button"
        onClick={onOpen}
        className="mt-4 inline-flex items-center justify-center rounded-xl border border-border-light px-3 py-2 text-xs font-semibold text-text-primaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-primaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
      >
        상세 보기
      </button>
    </div>
  );
}
