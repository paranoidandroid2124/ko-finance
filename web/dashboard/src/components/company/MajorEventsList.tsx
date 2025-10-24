"use client";

import { EventItem } from "@/hooks/useCompanySnapshot";

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
