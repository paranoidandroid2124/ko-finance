"use client";

import classNames from "classnames";
import { useCallback, useMemo } from "react";
import { ChatAnswerBadge } from "@/components/legal";
import ToolWidgetRenderer from "@/components/chat/ToolWidgetRenderer";
import RagSourcesWidget from "@/components/chat/widgets/RagSourcesWidget";
import type { ChatMessageMeta, ChatRole, CitationEntry, CitationMap, RagSourceReference } from "@/store/chatStore";
import { useToastStore } from "@/store/toastStore";
import { logEvent } from "@/lib/telemetry";
import { renderChatContent } from "@/lib/renderChatContent";

export type ChatMessageProps = {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: string;
  meta?: ChatMessageMeta;
  isGuardrail?: boolean;
  onRetry?: () => void;
};

const statusLabel: Record<NonNullable<ChatMessageMeta["status"]>, string> = {
  pending: "답변 준비 중",
  streaming: "전송 중",
  ready: "완료",
  error: "실패",
  blocked: "차단됨"
};

type NormalizedCitation = {
  id: string;
  bucket?: string;
  label: string;
  pageNumber?: number;
  deeplinkUrl?: string;
  fallbackUrl?: string;
  charStart?: number;
  charEnd?: number;
  sentenceHash?: string;
  documentId?: string;
  chunkId?: string;
  excerpt?: string;
};

const CITATION_BUCKET_LABELS: Record<string, string> = {
  page: "페이지",
  table: "표",
  footnote: "각주"
};

const coerceNumber = (value: unknown): number | undefined => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim().length) {
    const parsed = Number(value);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  return undefined;
};

const coerceString = (value: unknown): string | undefined => {
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (trimmed.length) {
      return trimmed;
    }
  }
  return undefined;
};

const normalizeCitationEntry = (
  bucket: string,
  entry: CitationEntry,
  index: number
): NormalizedCitation | null => {
  if (typeof entry === "string") {
    const label = entry.trim();
    if (!label) {
      return null;
    }
    return {
      id: `${bucket}-${index}`,
      bucket,
      label
    };
  }
  if (!entry || typeof entry !== "object") {
    return null;
  }
  const pageNumber =
    coerceNumber(entry.pageNumber) ?? coerceNumber(entry.page_number) ?? coerceNumber(entry.page);
  const label =
    coerceString(entry.label) ??
    (pageNumber ? `(p.${pageNumber})` : undefined) ??
    coerceString(bucket) ??
    "출처";
  const deeplinkUrl = coerceString(entry.deeplinkUrl ?? entry.deeplink_url);
  const fallbackUrl =
    coerceString(entry.documentUrl ?? entry.document_url) ??
    coerceString(entry.viewerUrl ?? entry.viewer_url) ??
    coerceString(entry.sourceUrl ?? entry.source_url) ??
    coerceString(entry.downloadUrl ?? entry.download_url);
  return {
    id: `${bucket}-${index}`,
    bucket,
    label: label ?? "출처",
    pageNumber,
    deeplinkUrl,
    fallbackUrl,
    charStart: coerceNumber(entry.charStart ?? entry.char_start),
    charEnd: coerceNumber(entry.charEnd ?? entry.char_end),
    sentenceHash: coerceString(entry.sentenceHash ?? entry.sentence_hash),
    documentId: coerceString(entry.documentId ?? entry.document_id),
    chunkId: coerceString(entry.chunkId ?? entry.chunk_id),
    excerpt: coerceString(entry.excerpt)
  };
};

const normalizeCitations = (citations?: CitationMap): NormalizedCitation[] => {
  if (!citations) {
    return [];
  }
  const normalized: NormalizedCitation[] = [];
  Object.entries(citations).forEach(([bucket, values]) => {
    if (!Array.isArray(values) || values.length === 0) {
      return;
    }
    values.forEach((entry, index) => {
      const normalizedEntry = normalizeCitationEntry(bucket, entry, index);
      if (normalizedEntry) {
        normalized.push(normalizedEntry);
      }
    });
  });
  return normalized;
};

export function ChatMessageBubble({ role, content, timestamp, meta, isGuardrail, onRetry }: ChatMessageProps) {
  const isUser = role === "user";
  const status = meta?.status;
  const showStatusBadge = !isUser && status && status !== "ready";
  const errorMessage =
    typeof meta?.errorMessage === "string" && meta.errorMessage.length > 0
      ? meta.errorMessage
      : "답변을 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.";
  const canRetry = Boolean(meta?.retryable && onRetry);
  const showToast = useToastStore((state) => state.show);
  const normalizedCitations = useMemo(() => normalizeCitations(meta?.citations), [meta?.citations]);
  const ragSources = useMemo(() => {
    if (!meta?.sources || !Array.isArray(meta.sources)) {
      return [] as RagSourceReference[];
    }
    return meta.sources.filter(
      (source): source is RagSourceReference => Boolean(source && typeof source === "object")
    );
  }, [meta?.sources]);
  const memoryMeta = (meta?.memory ?? null) as
    | {
        enabled?: boolean;
        required?: boolean;
        applied?: boolean;
        reason?: string;
      }
    | null;

  const memoryBadge = useMemo(() => {
    if (!memoryMeta) {
      return null;
    }
    if (memoryMeta.applied) {
      return {
        label: "LightMem 적용",
        tone: "positive",
        description: "최근 대화 요약과 비교 맥락을 활용했습니다."
      };
    }
    if (memoryMeta.required && memoryMeta.enabled === false) {
      return {
        label: "LightMem 비활성",
        tone: "warning",
        description: memoryMeta.reason
          ? `메모리를 사용할 수 없습니다: ${memoryMeta.reason}`
          : "현재 플랜/설정에서 LightMem 기능이 꺼져 있습니다."
      };
    }
    if (memoryMeta.required) {
      return {
        label: "LightMem 준비 중",
        tone: "info",
        description: "비교 요청을 위해 메모리를 불러오는 중입니다."
      };
    }
    return null;
  }, [memoryMeta]);

  const handleOpenCitation = useCallback(
    (citation: NormalizedCitation) => {
      if (!citation.deeplinkUrl && !citation.fallbackUrl) {
        showToast({
          intent: "warning",
          title: "링크를 열 수 없습니다",
          message: "연결된 문서 URL이 포함되지 않은 출처입니다."
        });
        logEvent("rag.deeplink_failed", {
          reason: "missing_url",
          bucket: citation.bucket,
          pageNumber: citation.pageNumber,
          chunkId: citation.chunkId
        });
        return;
      }
      const target = citation.deeplinkUrl ?? citation.fallbackUrl!;
      const opened = window.open(target, "_blank", "noopener,noreferrer");
      if (!opened) {
        showToast({
          intent: "warning",
          title: "팝업이 차단되었어요",
          message: "브라우저 팝업 차단을 해제하거나 링크를 길게 눌러 새 탭에서 열어주세요."
        });
        logEvent("rag.deeplink_failed", {
          reason: "popup_blocked",
          bucket: citation.bucket,
          pageNumber: citation.pageNumber,
          chunkId: citation.chunkId,
          hasDeeplink: Boolean(citation.deeplinkUrl)
        });
        return;
      }
      logEvent("rag.deeplink_opened", {
        bucket: citation.bucket,
        pageNumber: citation.pageNumber,
        chunkId: citation.chunkId,
        documentId: citation.documentId,
        hasDeeplink: Boolean(citation.deeplinkUrl)
      });
    },
    [showToast]
  );

  return (
    <div className={classNames("group flex w-full gap-3", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/20 text-sm font-semibold text-primary transition-motion-fast motion-safe:group-hover:-translate-y-1">
          AI
        </div>
      )}
      <div
        className={classNames(
          "max-w-[80%] rounded-3xl px-5 py-4 text-sm leading-relaxed shadow-[0_15px_45px_rgba(3,7,18,0.45)] transition-all motion-safe:hover:-translate-y-1 motion-safe:group-hover:-translate-y-1",
          isUser
            ? "bg-gradient-to-br from-blue-600 to-cyan-500 text-white shadow-blue-500/30"
            : "border border-white/10 bg-[#0b1425]/85 text-slate-200 backdrop-blur-xl"
        )}
      >
        {!isUser ? (
          <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] font-medium text-text-secondaryLight dark:text-text-secondaryDark">
            <ChatAnswerBadge />
            {memoryBadge ? (
              <span
                className={classNames(
                  "rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wide",
                  memoryBadge.tone === "positive" && "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-200",
                  memoryBadge.tone === "warning" && "bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-200",
                  memoryBadge.tone === "info" && "bg-primary/10 text-primary dark:bg-primary.dark/20 dark:text-primary.dark"
                )}
                title={memoryBadge.description}
              >
                {memoryBadge.label}
              </span>
            ) : null}
          </div>
        ) : null}
        <div className="flex items-start gap-2">
          <p className="flex-1 whitespace-pre-wrap leading-relaxed">
            {typeof content === "string" ? renderChatContent(content) : content}
            {isGuardrail && (
              <span className="mt-2 block text-xs text-accent-warning">
                guardrail 경고가 감지되어 안전 메시지로 대체되었습니다.
              </span>
            )}
          </p>
          {showStatusBadge && status && (
            <span className="shrink-0 rounded-full bg-border-light px-2 py-0.5 text-[10px] font-semibold uppercase text-text-secondaryLight dark:bg-border-dark dark:text-text-secondaryDark">
              {statusLabel[status] ?? status}
            </span>
          )}
        </div>
        {!isUser && ragSources.length ? (
          <div className="mt-3">
            <RagSourcesWidget sources={ragSources} />
          </div>
        ) : null}
        {!isUser && normalizedCitations.length ? (
          <div className="mt-3 rounded-lg border border-border-light/80 bg-white/70 p-3 text-xs text-text-secondaryLight dark:border-border-dark/70 dark:bg-background-cardDark/70 dark:text-text-secondaryDark">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-primary">출처</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {normalizedCitations.map((citation) => {
                const bucketLabel = citation.bucket ? CITATION_BUCKET_LABELS[citation.bucket] ?? citation.bucket : null;
                const descriptionParts = [
                  bucketLabel,
                  citation.pageNumber ? `${citation.pageNumber}쪽` : null,
                  citation.excerpt
                ].filter(Boolean);
                const title = descriptionParts.join(" · ");
                const clickable = Boolean(citation.deeplinkUrl || citation.fallbackUrl);
                return (
                  <button
                    key={citation.id}
                    type="button"
                    disabled={!clickable}
                    title={title || undefined}
                    onClick={() => (clickable ? handleOpenCitation(citation) : undefined)}
                    className={classNames(
                      "inline-flex items-center gap-1 rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors motion-safe:active:translate-y-[1px]",
                      clickable
                        ? "border-primary/40 bg-primary/5 text-primary hover:border-primary hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                        : "cursor-not-allowed border-border-light bg-border-light/30 text-text-tertiaryLight dark:border-border-dark dark:bg-border-dark/30 dark:text-text-tertiaryDark"
                    )}
                  >
                    {citation.label}
                    {citation.deeplinkUrl ? (
                      <span className="text-[10px] font-normal text-primary/70">열기</span>
                    ) : null}
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
        {meta?.toolAttachments && meta.toolAttachments.length > 0 ? (
          <div className="mt-3 space-y-3">
            {meta.toolAttachments.map((attachment, index) => (
              <ToolWidgetRenderer key={`${id}-attachment-${index}`} attachment={attachment} />
            ))}
          </div>
        ) : null}
        {!isUser && status && (status === "error" || status === "blocked") && (
          <div className="mt-3 space-y-2 rounded-lg border border-accent-negative/40 bg-accent-negative/10 p-3 text-xs text-accent-negative">
            <p>{errorMessage}</p>
            {canRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="rounded-md border border-accent-negative/60 px-3 py-1 text-[11px] font-semibold text-accent-negative transition-colors transition-motion-fast hover:border-accent-negative hover:bg-accent-negative/20 motion-safe:active:translate-y-[1px]"
              >
                다시 시도
              </button>
            )}
          </div>
        )}
        <p
          className={classNames(
            "mt-3 text-[11px]",
            isUser ? "text-white/70" : "text-text-secondaryLight dark:text-text-secondaryDark"
          )}
        >
          {timestamp}
        </p>
      </div>
    </div>
  );
}
