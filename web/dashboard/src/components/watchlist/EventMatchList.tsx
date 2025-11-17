"use client";

import { useMemo } from "react";

import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { ListState } from "@/components/ui/ListState";
import { formatDateTime, formatRelativeTime } from "@/lib/date";
import type { AlertEventMatch } from "@/lib/alertsApi";

type EventMatchListProps = {
  matches: AlertEventMatch[];
  loading?: boolean;
  limit?: number;
  emptyMessage?: string;
  className?: string;
};

export function EventMatchList({
  matches,
  loading = false,
  limit = 6,
  emptyMessage = "최근 매칭된 이벤트가 없습니다.",
  className,
}: EventMatchListProps) {
  const items = useMemo(() => matches.slice(0, limit), [matches, limit]);
  const state = loading ? "loading" : items.length === 0 ? "empty" : "ready";

  return (
    <ListState
      className={className}
      state={state}
      skeleton={<SkeletonBlock lines={3} />}
      emptyTitle="매칭 데이터 없음"
      emptyDescription={emptyMessage}
      emptyClassName="px-0 py-4 text-xs"
    >
      <div className="space-y-2">
        {items.map((match) => {
          const relativeMatchedAt = formatRelativeTime(match.matchedAt, { fallback: "시각 미상" });
          const absoluteMatchedAt = formatDateTime(match.matchedAt, {
            fallback: "시각 미상",
            includeSeconds: true,
          });
          return (
            <div
              key={`${match.eventId}-${match.alertId}`}
              className="rounded-lg border border-border-light/70 bg-background-base px-3 py-2 text-xs dark:border-border-dark/70 dark:bg-background-baseDark"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                  {match.ruleName}
                  <span className="ml-2 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary dark:bg-primary.dark/20 dark:text-primary.dark">
                    {match.eventType}
                  </span>
                </p>
                <span className="text-text-secondaryLight dark:text-text-secondaryDark" title={absoluteMatchedAt}>
                  {relativeMatchedAt}
                </span>
              </div>
              <p className="text-text-secondaryLight dark:text-text-secondaryDark">
                {match.ticker ?? "티커 미상"} · {match.corpName ?? "기업 미상"}
              </p>
            </div>
          );
        })}
      </div>
    </ListState>
  );
}
