"use client";

import { EventItem } from "@/hooks/useCompanySnapshot";
import { interpretDilution, interpretPValue } from "@/lib/insightTemplates";

type MajorEventsListProps = {
  events: EventItem[];
};

const formatDate = (value?: string | null) => {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString();
};

const toNumberOrNull = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const buildEventInsights = (derivedMetrics: Record<string, unknown> = {}) => {
  const insights: { label: string; message: string }[] = [];

  // A1: 이벤트 임팩트(p-value 해석)
  const pValue =
    toNumberOrNull(derivedMetrics.p_value) ??
    toNumberOrNull((derivedMetrics as Record<string, unknown>).pValue) ??
    toNumberOrNull((derivedMetrics as Record<string, unknown>).pvalue);
  if (pValue != null) {
    const interpreted = interpretPValue(pValue);
    insights.push({ label: "이벤트 임팩트", message: interpreted.message });
  }

  // D1: 희석 임팩트(이론적 가격 하락 압력)
  const dilution = interpretDilution({
    currentPrice: toNumberOrNull(derivedMetrics.current_price ?? (derivedMetrics as Record<string, unknown>).currentPrice),
    issuePrice: toNumberOrNull(derivedMetrics.issue_price ?? (derivedMetrics as Record<string, unknown>).issuePrice),
    existingShares: toNumberOrNull(
      derivedMetrics.existing_shares ?? (derivedMetrics as Record<string, unknown>).existingShares,
    ),
    newShares: toNumberOrNull(derivedMetrics.new_shares ?? (derivedMetrics as Record<string, unknown>).newShares),
  });
  if (dilution.pricePressurePercent != null) {
    insights.push({ label: "희석 임팩트", message: dilution.message });
  }

  // A2: Focus Score (??? ???)
  const focusScoreRaw = (derivedMetrics as Record<string, unknown>).focus_score;
  if (focusScoreRaw && typeof focusScoreRaw === "object") {
    const focusScore = focusScoreRaw as { total_score?: number; sub_scores?: Record<string, unknown> };
    if (typeof focusScore.total_score === "number") {
      const subs = focusScore.sub_scores ?? {};
      const subText = ["impact", "clarity", "consistency", "confirmation"]
        .map((key) => {
          const value = subs[key];
          if (typeof value === "number") {
            return `${key.charAt(0).toUpperCase() + key.slice(1)} ${value}`;
          }
          return null;
        })
        .filter(Boolean)
        .join(" � ");

      insights.push({
        label: "Focus Score",
        message: `?? ${Math.round(focusScore.total_score)}${subText ? ` (${subText})` : ""}`,
      });
    }
  }

  return insights;
};

export function MajorEventsList({ events }: MajorEventsListProps) {
  if (!events.length) {
    return (
      <section className="rounded-xl border border-dashed border-border-light p-6 text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
        주요사항 공시 이력이 아직 없습니다.
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <header className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">주요 이벤트</h2>
      </header>
      <ul className="space-y-3">
        {events.map((event) => (
          <li
            key={event.id}
            className="rounded-lg border border-border-light bg-background-light/70 px-4 py-3 text-sm dark:border-border-dark dark:bg-background-dark/60"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">{event.eventName ?? event.eventType}</p>
              <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                {formatDate(event.eventDate)}
              </span>
            </div>
            {event.reportName ? (
              <p className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">{event.reportName}</p>
            ) : null}
            {(() => {
              const insights = buildEventInsights(event.derivedMetrics);
              if (!insights.length) return null;
              return (
                <ul className="mt-2 space-y-1 text-xs text-text-primaryLight dark:text-text-primaryDark">
                  {insights.map((insight, idx) => (
                    <li
                      key={`${event.id}-insight-${idx}`}
                      className="rounded border border-border-light/60 px-2 py-1 dark:border-border-dark/60"
                    >
                      <p className="text-[11px] uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                        {insight.label}
                      </p>
                      <p className="mt-0.5">{insight.message}</p>
                    </li>
                  ))}
                </ul>
              );
            })()}
            {Object.keys(event.derivedMetrics ?? {}).length ? (
              <dl className="mt-2 grid grid-cols-2 gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                {Object.entries(event.derivedMetrics ?? {}).map(([key, value]) => (
                  <div key={key} className="flex flex-col rounded border border-border-light/60 px-2 py-1 dark:border-border-dark/60">
                    <dt className="font-semibold uppercase tracking-wide text-[10px]">{key}</dt>
                    <dd className="mt-1 text-[11px] text-text-primaryLight dark:text-text-primaryDark">{String(value)}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

