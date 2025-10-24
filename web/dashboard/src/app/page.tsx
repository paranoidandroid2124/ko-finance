"use client";

import { useMemo } from "react";
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

export default function DashboardPage() {
  const router = useRouter();
  const { data, isLoading, isError } = useDashboardOverview();

  const metrics = data?.metrics ?? [];
  const alerts = data?.alerts ?? [];
  const newsItems = data?.news ?? [];
  const { data: sectorSignals, isLoading: isSectorLoading } = useSectorSignals();
  const rawSectorPoints = sectorSignals?.points;
  const sectorPoints = useMemo(() => rawSectorPoints ?? [], [rawSectorPoints]);
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

  const handleAlertSelect = (alert: typeof alerts[number]) => {
    const target = alert.targetUrl?.trim();
    if (target) {
      if (/^https?:\/\//i.test(target)) {
        window.open(target, "_blank", "noopener,noreferrer");
      } else {
        router.push(target);
      }
      return;
    }
    if (alert.title.includes("뉴스")) {
      router.push("/news");
    } else if (alert.title.includes("공시")) {
      router.push("/filings");
    } else {
      router.push("/chat");
    }
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
          <div className="grid gap-4 lg:grid-cols-4">
            <SkeletonBlock className="h-32" />
            <SkeletonBlock className="h-32" />
            <SkeletonBlock className="h-32" />
            <SkeletonBlock className="h-32" />
          </div>
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="space-y-6 lg:col-span-2">
              <SkeletonBlock lines={10} />
              <SkeletonBlock lines={10} />
            </div>
            <div className="space-y-6">
              <SkeletonBlock lines={8} />
              <SkeletonBlock lines={8} />
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <section className="grid gap-4 lg:grid-cols-4">
        {metrics.length > 0 ? (
          metrics.map((item) => <KpiCard key={item.title} {...item} />)
        ) : (
          <EmptyState
            title="표시할 KPI가 없습니다"
            description="실제 지표 연동을 완료하면 이 영역에서 핵심 지표를 확인할 수 있습니다."
            className="lg:col-span-4"
          />
        )}
      </section>

      <section className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <FilingTrendChart />
          <SectorHotspotScatter points={sectorPoints} isLoading={isSectorLoading} />
          <div className="grid gap-3 sm:grid-cols-2">
            {dashboardSparkPoints.map((point) => (
              <SectorSparkCard key={`dashboard-spark-${point.sector.id}`} point={point} />
            ))}
            {!isSectorLoading && dashboardSparkPoints.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border-light p-4 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
                섹터 데이터가 아직 집계되지 않았습니다.
              </div>
            ) : null}
          </div>
        </div>
        <div className="space-y-6">
          <div className="xl:hidden">
            {alerts.length > 0 ? (
              <AlertFeed alerts={alerts} onSelect={handleAlertSelect} />
            ) : (
              <EmptyState
                title="실시간 알림이 없습니다"
                description="파이프라인이 재개되면 guardrail 경고와 공시 알림이 여기에 표시됩니다."
              />
            )}
          </div>
          {newsItems.length > 0 ? (
            <NewsList items={newsItems} />
          ) : (
            <EmptyState title="표시할 뉴스가 없습니다" description="데이터 동기화를 기다리는 중입니다." />
          )}
        </div>
      </section>
    </AppShell>
  );
}
