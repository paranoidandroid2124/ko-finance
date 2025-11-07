"use client";

import clsx from "clsx";

type RagSlaSummaryCardProps = {
  metrics: {
    totalRuns: number;
    breachCount: number;
    metCount: number;
    satisfiedRate: number | null;
    targetMinutes: number | null;
    toneClass: string;
  } | null;
  latencyLabels: {
    p50Duration?: string | null;
    p95Duration?: string | null;
    p50Queue?: string | null;
    p95Queue?: string | null;
  } | null;
  queueSnapshot: {
    toneClass: string;
    oldestLabel: string | null;
    cooldownLabel: string | null;
    nextAutoLabel: string | null;
  } | null;
  queueSummary: {
    ready?: number | null;
    slaRiskCount?: number | null;
    coolingDown?: number | null;
  } | null;
  slaSummaryLoading: boolean;
  dataSourceSuffix: string;
  satisfiedRateDecimals: number;
};

export function RagSlaSummaryCard({
  metrics,
  latencyLabels,
  queueSnapshot,
  queueSummary,
  slaSummaryLoading,
  dataSourceSuffix,
  satisfiedRateDecimals,
}: RagSlaSummaryCardProps) {
  if (!metrics && !queueSummary) {
    return null;
  }

  return (
    <section className="grid gap-3 rounded-xl bg-background-base p-4 dark:bg-background-cardDark md:grid-cols-2">
      <article className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
          SLA 목표
        </p>
        <p className="text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark">
          {metrics?.targetMinutes ? `${metrics.targetMinutes}분 이내` : "—"}
        </p>
        <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
          {slaSummaryLoading && !metrics
            ? "SLA 지표를 불러오는 중이에요."
            : metrics
            ? `최근 ${metrics.totalRuns}회 중 ${metrics.metCount}회는 약속을 지켰어요${dataSourceSuffix}.`
            : "재색인 기록이 아직 없어요."}
        </p>
        {metrics?.satisfiedRate !== null && metrics?.satisfiedRate !== undefined ? (
          <p className={clsx("text-sm font-semibold", metrics.toneClass)}>
            {metrics.satisfiedRate.toFixed(satisfiedRateDecimals)}% 만족 ({metrics.breachCount}회 지연)
          </p>
        ) : slaSummaryLoading ? (
          <p className="text-sm text-text-tertiaryLight dark:text-text-tertiaryDark">지표를 불러오는 중이에요…</p>
        ) : null}
      </article>

      <article className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
          재색인 속도
        </p>
        <p className="text-sm text-text-primaryLight dark:text-text-primaryDark">
          p50 {latencyLabels?.p50Duration ?? "—"}
        </p>
        <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
          95% 구간은 {latencyLabels?.p95Duration ?? "—"} 이내예요.
        </p>
        <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">대기 포함 기준이에요.</p>
      </article>

      <article className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
          대기열 체감
        </p>
        <p className="text-sm text-text-primaryLight dark:text-text-primaryDark">
          p50 {latencyLabels?.p50Queue ?? "—"} · p95 {latencyLabels?.p95Queue ?? "—"}
        </p>
        <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
          빠르게 새 Evidence를 만날 수 있도록 살피고 있어요.
        </p>
      </article>

      <article className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
          큐 건강도
        </p>
        <p className={clsx("text-sm font-semibold", queueSnapshot?.toneClass ?? "text-text-primaryLight dark:text-text-primaryDark")}>
          대기 {queueSummary?.ready ?? 0}건 · 위험 {queueSummary?.slaRiskCount ?? 0}건 · 쿨다운 {queueSummary?.coolingDown ?? 0}건
        </p>
        <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
          가장 오래 기다린 작업은 {queueSnapshot?.oldestLabel ?? "—"}째 기다리고 있어요.
        </p>
        <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
          쿨다운 평균 {queueSnapshot?.cooldownLabel ?? "—"} 남았어요.
        </p>
        <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
          다음 자동 재시도는 {queueSnapshot?.nextAutoLabel ?? "준비 중"}에 이어질 예정이에요.
        </p>
      </article>
    </section>
  );
}
