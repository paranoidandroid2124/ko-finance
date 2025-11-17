"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import type { Route } from "next";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { useBoardDetail } from "@/hooks/useBoards";

const sentimentColor = (value?: number | null) => {
  if (value === null || value === undefined) {
    return "text-text-secondaryLight dark:text-text-secondaryDark";
  }
  if (value > 0.2) {
    return "text-emerald-500";
  }
  if (value < -0.2) {
    return "text-red-500";
  }
  return "text-amber-500";
};

export default function BoardDetailPage() {
  const params = useParams<{ boardId: string }>();
  const router = useRouter();
  const boardsRoute = "/boards" as Route;
  const boardId = params?.boardId ?? "";
  const { data, isLoading, isError, refetch } = useBoardDetail(boardId);

  const entries = data?.entries ?? [];
  const timeline = data?.timeline ?? [];
  const board = data?.board;

  const isEmpty = !isLoading && !board;

  const sortedEntries = useMemo(() => entries.sort((a, b) => b.eventCount - a.eventCount), [entries]);

  if (isLoading) {
    return (
      <AppShell>
        <div className="space-y-6">
          <SkeletonBlock className="h-20" />
          <SkeletonBlock className="h-64" />
          <SkeletonBlock className="h-80" />
        </div>
      </AppShell>
    );
  }

  if (isError) {
    return (
      <AppShell>
        <ErrorState
          title="보드 데이터를 불러오지 못했습니다."
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

  if (isEmpty) {
    return (
      <AppShell>
        <EmptyState
          title="보드를 찾을 수 없습니다"
          description="이 보드에 연결된 룰이 존재하지 않거나 이벤트 기록이 없습니다."
          action={
            <button
              type="button"
              onClick={() => router.push(boardsRoute)}
              className="rounded-lg border border-border-light px-3 py-1 text-sm font-semibold text-text-primaryLight hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-primaryDark"
            >
              목록으로 돌아가기
            </button>
          }
        />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-8">
        <section className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm uppercase text-text-secondaryLight dark:text-text-secondaryDark">{board?.type}</p>
              <h1 className="text-2xl font-semibold text-text-primaryLight dark:text-text-primaryDark">{board?.name}</h1>
              <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                {board?.description ?? "최근 이벤트와 알림을 모아놓은 보드입니다."}
              </p>
            </div>
            <div className="flex gap-4 text-sm">
              <div>
                <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">최근 이벤트</p>
                <p className="text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark">{board?.eventCount ?? 0}건</p>
              </div>
              <div>
                <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">알림 채널</p>
                <p className="text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark">{board?.channels.length ?? 0}</p>
              </div>
            </div>
          </div>
          {board?.tickers?.length ? (
            <div className="mt-4 flex flex-wrap gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              {board.tickers.map((ticker) => (
                <Link
                  key={`${board.id}-${ticker}`}
                  href={`/company/${ticker}`}
                  className="rounded-full border border-border-light px-3 py-1 transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark"
                >
                  {ticker}
                </Link>
              ))}
            </div>
          ) : null}
        </section>

        <section className="rounded-2xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">종목 리스트</h2>
            <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">최근 이벤트 기준 정렬</span>
          </div>
          {sortedEntries.length === 0 ? (
            <EmptyState
              title="표시할 종목이 없습니다"
              description="이 보드에 연결된 종목의 이벤트가 아직 없습니다."
              className="border-none"
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border-light text-xs uppercase tracking-wide text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
                    <th className="py-2 pr-4">종목</th>
                    <th className="py-2 pr-4">이벤트 수</th>
                    <th className="py-2 pr-4">최근 헤드라인</th>
                    <th className="py-2 pr-4">감성</th>
                    <th className="py-2 pr-4">최근 시각</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedEntries.map((entry) => (
                    <tr key={entry.ticker} className="border-b border-border-light last:border-b-0 dark:border-border-dark">
                      <td className="py-3 pr-4">
                        <Link href={`/company/${entry.ticker}`} className="font-semibold text-primary hover:underline dark:text-primary.dark">
                          {entry.ticker}
                        </Link>
                        <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{entry.corpName}</p>
                      </td>
                      <td className="py-3 pr-4">{entry.eventCount}</td>
                      <td className="py-3 pr-4 text-sm text-text-primaryLight dark:text-text-primaryDark">
                        {entry.lastHeadline ?? "헤드라인 없음"}
                      </td>
                      <td className={`py-3 pr-4 text-sm font-semibold ${sentimentColor(entry.sentiment)}`}>
                        {entry.sentiment !== undefined && entry.sentiment !== null ? entry.sentiment.toFixed(2) : "N/A"}
                      </td>
                      <td className="py-3 pr-4 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                        {entry.lastEventAt ? new Date(entry.lastEventAt).toLocaleString() : "미기록"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">타임라인</h2>
            <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">최신순</span>
          </div>
          {timeline.length === 0 ? (
            <EmptyState
              title="타임라인 이벤트가 없습니다"
              description="알림이 수집되면 타임라인에 표시됩니다."
              className="border-none"
            />
          ) : (
            <ul className="space-y-3">
              {timeline.map((event) => (
                <li key={event.id} className="rounded-xl border border-border-light px-4 py-3 text-sm text-text-primaryLight dark:border-border-dark dark:text-text-primaryDark">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-semibold">{event.headline}</p>
                    <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                      {event.deliveredAt ? new Date(event.deliveredAt).toLocaleString() : "시간 미기록"}
                    </span>
                  </div>
                  <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{event.summary}</p>
                  <div className="mt-2 flex items-center gap-3 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                    {event.channel ? <span className="rounded-full bg-background-cardDark/40 px-2 py-0.5">{event.channel}</span> : null}
                    {event.sentiment !== undefined && event.sentiment !== null ? (
                      <span className={sentimentColor(event.sentiment)}>감성 {event.sentiment.toFixed(2)}</span>
                    ) : null}
                    {event.url ? (
                      <a
                        href={event.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-semibold text-primary hover:underline dark:text-primary.dark"
                      >
                        자세히 보기
                      </a>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </AppShell>
  );
}
