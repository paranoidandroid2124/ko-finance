"use client";

import { useEffect, useMemo } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { CompanySummaryCard } from "@/components/company/CompanySummaryCard";
import { KeyMetricsGrid } from "@/components/company/KeyMetricsGrid";
import { MajorEventsList } from "@/components/company/MajorEventsList";
import { NewsSignalCards } from "@/components/company/NewsSignalCards";
import { useCompanySnapshot } from "@/hooks/useCompanySnapshot";
import type { CompanySearchResult } from "@/hooks/useCompanySearch";

const RECENT_COMPANIES_KEY = "kofilot_recent_companies";

type CompanySnapshotPageProps = {
  params: {
    ticker: string;
  };
};

export default function CompanySnapshotPage({ params }: CompanySnapshotPageProps) {
  const identifier = decodeURIComponent(params.ticker ?? "").toUpperCase();
  const { data, isLoading, isError } = useCompanySnapshot(identifier);

  const hasData = useMemo(() => Boolean(data && data.keyMetrics.length + data.majorEvents.length + data.newsSignals.length > 0), [data]);

  useEffect(() => {
    if (!data || typeof window === "undefined") {
      return;
    }
    const entry: CompanySearchResult = {
      corpCode: data.corpCode ?? null,
      ticker: data.ticker ?? null,
      corpName: data.corpName ?? data.ticker ?? data.corpCode ?? null,
      latestReportName: data.latestFiling?.reportName ?? null,
      latestFiledAt: data.latestFiling?.filedAt ?? null
    };
    try {
      const stored = window.localStorage.getItem(RECENT_COMPANIES_KEY);
      const parsed: CompanySearchResult[] = stored ? JSON.parse(stored) : [];
      const filtered = Array.isArray(parsed)
        ? parsed.filter((item) => {
            if (!item) return false;
            if (entry.ticker && item.ticker && item.ticker === entry.ticker) return false;
            if (!entry.ticker && item.corpCode && entry.corpCode && item.corpCode === entry.corpCode) return false;
            return true;
          })
        : [];
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
          description="DART 또는 뉴스 시그널 데이터를 확인하는 중 문제가 발생했습니다. 잠시 후 다시 시도해주세요."
        />
      </AppShell>
    );
  }

  if (!hasData) {
    return (
      <AppShell>
        <div className="space-y-6">
          <CompanySummaryCard name={data.corpName ?? identifier} ticker={data.ticker} headline={data.latestFiling} summary={data.summary} />
          <EmptyState
            title="아직 표시할 시그널이 없습니다"
            description="최근 공시, 뉴스, 재무 요약이 준비되면 자동으로 스냅샷이 채워집니다."
          />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <CompanySummaryCard name={data.corpName ?? identifier} ticker={data.ticker} headline={data.latestFiling} summary={data.summary} />
        <KeyMetricsGrid metrics={data.keyMetrics} />
        <div className="grid gap-6 xl:grid-cols-[minmax(0,0.6fr)_minmax(0,1fr)]">
          <MajorEventsList events={data.majorEvents} />
        <NewsSignalCards signals={data.newsSignals} companyName={data.corpName ?? null} />
        </div>
      </div>
    </AppShell>
  );
}
