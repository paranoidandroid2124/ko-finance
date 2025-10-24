"use client";

import { useMemo, useState } from "react";
import { shallow } from "zustand/shallow";
import { AppShell } from "@/components/layout/AppShell";
import { NewsSentimentHeatmap } from "@/components/charts/NewsSentimentHeatmap";
import { NewsList } from "@/components/ui/NewsList";
import { TopicRankingCard } from "@/components/news/TopicRankingCard";
import { NewsFilterPanel } from "@/components/news/NewsFilterPanel";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { useNewsInsights } from "@/hooks/useNewsInsights";
import { useSectorSignals, type SectorSignalPoint } from "@/hooks/useSectorSignals";
import { selectNewsFilterOptions, useNewsFilterStore } from "@/store/newsFilterStore";
import { SectorHotspotScatter } from "@/components/sectors/SectorHotspotScatter";
import { SectorSparkCard } from "@/components/sectors/SectorSparkCard";
import { SectorDetailDrawer } from "@/components/sectors/SectorDetailDrawer";

export default function NewsInsightsPage() {
  const filters = useNewsFilterStore(selectNewsFilterOptions, shallow);
  const { data, isLoading, isError } = useNewsInsights(filters);
  const news = data?.news ?? [];
  const topics = data?.topics ?? [];
  const { data: signalsData, isLoading: isSignalsLoading } = useSectorSignals();
  const [drawerPoint, setDrawerPoint] = useState<SectorSignalPoint | null>(null);

  const rawSignalPoints = signalsData?.points;
  const signalPoints = useMemo(() => rawSignalPoints ?? [], [rawSignalPoints]);
  const sparkPoints = useMemo(() => {
    const sorted = [...signalPoints].sort((a, b) => (b.sentimentZ ?? 0) - (a.sentimentZ ?? 0));
    const unique = new Map<number, SectorSignalPoint>();
    sorted.forEach((point) => {
      if (!unique.has(point.sector.id)) {
        unique.set(point.sector.id, point);
      }
    });
    return Array.from(unique.values()).slice(0, 6);
  }, [signalPoints]);

  const handleSelectSector = (point: SectorSignalPoint) => {
    setDrawerPoint(point);
  };

  const handleCloseDrawer = () => {
    setDrawerPoint(null);
  };

  if (isError) {
    return (
      <AppShell>
        <ErrorState
          title="뉴스 데이터를 불러오지 못했습니다"
          description="RSS 소스 연결 상태를 확인한 뒤 다시 시도해주세요."
        />
      </AppShell>
    );
  }

  if (isLoading) {
    return (
      <AppShell>
        <div className="grid gap-6 xl:grid-cols-[260px_minmax(0,1fr)]">
          <SkeletonBlock className="h-full" lines={6} />
          <div className="space-y-6">
            <div className="grid gap-6 lg:grid-cols-2">
              <SkeletonBlock lines={8} />
              <SkeletonBlock lines={8} />
            </div>
            <SkeletonBlock lines={10} />
          </div>
        </div>
      </AppShell>
    );
  }

  if (!news.length) {
    return (
      <AppShell>
        <div className="grid gap-6 xl:grid-cols-[260px_minmax(0,1fr)]">
          <NewsFilterPanel />
          <EmptyState
            title="표시할 뉴스가 없습니다"
            description="필터 조건을 완화하거나 데이터 동기화를 다시 시도해주세요."
          />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="grid gap-6 xl:grid-cols-[260px_minmax(0,1fr)]">
        <NewsFilterPanel />
        <div className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
            <SectorHotspotScatter points={signalPoints} isLoading={isSignalsLoading} onSelect={handleSelectSector} />
            <TopicRankingCard topics={topics} />
          </div>
          <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
            {sparkPoints.map((point) => (
              <SectorSparkCard key={point.sector.id} point={point} onSelect={handleSelectSector} />
            ))}
            {!isSignalsLoading && sparkPoints.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border-light p-4 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
                표시할 섹터 시계열이 없습니다. 집계가 완료되면 자동으로 나타납니다.
              </div>
            ) : null}
          </div>
          <NewsList items={news} />
          <details className="group rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition dark:border-border-dark dark:bg-background-cardDark">
            <summary className="cursor-pointer text-sm font-semibold text-text-primaryLight outline-none marker:text-primary dark:text-text-primaryDark">
              히트맵(고급 보기)
            </summary>
            <div className="mt-4">
              <NewsSentimentHeatmap />
            </div>
          </details>
        </div>
      </div>
      <SectorDetailDrawer open={Boolean(drawerPoint)} point={drawerPoint} onClose={handleCloseDrawer} />
    </AppShell>
  );
}
