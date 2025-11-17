"use client";

import Link from "next/link";
import type { Route } from "next";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { useBoards, type BoardSummary } from "@/hooks/useBoards";

const TYPE_LABEL: Record<BoardSummary["type"], string> = {
  watchlist: "Watchlist",
  sector: "Sector",
  theme: "Theme",
};

export default function BoardsPage() {
  const { data, isLoading, isError, refetch } = useBoards();

  if (isLoading) {
    return (
      <AppShell>
        <div className="space-y-6">
          <SkeletonBlock className="h-16" />
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <SkeletonBlock key={`board-skeleton-${index}`} className="h-48" />
            ))}
          </div>
        </div>
      </AppShell>
    );
  }

  if (isError) {
    return (
      <AppShell>
        <ErrorState
          title="보드 목록을 불러오지 못했습니다."
          description="네트워크 상태를 확인한 뒤 다시 시도해주세요."
          action={
            <button
              type="button"
              onClick={() => refetch()}
              className="rounded-lg border border-border-light px-3 py-1 text-sm font-semibold text-text-primaryLight hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-primaryDark"
            >
              다시 시도
            </button>
          }
        />
      </AppShell>
    );
  }

  const boards = data ?? [];

  return (
    <AppShell>
      <div className="space-y-6">
        <header className="flex flex-col gap-3">
          <h1 className="text-2xl font-semibold text-text-primaryLight dark:text-text-primaryDark">보드</h1>
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            워치리스트/섹터/테마별로 묶인 이벤트 신호를 한 눈에 살펴보고 바로 Drill-down 할 수 있습니다.
          </p>
        </header>

        {boards.length === 0 ? (
          <EmptyState
            title="보드가 없습니다"
            description="Watchlist 페이지에서 룰을 만들고 이벤트를 쌓으면 자동으로 보드가 생성됩니다."
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {boards.map((board) => (
              <Link
                key={board.id}
                href={`/boards/${encodeURIComponent(board.id)}` as Route}
                className="rounded-2xl border border-border-light bg-background-cardLight p-5 shadow-card transition hover:-translate-y-1.5 hover:border-primary hover:shadow-lg dark:border-border-dark dark:bg-background-cardDark"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">{board.name}</p>
                  <span className="rounded-full bg-background-cardDark/40 px-2 py-0.5 text-[11px] uppercase text-text-secondaryLight dark:bg-background-cardDark/60 dark:text-text-secondaryDark">
                    {TYPE_LABEL[board.type]}
                  </span>
                </div>
                <p className="mt-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark line-clamp-2">
                  {board.description ?? "최근 이벤트 요약을 확인하려면 클릭하세요."}
                </p>
                <div className="mt-4 flex items-center justify-between text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  <span>종목 {board.tickers.length}개</span>
                  <span>최근 알림 {board.recentAlerts}건</span>
                </div>
                <div className="mt-4 flex flex-wrap gap-2 text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
                  {board.tickers.slice(0, 4).map((ticker) => (
                    <span key={`${board.id}-${ticker}`} className="rounded-full bg-background-cardDark/30 px-2 py-0.5">
                      {ticker}
                    </span>
                  ))}
                  {board.tickers.length > 4 ? <span>+{board.tickers.length - 4}</span> : null}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
