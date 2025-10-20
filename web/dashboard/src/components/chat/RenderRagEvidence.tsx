"use client";

import { useMemo } from "react";
import type { RagEvidenceItem } from "@/store/chatStore";

type RagEvidencePanelProps = {
  status: "idle" | "loading" | "ready" | "error";
  items: RagEvidenceItem[];
  activeId?: string;
  confidence?: number;
  errorMessage?: string;
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

function format_confidence_text(confidence?: number) {
  if (typeof confidence !== "number" || Number.isNaN(confidence)) {
    return null;
  }
  const normalized = Math.min(Math.max(confidence * 100, MIN_CONFIDENCE), MAX_CONFIDENCE);
  return `${Math.round(normalized)}% 신뢰도`;
}

export function render_evidence_panel({
  status,
  items,
  activeId,
  confidence,
  errorMessage,
  onSelectItem,
  onOpenSource
}: RagEvidencePanelProps) {
  const confidenceLabel = useMemo(() => format_confidence_text(confidence), [confidence]);

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

  return (
    <section className="space-y-3 rounded-xl border border-border-light bg-white/70 p-3 text-xs shadow-sm transition-colors dark:border-border-dark dark:bg-white/5">
      <header className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase text-primary">RAG 근거</p>
          <p className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">{hintText}</p>
        </div>
        {confidenceLabel && (
          <span className="rounded-md border border-primary/40 px-2 py-1 text-[11px] font-semibold text-primary dark:border-primary/30">
            {confidenceLabel}
          </span>
        )}
      </header>

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
                className={`rounded-lg border px-3 py-3 ${
                  isActive
                    ? "border-primary bg-primary/5 text-text-primaryLight dark:border-primary.dark dark:bg-primary/10"
                    : "border-border-light bg-white text-text-secondaryLight shadow-sm transition-colors hover:border-primary/50 hover:text-text-primaryLight dark:border-border-dark dark:bg-white/5 dark:text-text-secondaryDark"
                }`}
              >
                <button
                  type="button"
                  className="w-full text-left"
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
                      <span className="rounded bg-border-light/50 px-2 py-0.5 text-[10px] dark:bg-border-dark/40">
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

export const RagEvidencePanel = render_evidence_panel;
