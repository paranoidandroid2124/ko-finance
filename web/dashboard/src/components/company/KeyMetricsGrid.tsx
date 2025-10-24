"use client";

import { KeyMetric } from "@/hooks/useCompanySnapshot";

type KeyMetricsGridProps = {
  metrics: KeyMetric[];
};

const formatNumber = (value?: number | null, unit?: string | null) => {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "N/A";
  }
  const formatter = new Intl.NumberFormat("ko-KR", {
    maximumFractionDigits: Math.abs(value) < 1 ? 3 : 2,
  });
  const formatted = formatter.format(value);
  return unit ? `${formatted}${unit}` : formatted;
};

export function KeyMetricsGrid({ metrics }: KeyMetricsGridProps) {
  if (!metrics.length) {
    return (
      <section className="rounded-xl border border-dashed border-border-light p-6 text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
        주요 재무 지표가 아직 산출되지 않았습니다. 사업/분기 보고서가 수집되면 자동으로 채워집니다.
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">핵심 지표</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map((metric) => (
          <article
            key={metric.metricCode}
            className="rounded-lg border border-border-light bg-background-light/70 p-4 text-sm transition-colors dark:border-border-dark dark:bg-background-dark/60"
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
              {metric.label}
            </p>
            <p className="mt-2 text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">
              {formatNumber(metric.value ?? null, metric.unit ?? null)}
            </p>
            <p className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              {metric.fiscalYear ? `${metric.fiscalYear}년` : ""} {metric.fiscalPeriod ?? ""}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
