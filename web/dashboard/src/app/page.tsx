"use client";

import { useEffect, useMemo, useState } from "react";
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
import { SearchResults } from "@/components/search/SearchResults";
import {
  useSearchResults,
  type SearchResult,
  type SearchResultType,
  type SearchTotals,
} from "@/hooks/useSearchResults";

const SEARCH_LIMIT = 6;

const createInitialOffsets = (): Record<SearchResultType, number> => ({
  filing: 0,
  news: 0,
  table: 0,
  chart: 0,
});

const createEmptyResults = (): Record<SearchResultType, SearchResult[]> => ({
  filing: [],
  news: [],
  table: [],
  chart: [],
});

export default function DashboardPage() {
  const router = useRouter();
  const { data, isLoading, isError } = useDashboardOverview();

  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeType, setActiveType] = useState<SearchResultType>("filing");
  const [offsetByType, setOffsetByType] = useState<Record<SearchResultType, number>>(createInitialOffsets);
  const [resultsByType, setResultsByType] = useState<Record<SearchResultType, SearchResult[]>>(createEmptyResults);
  const [totalsState, setTotalsState] = useState<SearchTotals | null>(null);

  const activeOffset = offsetByType[activeType];
  const {
    data: searchData,
    isFetching: isSearchFetching,
    isError: isSearchError,
    refetch: refetchSearch,
  } = useSearchResults(searchQuery, activeType, SEARCH_LIMIT, activeOffset);

  const searchTotals = totalsState ?? searchData?.totals ?? null;
  const searchResults = resultsByType[activeType];

  useEffect(() => {
    if (!searchQuery.trim() || !searchData) {
      return;
    }

    setTotalsState(searchData.totals);
    setResultsByType((previous) => {
      const baseline = activeOffset === 0 ? [] : previous[activeType] ?? [];
      const merged = activeOffset === 0 ? searchData.results : [...baseline, ...searchData.results];
      const deduped: SearchResult[] = [];
      const seen = new Set<string>();
      for (const item of merged) {
        if (seen.has(item.id)) {
          continue;
        }
        seen.add(item.id);
        deduped.push(item);
      }
      return { ...previous, [activeType]: deduped };
    });
  }, [searchData, searchQuery, activeType, activeOffset]);

  useEffect(() => {
    if (!searchQuery.trim()) {
      setResultsByType(createEmptyResults());
      setTotalsState(null);
      setOffsetByType(createInitialOffsets());
      setActiveType("filing");
    }
  }, [searchQuery]);

  useEffect(() => {
    if (!searchInput.trim() && searchQuery) {
      setSearchQuery("");
    }
  }, [searchInput, searchQuery]);

  const handleSearchSubmit = () => {
    const trimmed = searchInput.trim();
    if (!trimmed) {
      setSearchQuery("");
      return;
    }

    const normalized = trimmed;
    const isNewQuery = normalized !== searchQuery;

    setSearchQuery(normalized);
    if (isNewQuery) {
      setActiveType("filing");
      setOffsetByType(createInitialOffsets());
      setResultsByType(createEmptyResults());
      setTotalsState(null);
    } else {
      void refetchSearch();
    }
  };

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

  const handleAlertSelect = (alert: (typeof alerts)[number]) => {
    const target = alert?.targetUrl?.trim();
    if (!alert || !target) {
      return;
    }
    if (/^https?:\/\//i.test(target)) {
      window.open(target, "_blank", "noopener,noreferrer");
      return;
    }
    router.push(target);
  };

  const handleSearchTypeChange = (type: SearchResultType) => {
    setActiveType(type);
  };

  const handleLoadMore = () => {
    const totalForActive = searchTotals?.[activeType] ?? 0;
    if (totalForActive <= searchResults.length) {
      return;
    }
    setOffsetByType((previous) => ({
      ...previous,
      [activeType]: previous[activeType] + SEARCH_LIMIT,
    }));
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

  const totalForActive = searchTotals?.[activeType] ?? 0;
  const canLoadMore = totalForActive > searchResults.length;

  return (
    <AppShell>
      <section className="space-y-6">
        <GlobalSearchBar
          value={searchInput}
          onChange={setSearchInput}
          onSubmit={handleSearchSubmit}
          onOpenCommand={() => undefined}
          isLoading={isSearchFetching}
        />
        {searchQuery.trim() ? (
          isSearchError ? (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200">
              검색 API 응답이 지연되고 있습니다. 잠시 후 다시 시도해주세요.
            </div>
          ) : (
            <SearchResults
              results={searchResults}
              totals={searchTotals}
              activeType={activeType}
              isLoading={isSearchFetching}
              onChangeType={handleSearchTypeChange}
              onLoadMore={handleLoadMore}
              canLoadMore={canLoadMore}
            />
          )
        ) : (
          <div className="rounded-2xl border border-dashed border-border-light p-6 text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
            상단 검색창에서 키워드를 입력하면 공시·뉴스·데이터 결과가 여기에 표시됩니다.
          </div>
        )}
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
                아직 집계된 섹터 신호가 없습니다. 데이터 동기화를 확인해주세요.
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
                title="표시할 알림이 없습니다"
                description="관심 기업을 추가하거나 경보 조건을 설정하면 이 영역에 표시됩니다."
              />
            )}
          </div>
          {newsItems.length > 0 ? (
            <NewsList items={newsItems} />
          ) : (
            <EmptyState
              title="최근 뉴스가 없습니다"
              description="데이터 동기화가 완료되면 최신 뉴스 신호가 자동으로 채워집니다."
            />
          )}
        </div>
      </section>
    </AppShell>
  );
}
