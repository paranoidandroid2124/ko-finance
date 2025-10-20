"use client";

import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { KpiCard } from "@/components/ui/KpiCard";
import { AlertFeed } from "@/components/ui/AlertFeed";
import { NewsList } from "@/components/ui/NewsList";
import { FilingTrendChart } from "@/components/charts/FilingTrendChart";
import { NewsSentimentHeatmap } from "@/components/charts/NewsSentimentHeatmap";

const KPI_DATA = [
  { title: "공시 처리", value: "86건", delta: "+12%", trend: "up", description: "24시간 내 분석 완료" },
  { title: "뉴스 감성지수", value: "62.4", delta: "-4.7", trend: "down", description: "15분 윈도우 평균" },
  { title: "RAG 세션", value: "128", delta: "+8.5%", trend: "up", description: "Guardrail 통과율 97%" },
  { title: "알림 전송", value: "412", delta: "0%", trend: "flat", description: "텔레그램/이메일 합산" }
] as const;

const ALERTS = [
  {
    id: "1",
    title: "부정 뉴스 증가",
    body: "반도체 섹터 감성 -12%p (15분)",
    timestamp: "5분 전",
    tone: "negative" as const
  },
  {
    id: "2",
    title: "신규 공시",
    body: "삼성전자 분기보고서 업로드",
    timestamp: "12분 전",
    tone: "neutral" as const
  },
  {
    id: "3",
    title: "RAG self-check",
    body: "guardrail 경고 1건",
    timestamp: "18분 전",
    tone: "warning" as const
  }
];

const NEWS_ITEMS = [
  {
    id: "news-1",
    title: "AI 반도체 수요 둔화 우려",
    sentiment: "negative" as const,
    source: "연합뉴스",
    publishedAt: "10분 전"
  },
  {
    id: "news-2",
    title: "친환경 에너지 투자 확대",
    sentiment: "positive" as const,
    source: "매일경제",
    publishedAt: "25분 전"
  },
  {
    id: "news-3",
    title: "원자재 가격 변동성 확대",
    sentiment: "neutral" as const,
    source: "조선비즈",
    publishedAt: "40분 전"
  }
];

export default function DashboardPage() {
  const router = useRouter();

  const handleAlertSelect = (alert: (typeof ALERTS)[number]) => {
    if (alert.title.includes("뉴스")) {
      router.push("/news");
    } else if (alert.title.includes("공시")) {
      router.push("/filings");
    } else {
      router.push("/chat");
    }
  };

  return (
    <AppShell>
      <section className="grid gap-4 lg:grid-cols-4">
        {KPI_DATA.map((item) => (
          <KpiCard key={item.title} {...item} />
        ))}
      </section>

      <section className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <FilingTrendChart />
          <NewsSentimentHeatmap />
        </div>
        <div className="space-y-6">
          <AlertFeed alerts={ALERTS} onSelect={handleAlertSelect} />
          <NewsList items={NEWS_ITEMS} />
        </div>
      </section>
    </AppShell>
  );
}