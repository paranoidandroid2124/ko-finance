"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { GlobalSearchBar } from "@/components/search/GlobalSearchBar";
import { SearchResults } from "@/components/search/SearchResults";
import { EmptyState } from "@/components/ui/EmptyState";
import { SearchFiltersSidebar } from "./_components/SearchFiltersSidebar";
import { SearchCommandPalette, type SearchCommandItem } from "./_components/SearchCommandPalette";
import { useSearchController } from "./_hooks/useSearchController";

const QUICK_SEARCH_SUGGESTIONS = ["자사주 매입", "유상증자", "감사의견", "재무제표", "신규상장"];

export default function SearchPage() {
  const controller = useSearchController();
  const {
    filters,
    activeFilterChips,
    activeType,
    searchInput,
    setSearchInput,
    searchResults,
    totals,
    isFetching,
    isError,
    hasQuery,
    canLoadMore,
    handleFilterChange,
    handleSearchSubmit,
    handleQuickSearch,
    handleTypeChange,
    handleLoadMore,
  } = controller;
  const router = useRouter();
  const [isCommandOpen, setIsCommandOpen] = useState(false);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setIsCommandOpen((previous) => !previous);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  const trimmedSearch = searchInput.trim();
  const activeTypeLabel =
    activeType === "filing" ? "공시" : activeType === "news" ? "뉴스" : activeType === "table" ? "표" : "차트";

  const commandItems = useMemo<SearchCommandItem[]>(() => {
    const baseCommands: SearchCommandItem[] = [
      {
        id: "goto-dashboard",
        label: "대시보드로 이동",
        description: "워치리스트 · KPI 한눈에 보기",
        shortcut: "G · D",
        onSelect: () => router.push("/"),
      },
      {
        id: "goto-watchlist",
        label: "Watchlist 관리",
        description: "경보 룰 · Digest 설정",
        shortcut: "G · W",
        onSelect: () => router.push("/watchlist"),
      },
      {
        id: "goto-company",
        label: "회사 스냅샷 열기",
        description: "티커 기반 상세 리포트",
        shortcut: "G · C",
        onSelect: () => router.push("/company"),
      },
      {
        id: "goto-news",
        label: "뉴스 허브로 이동",
        description: "섹터 감성 · 이벤트 집중 보기",
        shortcut: "G · N",
        onSelect: () => router.push("/news"),
      },
    ];
    if (trimmedSearch) {
      baseCommands.unshift({
        id: "run-current-search",
        label: `"${trimmedSearch}" 검색 실행`,
        description: `${activeTypeLabel} 탭 기준으로 검색`,
        shortcut: "Enter",
        onSelect: handleSearchSubmit,
      });
    }
    return baseCommands;
  }, [activeTypeLabel, handleSearchSubmit, router, trimmedSearch]);

  const quickSuggestionAction = (
    <div className="flex flex-wrap justify-center gap-2">
      {QUICK_SEARCH_SUGGESTIONS.map((suggestion) => (
        <button
          type="button"
          key={suggestion}
          onClick={() => handleQuickSearch(suggestion)}
          className="rounded-full border border-border-light px-3 py-1 text-xs font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
        >
          {suggestion}
        </button>
      ))}
    </div>
  );

  return (
    <AppShell>
      <div className="flex min-h-[80vh] flex-col gap-6 lg:flex-row">
        <SearchFiltersSidebar filters={filters} onChange={handleFilterChange} />
        <section className="flex-1 space-y-6">
          <div className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <h1 className="text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark">통합 검색</h1>
                {activeFilterChips.length > 0 ? (
                  <div className="flex flex-wrap gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                    {activeFilterChips.map((chip) => (
                      <span key={chip} className="rounded-full bg-background-cardDark/40 px-3 py-1">
                        {chip}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
              <GlobalSearchBar
                value={searchInput}
                onChange={setSearchInput}
                onSubmit={handleSearchSubmit}
                onOpenCommand={() => setIsCommandOpen(true)}
                isLoading={isFetching}
              />
            </div>
          </div>

          {!hasQuery ? (
            <EmptyState
              title="검색어를 입력해주세요"
              description="회사명, 티커, 키워드를 입력하면 공시·뉴스·데이터가 탭으로 정리되어 표시됩니다."
              action={quickSuggestionAction}
              className="rounded-2xl border border-dashed border-border-light p-10 text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark"
            />
          ) : (
            <SearchResults
              results={searchResults}
              totals={totals ?? null}
              activeType={activeType}
              isLoading={isFetching}
              onChangeType={handleTypeChange}
              onLoadMore={handleLoadMore}
              canLoadMore={canLoadMore}
            />
          )}

          {isError ? (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200">
              검색 API 응답이 지연되고 있습니다. 잠시 후 다시 시도해주세요.
            </div>
          ) : null}
        </section>
      </div>
      <SearchCommandPalette open={isCommandOpen} commands={commandItems} onClose={() => setIsCommandOpen(false)} />
    </AppShell>
  );
}
