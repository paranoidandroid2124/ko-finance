"use client";

import { AppShell } from "@/components/layout/AppShell";
import { GlobalSearchBar } from "@/components/search/GlobalSearchBar";
import { SearchResults } from "@/components/search/SearchResults";
import { EmptyState } from "@/components/ui/EmptyState";
import { SearchFiltersSidebar } from "./_components/SearchFiltersSidebar";
import { useSearchController } from "./_hooks/useSearchController";

export default function SearchPage() {
  const controller = useSearchController();

  return (
    <AppShell>
      <div className="flex min-h-[80vh] flex-col gap-6 lg:flex-row">
        <SearchFiltersSidebar filters={controller.filters} onChange={controller.handleFilterChange} />
        <section className="flex-1 space-y-6">
          <div className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <h1 className="text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark">통합 검색</h1>
                {controller.activeFilterChips.length > 0 ? (
                  <div className="flex flex-wrap gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                    {controller.activeFilterChips.map((chip) => (
                      <span key={chip} className="rounded-full bg-background-cardDark/40 px-3 py-1">
                        {chip}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
              <GlobalSearchBar
                value={controller.searchInput}
                onChange={controller.setSearchInput}
                onSubmit={controller.handleSearchSubmit}
                onOpenCommand={() => undefined}
                isLoading={controller.isFetching}
              />
            </div>
          </div>

          {!controller.hasQuery ? (
            <EmptyState
              title="검색어를 입력해주세요"
              description="회사명, 티커, 키워드를 입력하면 공시·뉴스·데이터가 탭으로 정리돼 표시됩니다."
              className="rounded-2xl border border-dashed border-border-light p-10 text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark"
            />
          ) : (
            <SearchResults
              results={controller.searchResults}
              totals={controller.totals ?? null}
              activeType={controller.activeType}
              isLoading={controller.isFetching}
              onChangeType={controller.handleTypeChange}
              onLoadMore={controller.handleLoadMore}
              canLoadMore={controller.canLoadMore}
            />
          )}

          {controller.isError ? (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200">
              검색 API 응답이 지연되고 있습니다. 잠시 후 다시 시도해주세요.
            </div>
          ) : null}
        </section>
      </div>
    </AppShell>
  );
}
