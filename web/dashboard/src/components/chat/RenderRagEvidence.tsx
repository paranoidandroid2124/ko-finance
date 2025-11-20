"use client";

import { useMemo } from "react";
import { ChatEvidencePanelNotice } from "@/components/legal";
import type {
  GuardrailLevel,
  GuardrailTelemetry,
  MetricSummary,
  MetricsTelemetry,
  RagEvidenceItem
} from "@/store/chatStore";

type RagEvidencePanelProps = {
  status: "idle" | "loading" | "ready" | "error";
  items: RagEvidenceItem[];
  activeId?: string;
  confidence?: number;
  errorMessage?: string;
  guardrail: GuardrailTelemetry;
  metrics: MetricsTelemetry;
  onSelectItem?: (itemId: string) => void;
  onOpenSource?: (itemId: string) => void;
};

const STATUS_HINT: Record<RagEvidencePanelProps["status"], string> = {
  loading: "RAG 근거를 불러오는 중입니다.",
  idle: "표시할 RAG 근거가 아직 없습니다.",
  ready: "RAG 근거가 준비되었습니다.",
  error: "근거를 가져오지 못했습니다."
};

const MIN_CONFIDENCE = 0;
const MAX_CONFIDENCE = 100;

const GUARDRAIL_LABEL: Record<GuardrailLevel, string> = {
  pass: "정상",
  warn: "주의",
  fail: "차단"
};

const GUARDRAIL_TONE: Record<GuardrailLevel, { badge: string; container: string }> = {
  pass: {
    badge:
      "border-emerald-400 bg-emerald-500/10 text-emerald-600 dark:border-emerald-300/40 dark:bg-emerald-500/10 dark:text-emerald-200",
    container:
      "border-emerald-200 bg-emerald-50/70 text-emerald-700 dark:border-emerald-400/40 dark:bg-emerald-500/5 dark:text-emerald-200"
  },
  warn: {
    badge:
      "border-amber-400 bg-amber-500/10 text-amber-600 dark:border-amber-300/40 dark:bg-amber-500/10 dark:text-amber-200",
    container:
      "border-amber-200 bg-amber-50/70 text-amber-700 dark:border-amber-300/40 dark:bg-amber-500/5 dark:text-amber-200"
  },
  fail: {
    badge:
      "border-destructive/70 bg-destructive/10 text-destructive dark:border-destructive/60 dark:bg-destructive/15 dark:text-destructive",
    container:
      "border-destructive/60 bg-destructive/5 text-destructive dark:border-destructive/60 dark:bg-destructive/20 dark:text-destructive"
  }
};

const METRIC_TONE: Record<NonNullable<MetricSummary["trend"]>, string> = {
  up: "text-emerald-600 dark:text-emerald-200",
  down: "text-destructive",
  flat: "text-text-secondaryLight dark:text-text-secondaryDark"
};

function format_confidence_text(confidence?: number) {
  if (typeof confidence !== "number" || Number.isNaN(confidence)) {
    return null;
  }
  const normalized = Math.min(Math.max(confidence * 100, MIN_CONFIDENCE), MAX_CONFIDENCE);
  return `${Math.round(normalized)}% 신뢰도`;
}

export function RagEvidencePanel({
  status,
  items,
  activeId,
  confidence,
  errorMessage,
  guardrail,
  metrics,
  onSelectItem,
  onOpenSource
}: RagEvidencePanelProps) {
  const confidenceLabel = useMemo(() => format_confidence_text(confidence), [confidence]);

  const guardrailBadge = useMemo(() => {
    if (guardrail.status !== "ready" || !guardrail.level) {
      return null;
    }
    const tone = GUARDRAIL_TONE[guardrail.level];
    return (
      <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-semibold ${tone.badge}`}>
        {GUARDRAIL_LABEL[guardrail.level]}
      </span>
    );
  }, [guardrail]);

  const handle_select_item = (candidateId: string) => {
    if (onSelectItem) {
      onSelectItem(candidateId);
    }
  };

  const handle_open_source = (candidateId: string) => {
    if (onOpenSource) {
      onOpenSource(candidateId);
    }
  };

  const showSkeleton = status === "loading";
  const noEvidence = items.length === 0;
  const showEmptyState = (status === "idle" || status === "ready") && noEvidence;
  const showErrorState = status === "error";

  const hintText = showErrorState && errorMessage ? errorMessage : STATUS_HINT[status];

  const render_guardrail = () => {
    if (guardrail.status === "loading") {
      return (
        <div className="flex flex-col gap-2 rounded-lg border border-border-light/70 bg-background-cardLight/60 p-3 transition-motion-medium dark:border-border-dark/50 dark:bg-background-cardDark/40">
          <div className="h-3 w-16 motion-shimmer animate-motion-shimmer animate-pulse rounded bg-border-light/60 dark:bg-border-dark/40" />
          <div className="h-3 w-3/4 motion-shimmer animate-motion-shimmer animate-pulse rounded bg-border-light/50 dark:bg-border-dark/30" />
        </div>
      );
    }

    if (guardrail.status === "error") {
      return (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-[11px] text-destructive transition-motion-medium dark:border-destructive/60 dark:bg-destructive/15">
            <p>Guardrail 정보를 불러오지 못했습니다.</p>
          {guardrail.errorMessage ? <p className="mt-1">{guardrail.errorMessage}</p> : null}
        </div>
      );
    }

    if (guardrail.status === "ready" && guardrail.level) {
      const tone = GUARDRAIL_TONE[guardrail.level];
      return (
        <div className={`space-y-2 rounded-lg border px-3 py-3 text-[11px] transition-motion-medium motion-safe:hover:-translate-y-0.5 ${tone.container}`}>
          <div className="flex items-center justify-between gap-2">
            <p className="font-semibold">가드레일 상태</p>
            {guardrailBadge}
          </div>
          <p className="leading-relaxed">{guardrail.message}</p>
        </div>
      );
    }

    return (
      <div className="rounded-lg border border-dashed border-border-light px-3 py-3 text-[11px] text-text-secondaryLight transition-motion-medium dark:border-border-dark dark:text-text-secondaryDark">
        가드레일 결과가 준비되면 여기에 표시됩니다.
      </div>
    );
  };

  const render_metrics = () => {
    if (metrics.status === "loading") {
      return (
        <div className="grid gap-2">
          {Array.from({ length: 2 }).map((_, index) => (
            <div
              key={`metric-skeleton-${index}`}
              className="rounded-lg border border-border-light/70 bg-background-cardLight/60 p-3 transition-motion-medium dark:border-border-dark/50 dark:bg-background-cardDark/40"
            >
              <div className="h-3 w-1/3 motion-shimmer animate-motion-shimmer animate-pulse rounded bg-border-light/60 dark:bg-border-dark/40" />
              <div className="mt-2 h-4 w-16 motion-shimmer animate-motion-shimmer animate-pulse rounded bg-border-light/50 dark:bg-border-dark/30" />
              <div className="mt-2 h-3 w-1/2 motion-shimmer animate-motion-shimmer animate-pulse rounded bg-border-light/40 dark:bg-border-dark/20" />
            </div>
          ))}
        </div>
      );
    }

    if (metrics.status === "error") {
      return (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-3 text-[11px] text-destructive transition-motion-medium dark:border-destructive/60 dark:bg-destructive/15">
          <p>주요 지표를 표시할 수 없습니다.</p>
          {metrics.errorMessage ? <p className="mt-1">{metrics.errorMessage}</p> : null}
        </div>
      );
    }

    if (metrics.status === "ready" && metrics.items.length > 0) {
      return (
        <div className="grid gap-2">
          {metrics.items.map((metric) => {
            const tone = metric.trend ? METRIC_TONE[metric.trend] : "text-text-secondaryLight dark:text-text-secondaryDark";
            return (
              <div
                key={metric.id}
                className="rounded-lg border border-border-light px-3 py-3 text-[11px] transition-motion-medium motion-safe:hover:-translate-y-0.5 dark:border-border-dark"
              >
                <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{metric.label}</p>
                <p className="mt-1 text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">{metric.value}</p>
                <div className="mt-2 flex items-center justify-between">
                  {metric.change ? <span className={`text-[11px] font-medium ${tone}`}>{metric.change}</span> : <span />}
                  {metric.description ? (
                    <span className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">{metric.description}</span>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      );
    }

    return (
      <div className="rounded-lg border border-dashed border-border-light px-3 py-3 text-[11px] text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
        표시할 지표 요약이 없습니다.
      </div>
    );
  };

  return (
    <section className="space-y-3 rounded-xl border border-border-light bg-white/70 p-3 text-xs shadow-sm transition-colors transition-motion-medium dark:border-border-dark dark:bg-white/5">
      <header className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase text-primary">RAG 근거</p>
          <p className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">{hintText}</p>
          <ChatEvidencePanelNotice className="mt-1 text-[11px] text-text-secondaryLight dark:text-text-secondaryDark" />
        </div>
        {confidenceLabel && (
          <span className="rounded-md border border-primary/40 px-2 py-1 text-[11px] font-semibold text-primary dark:border-primary/30">
            {confidenceLabel}
          </span>
        )}
      </header>

      <div className="space-y-3">
        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">가드레일</p>
          {render_guardrail()}
        </div>
        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">주요 지표</p>
          {render_metrics()}
        </div>
      </div>

      {showSkeleton ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, index) => (
            <div
              key={`skeleton-${index}`}
              className="animate-pulse rounded-lg border border-border-light/60 bg-background-cardLight px-3 py-3 dark:border-border-dark/40 dark:bg-background-cardDark"
            >
              <div className="h-3 w-3/4 rounded bg-border-light/70 dark:bg-border-dark/40" />
              <div className="mt-2 h-3 w-full rounded bg-border-light/60 dark:bg-border-dark/30" />
              <div className="mt-1 h-3 w-2/3 rounded bg-border-light/50 dark:bg-border-dark/20" />
            </div>
          ))}
        </div>
      ) : null}

      {showEmptyState ? (
        <div className="rounded-lg border border-dashed border-border-light px-3 py-6 text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
          질문을 전송하면 연관된 근거가 여기에 표시됩니다.
        </div>
      ) : null}

      {showErrorState ? (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-4 text-text-secondaryLight dark:border-destructive/50 dark:bg-destructive/10 dark:text-text-secondaryDark">
          guardrail이 활성화되었거나 네트워크 문제가 발생했습니다. 다시 시도해주세요.
        </div>
      ) : null}

      {!showSkeleton && !showEmptyState && !showErrorState ? (
        <ul className="space-y-2">
          {items.map((item) => {
            const isActive = item.id === activeId;
            return (
              <li
                key={item.id}
                className={`rounded-lg border px-3 py-3 transition-motion-medium motion-safe:hover:-translate-y-1 ${
                  isActive
                    ? "border-primary bg-primary/5 text-text-primaryLight dark:border-primary.dark dark:bg-primary/10"
                    : "border-border-light bg-white text-text-secondaryLight shadow-sm transition-colors hover:border-primary/50 hover:text-text-primaryLight dark:border-border-dark dark:bg-white/5 dark:text-text-secondaryDark"
                }`}
              >
                <button
                  type="button"
                  className="w-full text-left transition-motion-fast focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                  aria-pressed={isActive}
                  onClick={() => handle_select_item(item.id)}
                >
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-primary">{item.title}</p>
                  <p className="mt-2 leading-6 text-[13px] text-text-secondaryLight dark:text-text-secondaryDark">
                    {item.snippet}
                  </p>
                </button>
                <div className="mt-3 flex items-center justify-between text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                  <span>p.{item.page ?? "?"}</span>
                  <div className="flex items-center gap-2">
                    {typeof item.score === "number" && (
                      <span className="rounded bg-border-light/50 px-2 py-0.5 text-[10px] transition-motion-fast dark:bg-border-dark/40">
                        {Math.round(item.score * 100)}점
                      </span>
                    )}
                    {item.sourceUrl ? (
                      <button
                        type="button"
                        className="text-primary underline-offset-2 hover:underline"
                        onClick={() => handle_open_source(item.id)}
                      >
                        원문 보기
                      </button>
                    ) : null}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}

