"use client";

import { useMemo } from "react";
import type { DashboardAlert } from "@/hooks/useDashboardOverview";

const toneBadge: Record<DashboardAlert["tone"], string> = {
  positive: "bg-accent-positive/15 text-accent-positive",
  negative: "bg-accent-negative/15 text-accent-negative",
  warning: "bg-accent-warning/20 text-accent-warning",
  neutral: "bg-border-light/60 text-text-secondaryLight dark:bg-border-dark/60 dark:text-text-secondaryDark"
};

type AlertFeedProps = {
  alerts: DashboardAlert[];
  onSelect?: (alert: DashboardAlert) => void;
};

export function AlertFeed({ alerts, onSelect }: AlertFeedProps) {
  const items = useMemo(() => alerts.slice(0, 5), [alerts]);

  return (
    <div className="rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <h3 className="text-sm font-semibold">실시간 알림</h3>
      {items.length ? (
        <div className="mt-3 space-y-3 text-sm">
          {items.map((alert) => (
            <button
              key={alert.id}
              onClick={() => onSelect?.(alert)}
              className="w-full rounded-lg border border-border-light/70 p-3 text-left transition-colors hover:border-primary hover:text-primary dark:border-border-dark/70"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium leading-tight">{alert.title}</p>
                  <p className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">{alert.body}</p>
                </div>
                {alert.tone && (
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize ${toneBadge[alert.tone]}`}
                  >
                    {alert.tone}
                  </span>
                )}
              </div>
              <p className="mt-2 text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">{alert.timestamp}</p>
            </button>
          ))}
        </div>
      ) : (
        <p className="mt-3 rounded-lg border border-dashed border-border-light px-3 py-4 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
          표시할 알림이 없습니다. 데이터가 수집되면 자동으로 나타납니다.
        </p>
      )}
    </div>
  );
}
