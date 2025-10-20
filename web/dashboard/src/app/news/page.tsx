"use client";

import { AppShell } from "@/components/layout/AppShell";
import { NewsSentimentHeatmap } from "@/components/charts/NewsSentimentHeatmap";
import { NewsList } from "@/components/ui/NewsList";
import { TopicRankingCard } from "@/components/news/TopicRankingCard";
import { NewsFilterPanel } from "@/components/news/NewsFilterPanel";

const MOCK_NEWS = [
  {
    id: "n1",
    title: "AI 반도체 수요 둔화 우려",
    sentiment: "negative" as const,
    source: "연합뉴스",
    publishedAt: "10분 전"
  },
  {
    id: "n2",
    title: "친환경 에너지 투자 확대",
    sentiment: "positive" as const,
    source: "매일경제",
    publishedAt: "25분 전"
  },
  {
    id: "n3",
    title: "원자재 가격 변동성 확대",
    sentiment: "neutral" as const,
    source: "조선비즈",
    publishedAt: "40분 전"
  },
  {
    id: "n4",
    title: "바이오 규제 완화 기대감",
    sentiment: "positive" as const,
    source: "헤럴드경제",
    publishedAt: "1시간 전"
  }
];

const TOPICS = [
  { name: "AI 반도체", change: "-24.7%", sentiment: "negative" as const },
  { name: "친환경 에너지", change: "+18.5%", sentiment: "positive" as const },
  { name: "콘텐츠 플랫폼", change: "-12.2%", sentiment: "negative" as const },
  { name: "바이오 규제", change: "+9.4%", sentiment: "positive" as const }
];

export default function NewsInsightsPage() {
  return (
    <AppShell>
      <div className="grid gap-6 xl:grid-cols-[260px_minmax(0,1fr)]">
        <NewsFilterPanel />
        <div className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <NewsSentimentHeatmap />
            <TopicRankingCard topics={TOPICS} />
          </div>
          <NewsList items={MOCK_NEWS} />
        </div>
      </div>
    </AppShell>
  );
}

