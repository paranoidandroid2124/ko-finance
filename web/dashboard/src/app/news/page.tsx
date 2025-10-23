"use client";

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
import { selectNewsFilterOptions, useNewsFilterStore } from "@/store/newsFilterStore";

export default function NewsInsightsPage() {
  const filters = useNewsFilterStore(selectNewsFilterOptions, shallow);
  const { data, isLoading, isError } = useNewsInsights(filters);
  const news = data?.news ?? [];
  const topics = data?.topics ?? [];

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
          <div className="grid gap-6 lg:grid-cols-2">
            <NewsSentimentHeatmap />
            <TopicRankingCard topics={topics} />
          </div>
          <NewsList items={news} />
        </div>
      </div>
    </AppShell>
  );
}
