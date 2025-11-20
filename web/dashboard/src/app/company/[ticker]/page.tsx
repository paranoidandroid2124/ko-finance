"use client";

import { useEffect, useMemo } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { KeyMetricsGrid } from "@/components/company/KeyMetricsGrid";
import { MajorEventsList } from "@/components/company/MajorEventsList";
import { NewsSignalCards } from "@/components/company/NewsSignalCards";
import { FinancialStatementsBoard } from "@/components/company/FinancialStatementsBoard";
import { EvidenceBundleCard, FiscalAlignmentCard, RestatementRadarCard } from "@/components/company/InsightCards";
import { RecentFilingsPanel } from "@/components/company/RecentFilingsPanel";
import { CompanySummaryCard } from "@/components/company/CompanySummaryCard";
import { PlanLock } from "@/components/ui/PlanLock";
import { useCompanySnapshot, type CompanyFilingSummary, type EventItem } from "@/hooks/useCompanySnapshot";
import { useCompanyTimeline } from "@/hooks/useCompanyTimeline";
import { normalizeCompanySearchResult, type CompanySearchResult } from "@/hooks/useCompanySearch";

const RECENT_COMPANIES_KEY = "kofilot_recent_companies";

type TimelineItem = {
  id: string;
  title: string;
  type: "event" | "filing";
  timestamp?: string | null;
  summary?: string | null;
  url?: string | null;
};

type CompanyHeaderProps = {
  name: string;
  ticker?: string | null;
  corpCode?: string | null;
  sectorName?: string | null;
};

function CompanyHeader({ name, ticker, corpCode, sectorName }: CompanyHeaderProps) {
  return (
    <section className="rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark">{name}</h1>
          <div className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            {ticker ? <span>티커 {ticker}</span> : null}
            {ticker && corpCode ? <span className="mx-1 text-border-light dark:text-border-dark">•</span> : null}
            {corpCode ? <span>법인코드 {corpCode}</span> : null}
          </div>
        </div>
        {sectorName ? (
          <span className="rounded-full border border-border-light px-3 py-1 text-xs font-semibold text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
            {sectorName}
          </span>
        ) : null}
      </div>
    </section>
  );
}

type CompanySnapshotPageProps = {
  params: {
    ticker: string;
  };
};

export default function CompanySnapshotPage({ params }: CompanySnapshotPageProps) {
  const identifier = decodeURIComponent(params.ticker ?? "").toUpperCase();
  const { data, isLoading, isError } = useCompanySnapshot(identifier);
  const { data: timelineData, isLoading: isTimelineLoading } = useCompanyTimeline(identifier, 180);
  const hasData = useMemo(() => {
    if (!data) return false;
    const statementCount = data.financialStatements?.length ?? 0;
    return Boolean(
      statementCount ||
        data.keyMetrics.length ||
        data.majorEvents.length ||
        data.newsSignals.length ||
        data.recentFilings.length,
    );
  }, [data]);

const timelineItems = useMemo<TimelineItem[]>(() => {
  if (!timelineData?.points) {
    return [];
  }
  return timelineData.points
    .filter((point) => point.date)
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
    .map((point, index) => ({
      id: `${point.date}-${index}`,
      type: point.filingCount && point.filingCount > 0 ? "filing" : "event",
      title: point.headline ?? (point.filingCount && point.filingCount > 0 ? "공시 이벤트" : "뉴스 이벤트"),
      timestamp: point.date,
      summary: point.newsCount ? `뉴스 ${point.newsCount}건 · 감성 ${point.sentiment?.toFixed(2) ?? "N/A"}` : undefined,
      url: point.url ?? undefined,
    }));
}, [timelineData]);


  useEffect(() => {
    if (!data || typeof window === "undefined") {
      return;
    }
    const entry: CompanySearchResult = {
      corpCode: data.corpCode ?? null,
      ticker: data.ticker ?? null,
      corpName: data.corpName ?? data.ticker ?? data.corpCode ?? null,
      latestReportName: data.latestFiling?.reportName ?? null,
      latestFiledAt: data.latestFiling?.filedAt ?? null,
    };

    try {
      const stored = window.localStorage.getItem(RECENT_COMPANIES_KEY);
      const parsedRaw: unknown = stored ? JSON.parse(stored) : [];
      const parsed: CompanySearchResult[] = Array.isArray(parsedRaw)
        ? parsedRaw.map((item) => normalizeCompanySearchResult(item))
        : [];
      const filtered = parsed.filter((item) => {
        if (!item) return false;
        const candidateTicker = item.ticker ?? null;
        const candidateCorpCode = item.corpCode ?? null;
        if (entry.ticker && candidateTicker && candidateTicker === entry.ticker) return false;
        if (!entry.ticker && entry.corpCode && candidateCorpCode && candidateCorpCode === entry.corpCode) return false;
        return true;
      });
      const next = [entry, ...filtered].slice(0, 6);
      window.localStorage.setItem(RECENT_COMPANIES_KEY, JSON.stringify(next));
    } catch {
      // ignore storage errors
    }
  }, [data]);

  if (isLoading) {
    return (
      <AppShell>
        <div className="space-y-6">
          <SkeletonBlock lines={6} />
          <SkeletonBlock lines={4} />
          <SkeletonBlock lines={6} />
        </div>
      </AppShell>
    );
  }

  if (isError || !data) {
    return (
      <AppShell>
        <ErrorState
          title="회사 정보를 불러오지 못했습니다"
          description="DART 원문 조회 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        />
      </AppShell>
    );
  }

  if (!hasData) {
    return (
      <AppShell>
        <div className="space-y-6">
          <CompanyHeader name={data.corpName ?? identifier} ticker={data.ticker} corpCode={data.corpCode} />
          <RecentFilingsPanel filings={data.recentFilings} companyName={data.corpName ?? identifier} />
          <EmptyState
            title="표시할 데이터가 없습니다"
            description="주요 지표, 이벤트, 뉴스 신호를 찾을 수 없습니다. 기간이나 회사를 다시 선택해 주세요."
          />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-8">
        <CompanyHeader name={data.corpName ?? identifier} ticker={data.ticker} corpCode={data.corpCode} />

        <section className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,0.65fr)]">
            <CompanySummaryCard
              name={data.corpName ?? identifier}
              ticker={data.ticker}
              headline={data.latestFiling}
              summary={data.summary}
            />
            <div className="space-y-6">
              <RecentEventsSummaryCard events={data.majorEvents} />
              <RecentFilingsPeek filings={data.recentFilings} />
            </div>
          </div>
          {data.keyMetrics.length ? (
            <KeyMetricsGrid metrics={data.keyMetrics} />
          ) : (
            <EmptyState
              title="표시할 핵심 지표가 없습니다"
              description="재무 지표를 수집하지 못했습니다. 재무공시 여부를 다시 확인해 주세요."
              className="border-dashed"
            />
          )}
        </section>

        <section className="grid gap-6 xl:grid-cols-3">
          <PlanLock requiredTier="pro" title="정정 영향 인사이트" description="정정 공시가 주요 지표에 미친 영향을 한눈에 살펴보세요.">
            <RestatementRadarCard highlights={data.restatementHighlights} />
          </PlanLock>
          <PlanLock
            requiredTier="enterprise"
            title="Evidence Bundle"
            description="모든 수치에 출처와 원문 링크를 연결해 감사 패키지를 빠르게 구성하세요."
          >
            <EvidenceBundleCard links={data.evidenceLinks} />
          </PlanLock>
          <PlanLock requiredTier="pro" title="Fiscal Alignment" description="회계연도 전환·분기 길이 불일치를 자동 보정한 신뢰 지표입니다.">
            <FiscalAlignmentCard insight={data.fiscalAlignment} />
          </PlanLock>
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,0.55fr)_minmax(0,0.45fr)]">
          <MajorEventsList events={data.majorEvents} />
          <div className="space-y-6">
            <NewsSignalCards signals={data.newsSignals} companyName={data.corpName ?? null} />
            <TimelineCard items={timelineItems} isLoading={isTimelineLoading} />
          </div>
        </section>

        <section className="space-y-6">
          <RecentFilingsPanel filings={data.recentFilings} companyName={data.corpName ?? identifier} />
          {data.financialStatements.length ? (
            <FinancialStatementsBoard
              statements={data.financialStatements}
              corpName={data.corpName ?? identifier}
              identifier={data.ticker ?? data.corpCode ?? identifier}
            />
          ) : (
            <EmptyState
              title="표시할 재무제표가 없습니다"
              description="해당 회사의 최신 재무 데이터를 불러오지 못했습니다."
            />
          )}
        </section>
      </div>
    </AppShell>
  );
}

const formatDateLabel = (value?: string | null) => {
  if (!value) {
    return "날짜 정보 없음";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString("ko-KR");
};

type TimelineCardProps = {
  items: TimelineItem[];
  isLoading: boolean;
};

function TimelineCard({ items, isLoading }: TimelineCardProps) {
  return (
    <section className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">타임라인</h2>
      {isLoading ? (
        <SkeletonBlock className="mt-4 h-40" />
      ) : items.length === 0 ? (
        <EmptyState
          title="타임라인 이벤트가 없습니다"
          description="알림이 수집되면 타임라인에 표시됩니다."
          className="border-none"
        />
      ) : (
        <ul className="mt-4 space-y-3 text-sm">
          {items.map((item) => (
            <li key={`${item.type}-${item.id}`} className="rounded-xl border border-border-light px-4 py-3 dark:border-border-dark">
              <div className="flex items-center justify-between gap-3">
                <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{item.title}</p>
                <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  {item.timestamp ? new Date(item.timestamp).toLocaleString() : "시간 정보 없음"}
                </span>
              </div>
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{item.type.toUpperCase()}</p>
              {item.summary ? (
                <p className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">{item.summary}</p>
              ) : null}
              {item.url ? (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 inline-flex text-xs font-semibold text-primary hover:underline dark:text-primary.dark"
                >
                  원문 보기
                </a>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

type RecentEventsSummaryCardProps = {
  events: EventItem[];
};

function RecentEventsSummaryCard({ events }: RecentEventsSummaryCardProps) {
  if (!events.length) {
    return (
      <section className="rounded-xl border border-border-light bg-background-cardLight p-5 shadow-sm dark:border-border-dark dark:bg-background-cardDark">
        <h3 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">최근 감지 이벤트</h3>
        <p className="mt-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          최근 30일 동안 감지된 이벤트가 없습니다. Events & Alerts 탭에서 모니터링 규칙을 확인해보세요.
        </p>
      </section>
    );
  }

  const primary = events[0];
  const secondary = events.slice(1, 3);

  return (
    <section className="rounded-xl border border-border-light bg-background-cardLight p-5 shadow-sm dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">최근 감지 이벤트</h3>
        <span className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">{events.length}건 추적</span>
      </div>
      <div className="mt-3 rounded-lg border border-border-light/70 bg-background-light/40 px-4 py-3 dark:border-border-dark/70 dark:bg-background-dark/40">
        <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
          {primary.eventName ?? primary.eventType}
        </p>
        <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          {formatDateLabel(primary.eventDate)} · {primary.eventType}
        </p>
      </div>
      {secondary.length ? (
        <ul className="mt-3 space-y-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          {secondary.map((item) => (
            <li
              key={item.id}
              className="flex items-center justify-between rounded-lg border border-border-light/70 px-3 py-1.5 dark:border-border-dark/70"
            >
              <span className="truncate">{item.eventName ?? item.eventType}</span>
              <span>{formatDateLabel(item.eventDate)}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <p className="mt-3 text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
        상세한 타임라인은 Events & Alerts 탭에서 확인하세요.
      </p>
    </section>
  );
}

type RecentFilingsPeekProps = {
  filings: CompanyFilingSummary[];
};

function RecentFilingsPeek({ filings }: RecentFilingsPeekProps) {
  const items = filings.slice(0, 3);

  const openViewer = (url?: string | null) => {
    if (!url) {
      return;
    }
    window.open(url, "_blank", "noopener,noreferrer");
  };

  return (
    <section className="rounded-xl border border-border-light bg-background-cardLight p-5 shadow-sm dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">최신 공시</h3>
        <span className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
          {filings.length ? `${filings.length}건` : "기록 없음"}
        </span>
      </div>
      {items.length ? (
        <ul className="mt-3 space-y-2">
          {items.map((filing) => (
            <li
              key={filing.id ?? filing.receiptNo ?? filing.title ?? Math.random().toString(36)}
              className="rounded-lg border border-border-light/70 px-3 py-2 dark:border-border-dark/70"
            >
              <button
                type="button"
                onClick={() => openViewer(filing.viewerUrl)}
                className="w-full text-left text-sm font-semibold text-primary underline-offset-2 hover:underline dark:text-primary.dark"
              >
                {filing.reportName ?? filing.title ?? "공시 상세"}
              </button>
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                {formatDateLabel(filing.filedAt)} · {filing.category ?? "분류 미상"}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-xs text-text-secondaryLight dark:text-text-secondaryDark">최근에 감지된 공시가 없습니다.</p>
      )}
      <p className="mt-3 text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
        Filings 탭에서 전체 공시 이력을 확인할 수 있습니다.
      </p>
    </section>
  );
}
