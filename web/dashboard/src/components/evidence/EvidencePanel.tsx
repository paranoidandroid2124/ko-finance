"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useIntersectionObserver } from "@/hooks/useIntersectionObserver";
import { PlanLock } from "@/components/ui/PlanLock";
import type { PlanTier as PlanTierType } from "@/store/planStore";
import { InlinePdfViewer } from "./InlinePdfViewer";
import { getPlanLabel } from "@/lib/planTier";
import { EvidenceDiffTabs } from "./EvidenceDiffTabs";

export type PlanTier = PlanTierType;

export type EvidenceAnchor = {
  paragraphId?: string | null;
  pdfRect?: {
    page: number;
    x: number;
    y: number;
    width: number;
    height: number;
  } | null;
  similarity?: number | null;
};

export type EvidenceSelfCheck = {
  score?: number | null;
  verdict?: "pass" | "warn" | "fail" | null;
  explanation?: string | null;
};

export type EvidenceDocumentMeta = {
  documentId?: string | null;
  title?: string | null;
  corpName?: string | null;
  ticker?: string | null;
  receiptNo?: string | null;
  viewerUrl?: string | null;
  downloadUrl?: string | null;
  publishedAt?: string | null;
};

export type EvidenceTableCell = {
  columnIndex: number;
  headerPath: string[];
  value?: string | null;
  normalizedValue?: string | null;
  numericValue?: number | null;
  valueType?: string | null;
  confidence?: number | null;
};

export type EvidenceTableReference = {
  tableId?: string | null;
  pageNumber?: number | null;
  tableIndex?: number | null;
  title?: string | null;
  rowCount?: number | null;
  columnCount?: number | null;
  headerRows?: number | null;
  confidence?: number | null;
  columnHeaders?: string[][];
  focusRowIndex?: number | null;
  focusRowCells?: EvidenceTableCell[];
  explorerUrl?: string | null;
};

export type EvidenceItem = {
  urnId: string;
  quote: string;
  section?: string | null;
  pageNumber?: number | null;
  anchor?: EvidenceAnchor | null;
  selfCheck?: EvidenceSelfCheck | null;
  sourceReliability?: "high" | "medium" | "low" | null;
  createdAt?: string | null;
  chunkId?: string | null;
  locked?: boolean;
  lockedMessage?: string | null;
  diffType?: "created" | "updated" | "unchanged" | "removed" | null;
  diffChangedFields?: string[] | null;
  previousQuote?: string | null;
  previousSection?: string | null;
  previousPageNumber?: number | null;
  previousAnchor?: EvidenceAnchor | null;
  previousSourceReliability?: "high" | "medium" | "low" | null;
  previousSelfCheck?: EvidenceSelfCheck | null;
  documentTitle?: string | null;
  documentUrl?: string | null;
  documentDownloadUrl?: string | null;
  documentMeta?: EvidenceDocumentMeta | null;
  tableReference?: EvidenceTableReference | null;
};

export type EvidencePanelStatus = "loading" | "ready" | "empty" | "anchor-mismatch";

export type EvidencePanelProps = {
  planTier: PlanTier;
  status: EvidencePanelStatus;
  items: EvidenceItem[];
  selectedUrnId?: string;
  inlinePdfEnabled?: boolean;
  pdfUrl?: string | null;
  pdfDownloadUrl?: string | null;
  diffEnabled?: boolean;
  diffActive?: boolean;
  removedItems?: EvidenceItem[];
  onSelectEvidence?: (urnId: string) => void;
  onHoverEvidence?: (urnId: string | undefined) => void;
  onRequestOpenPdf?: (urnId: string) => void;
  onRequestUpgrade?: (tier: PlanTier) => void;
  onToggleDiff?: (nextValue: boolean) => void;
};

const RELIABILITY_TONE: Record<
  NonNullable<EvidenceItem["sourceReliability"]>,
  { badge: string; label: string }
> = {
  high: {
    badge:
      "border-emerald-400 bg-emerald-500/10 text-emerald-600 dark:border-emerald-300/40 dark:bg-emerald-500/10 dark:text-emerald-200",
    label: "신뢰도 높아요",
  },
  medium: {
    badge:
      "border-amber-400 bg-amber-500/10 text-amber-600 dark:border-amber-300/40 dark:bg-amber-500/10 dark:text-amber-100",
    label: "신뢰도 보통이에요",
  },
  low: {
    badge:
      "border-destructive/60 bg-destructive/10 text-destructive dark:border-destructive/60 dark:bg-destructive/15 dark:text-destructive",
    label: "신뢰도 낮은 편이에요",
  },
};

const VERDICT_TONE: Record<
  NonNullable<EvidenceSelfCheck["verdict"]>,
  { badge: string; label: string }
> = {
  pass: {
    badge:
      "border-emerald-400 bg-emerald-500/10 text-emerald-600 dark:border-emerald-300/40 dark:bg-emerald-500/10 dark:text-emerald-200",
    label: "셀프 체크 통과",
  },
  warn: {
    badge:
      "border-amber-400 bg-amber-500/10 text-amber-600 dark:border-amber-300/40 dark:bg-amber-500/10 dark:text-amber-100",
    label: "셀프 체크 주의",
  },
  fail: {
    badge:
      "border-destructive/60 bg-destructive/10 text-destructive dark:border-destructive/60 dark:bg-destructive/15 dark:text-destructive",
    label: "셀프 체크 다시 보기",
  },
};

const DIFF_TONE: Record<
  NonNullable<Exclude<EvidenceItem["diffType"], null | undefined>>,
  { badge: string; label: string; card: string; quote: string }
> = {
  created: {
    badge:
      "border-emerald-400 bg-emerald-500/10 text-emerald-600 dark:border-emerald-300/40 dark:bg-emerald-500/10 dark:text-emerald-200",
    label: "새로 담겼어요",
    card: "border-emerald-400/50 bg-emerald-50/40 dark:border-emerald-300/40 dark:bg-emerald-500/10",
    quote: "border-emerald-300/60 bg-emerald-500/10 text-emerald-700 dark:border-emerald-300/40 dark:text-emerald-200",
  },
  updated: {
    badge:
      "border-sky-400 bg-sky-500/10 text-sky-700 dark:border-sky-300/40 dark:bg-sky-500/10 dark:text-sky-200",
    label: "내용이 바뀌었어요",
    card: "border-sky-400/60 bg-sky-50/30 dark:border-sky-300/40 dark:bg-sky-500/10",
    quote: "border-sky-300/60 bg-sky-500/10 text-sky-700 dark:border-sky-300/40 dark:text-sky-200",
  },
  unchanged: {
    badge:
      "border-border-light bg-background-cardLight text-text-tertiaryLight dark:border-border-dark dark:bg-white/5 dark:text-text-tertiaryDark",
    label: "변화 없어요",
    card: "opacity-90",
    quote: "text-text-secondaryLight dark:text-text-secondaryDark",
  },
  removed: {
    badge:
      "border-destructive/60 bg-destructive/10 text-destructive dark:border-destructive/60 dark:bg-destructive/15 dark:text-destructive",
    label: "이젠 빠졌어요",
    card: "border-destructive/60 bg-destructive/5 dark:border-destructive/70 dark:bg-destructive/20",
    quote: "border-destructive/60 bg-destructive/10 text-destructive dark:text-destructive",
  },
};

const DIFF_FIELD_LABELS: Record<string, string> = {
  quote: "문장",
  section: "섹션",
  page_number: "페이지",
  pageNumber: "페이지",
  anchor: "하이라이트 위치",
  source_reliability: "출처 신뢰도",
  sourceReliability: "출처 신뢰도",
  self_check: "셀프 체크",
  selfCheck: "셀프 체크",
};

function formatSimilarity(anchor?: EvidenceAnchor | null) {
  if (!anchor || anchor.similarity === null || anchor.similarity === undefined) {
    return null;
  }
  return `${Math.round(anchor.similarity * 100)}% 일치`;
}

const SKELETON_ROWS = Array.from({ length: 4 });

export function EvidencePanel({
  planTier,
  status,
  items,
  selectedUrnId,
  inlinePdfEnabled = true,
  pdfUrl,
  pdfDownloadUrl,
  diffEnabled,
  diffActive,
  removedItems,
  onSelectEvidence,
  onHoverEvidence,
  onRequestOpenPdf,
  onRequestUpgrade,
  onToggleDiff,
}: EvidencePanelProps) {
  const [internalSelection, setInternalSelection] = useState<string | undefined>(items[0]?.urnId);
  const isControlled = selectedUrnId !== undefined;
  const activeUrn = isControlled ? selectedUrnId : internalSelection ?? items[0]?.urnId;

  const { observe, unobserve } = useIntersectionObserver({
    rootMargin: "-20% 0px -40% 0px",
  });

  const activeItem = useMemo(
    () => items.find((item) => item.urnId === activeUrn),
    [items, activeUrn],
  );

  const highlightRect = useMemo(() => {
    const rect = activeItem?.anchor?.pdfRect;
    if (!rect) {
      return null;
    }
    return {
      page: rect.page ?? activeItem?.pageNumber ?? 1,
      x: rect.x ?? 0,
      y: rect.y ?? 0,
      width: rect.width ?? 0,
      height: rect.height ?? 0,
    };
  }, [activeItem]);

  const pdfPage = highlightRect?.page ?? activeItem?.pageNumber ?? undefined;

  const [pdfStatus, setPdfStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [pdfErrorMessage, setPdfErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!inlinePdfEnabled || !pdfUrl || activeItem?.locked) {
      setPdfStatus("idle");
      setPdfErrorMessage(null);
      return;
    }
    setPdfStatus("loading");
    setPdfErrorMessage(null);
  }, [inlinePdfEnabled, pdfUrl, activeItem?.urnId, activeItem?.locked]);

  const handleSelect = useCallback(
    (urnId: string) => {
      onSelectEvidence?.(urnId);
      onHoverEvidence?.(undefined);
      if (!isControlled) {
        setInternalSelection(urnId);
      }
    },
    [isControlled, onSelectEvidence, onHoverEvidence],
  );

  const bindObserver = useCallback(
    (urnId: string) =>
      (element: HTMLLIElement | null) => {
        if (!element) {
          unobserve(element);
          return;
        }
        observe(element, (entry) => {
          if (!entry.isIntersecting || isControlled) {
            return;
          }
          setInternalSelection((current) => current ?? urnId);
        });
      },
    [observe, unobserve, isControlled],
  );

  const handlePdfLoad = useCallback(() => {
    setPdfStatus("ready");
    setPdfErrorMessage(null);
  }, []);

  const handlePdfError = useCallback((error: Error) => {
    setPdfStatus("error");
    setPdfErrorMessage(error.message);
  }, []);

  const renderLockedBanner = () => {
    if (!activeItem?.locked) {
      return null;
    }
    return (
      <PlanLock
        requiredTier="pro"
        currentTier={planTier}
        description={
          activeItem.lockedMessage ?? "Pro ?? ???? ?????? PDF ???? ??? ??? ? ????."
        }
        onUpgrade={onRequestUpgrade}
      />
    );
  };



  const renderPdfPane = () => {
    const inlineAllowed = inlinePdfEnabled && !!pdfUrl && !activeItem?.locked;
    const downloadLink =
      pdfDownloadUrl && (
        <a
          className="inline-flex items-center gap-1 rounded-lg border border-border-light px-3 py-2 text-xs font-semibold text-primary transition-motion-fast hover:border-primary hover:text-primary dark:border-border-dark dark:hover:border-primary"
          href={pdfDownloadUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          원문 새 창에서 보기
        </a>
      );

    if (!inlineAllowed) {
      if (activeItem?.locked) {
        return (
          <PlanLock
            requiredTier="pro"
            currentTier={planTier}
            description={
              activeItem.lockedMessage ??
              "Pro ?? ???? ??????? PDF ??? ????? ?????? ?? ??? ? ????."
            }
            onUpgrade={onRequestUpgrade}
            className="flex h-full flex-col justify-center"
          >
            {downloadLink}
          </PlanLock>
        );
      }
      return (
        <div className="flex h-full flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border-light/70 bg-background-cardLight/60 p-4 text-center text-sm text-text-secondaryLight dark:border-border-dark/60 dark:bg-background-cardDark/50 dark:text-text-secondaryDark">
          <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">PDF ????? ?? ? ? ???</p>
          <p className="text-xs leading-5">
            {pdfUrl
              ? "??? PDF ????? ???? ???. ?? ? ?? ?? ?? ??? ???."
              : "??? PDF? ?? ????. ?? ??? ?? ???? ? ???."}
          </p>
          {downloadLink}
        </div>
      );
    }

    return (

      <div className="flex h-full flex-col gap-3">
        <InlinePdfViewer
          key={`${activeItem?.urnId ?? "pdf"}-${pdfPage ?? "page"}`}
          src={pdfUrl ?? ""}
          page={pdfPage}
          highlightRect={highlightRect}
          onLoad={handlePdfLoad}
          onError={handlePdfError}
          className="flex-1"
        />
        {pdfStatus === "error" ? (
          <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-3 text-xs text-destructive dark:border-destructive/50 dark:bg-destructive/10">
            <p className="font-semibold">PDF 뷰어를 열지 못했어요.</p>
            {pdfErrorMessage ? (
              <p className="mt-1 text-[11px] text-destructive/80 dark:text-destructive/70">{pdfErrorMessage}</p>
            ) : null}
            <div className="mt-2 flex flex-wrap gap-2">{downloadLink}</div>
          </div>
        ) : (
          <div
            className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-text-secondaryLight dark:text-text-secondaryDark"
            aria-live="polite"
          >
            <span>
              {pdfStatus === "loading"
                ? "PDF.js로 문서를 불러오는 중이에요…"
                : pdfStatus === "ready"
                ? "하이라이트 영역을 누르면 문장과 PDF를 함께 살펴볼 수 있어요."
                : null}
            </span>
            {downloadLink}
          </div>
        )}
      </div>
    );
  };

  const renderAnchorMismatchBanner = () => {
    if (status !== "anchor-mismatch") {
      return null;
    }
    return (
      <div className="rounded-lg border border-amber-300/60 bg-amber-200/30 px-3 py-2 text-xs text-amber-800 dark:border-amber-300/50 dark:bg-amber-500/10 dark:text-amber-100">
        하이라이트 위치를 찾지 못했어요. 원문 열기 버튼으로 바로 확인하시거나, 필요하면 저희가 더 도와드릴게요.
      </div>
    );
  };

  const renderRemovedSection = () => {
    return <EvidenceRemovedList diffActive={diffActive} items={removedItems ?? []} />;
  };

  const renderList = () => {
    if (status === "loading") {
      return (
        <ul className="space-y-2">
          {items.map((item) => (
            <EvidenceListItem
              key={item.urnId}
              item={item}
              isActive={item.urnId === activeUrn}
              diffActive={Boolean(diffActive)}
              observerRef={bindObserver(item.urnId)}
              onSelect={handleSelect}
              onHover={onHoverEvidence}
              onRequestUpgrade={onRequestUpgrade}
            />
          ))}
        </ul>
      );
    }

    if (status === "empty" || items.length === 0) {
      return (
        <>
          <div className="rounded-lg border border-dashed border-border-light px-4 py-6 text-center text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
            아직 보여드릴 근거가 없어요. 조금 뒤 다시 확인하시거나 새 질문을 남겨 주세요.
          </div>
          {renderRemovedSection()}
        </>
      );
    }

    return (
      <>
        <ul className="space-y-2">
          {items.map((item) => {
            const isActive = item.urnId === activeUrn;
            const reliabilityTone = item.sourceReliability ? RELIABILITY_TONE[item.sourceReliability] : null;
            const verdictTone = item.selfCheck?.verdict ? VERDICT_TONE[item.selfCheck.verdict] : null;
            const diffKey = item.diffType as NonNullable<EvidenceItem["diffType"]> | undefined;
            const diffTone = diffActive && diffKey ? DIFF_TONE[diffKey] ?? null : null;
            const changedFields = Array.isArray(item.diffChangedFields) ? item.diffChangedFields : [];
            const changedSummary =
              diffActive && changedFields.length
                ? changedFields.map((field) => DIFF_FIELD_LABELS[field] ?? field).join(", ")
                : null;
            const itemClass = `group relative rounded-lg border px-3 py-3 transition-motion-medium ${
              isActive
                ? "border-primary bg-primary/5 text-text-primaryLight shadow-card dark:border-primary.dark dark:bg-primary/10 dark:text-text-primaryDark"
                : "border-border-light bg-white text-text-secondaryLight shadow-sm hover:border-primary/50 dark:border-border-dark dark:bg-white/5 dark:text-text-secondaryDark"
            }${diffTone ? ` ${diffTone.card}` : ""}`;
            const quoteClass =
              diffActive && diffTone
                ? `mt-2 whitespace-pre-line rounded-md border border-border-light/60 px-3 py-2 text-sm leading-6 ${diffTone.quote}`
                : "mt-2 whitespace-pre-line text-sm leading-6 text-text-secondaryLight dark:text-text-secondaryDark";

            return (
              <li key={item.urnId} ref={bindObserver(item.urnId)} className={itemClass}>
                {item.locked ? (
                  <div className="pointer-events-none absolute inset-0 rounded-lg border border-dashed border-border-light/90 bg-white/70 backdrop-blur-[2px] dark:border-border-dark/80 dark:bg-white/10" />
                ) : null}
                <button
                  type="button"
                  className="relative z-10 w-full text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                  onClick={() => handleSelect(item.urnId)}
                  onMouseEnter={() => onHoverEvidence?.(item.urnId)}
                  onFocus={() => onHoverEvidence?.(item.urnId)}
                  onMouseLeave={() => onHoverEvidence?.(undefined)}
                  onBlur={() => onHoverEvidence?.(undefined)}
                >
                  <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wide text-primary">
                    <span>{item.section ?? "문장"}</span>
                    {item.pageNumber ? <span>p.{item.pageNumber}</span> : null}
                  </div>
                  <p className={quoteClass}>{item.quote}</p>
                </button>

                {diffActive && item.diffType === "updated" && item.previousQuote ? (
                  <div className="relative z-10 mt-2 rounded-md border border-dashed border-border-light/70 bg-white/60 p-2 text-[11px] text-text-tertiaryLight dark:border-border-dark/60 dark:bg-white/10 dark:text-text-tertiaryDark">
                    <span className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">
                      이전 문장
                    </span>
                    <p className="mt-1 whitespace-pre-line line-through decoration-destructive/70 decoration-1">
                      {item.previousQuote}
                    </p>
                    {(item.previousSection && item.previousSection !== item.section) ||
                    (item.previousPageNumber && item.previousPageNumber !== item.pageNumber) ? (
                      <p className="mt-1 text-[10px] uppercase text-text-tertiaryLight dark:text-text-ter티aryDark">
                        위치: {item.previousSection ?? "—"} /{" "}
                        {item.previousPageNumber ? `p.${item.previousPageNumber}` : "페이지 정보 없음"}
                      </p>
                    ) : null}
                  </div>
                ) : null}

                {diffActive && item.diffType === "created" ? (
                  <p className="relative z-10 mt-2 text-[11px] font-semibold text-emerald-600 dark:text-emerald-300">
                    이번에 새로 담긴 문장이에요.
                  </p>
                ) : null}
                {diffActive && item.diffType === "unchanged" ? (
                  <p className="relative z-10 mt-2 text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                    이전 스냅샷과 같아요.
                  </p>
                ) : null}

                <div className="relative z-10 mt-3 flex flex-wrap items-center gap-2 text-[11px]">
                  {diffActive && diffTone ? (
                    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 font-semibold ${diffTone.badge}`}>
                      {diffTone.label}
                    </span>
                  ) : null}
                  {verdictTone ? (
                    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 font-semibold ${verdictTone.badge}`}>
                      {verdictTone.label}
                    </span>
                  ) : null}
                  {reliabilityTone ? (
                    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 font-semibold ${reliabilityTone.badge}`}>
                      {reliabilityTone.label}
                    </span>
                  ) : null}
                  {formatSimilarity(item.anchor) ? (
                    <span className="rounded-md border border-border-light px-2 py-0.5 font-semibold text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
                      {formatSimilarity(item.anchor)}
                    </span>
                  ) : null}
                  {item.chunkId ? (
                    <span className="rounded-md border border-border-light px-2 py-0.5 text-[10px] text-text-tertiaryLight dark:border-border-dark dark:text-text-tertiaryDark">
                      #{item.chunkId}
                    </span>
                  ) : null}
                </div>

                {diffActive && changedSummary ? (
                  <p className="relative z-10 mt-2 text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                    달라진 부분: {changedSummary}
                  </p>
                ) : null}

                {item.locked && onRequestUpgrade ? (
                  <div className="relative z-10 mt-3 flex flex-wrap items-center justify-between gap-2 rounded-md border border-dashed border-border-light/70 bg-white/60 px-3 py-2 text-[11px] dark:border-border-dark/60 dark:bg-white/10">
                    <span className="text-text-secondaryLight dark:text-text-secondaryDark">
                      이 하이라이트는 Pro 이상 플랜에서 확인하실 수 있어요.
                    </span>
                    <button
                      type="button"
                      className="rounded-md border border-primary/60 px-2 py-1 text-[11px] font-semibold text-primary transition-motion-fast hover:bg-primary/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                      onClick={() => onRequestUpgrade?.("pro")}
                    >
                      팀과 상담하기
                    </button>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
        {renderRemovedSection()}
      </>
    );
  };

  return (
    <section className="grid h-full gap-4 rounded-xl border border-border-light bg-white/80 p-4 shadow-card transition-colors transition-motion-medium dark:border-border-dark dark:bg-background-cardDark/80">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase text-primary">근거 노트</p>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            {status === "loading"
              ? "근거를 차분히 모으는 중이에요…"
              : status === "empty"
              ? "아직 보여드릴 근거가 없어요."
              : status === "anchor-mismatch"
              ? "하이라이트 위치를 찾지 못했어요. 원문을 바로 열어 확인해 주세요."
              : "챗봇이 참고한 문장을 함께 살펴봐요."}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
          <span className="rounded-md border border-border-light px-2 py-1 font-semibold uppercase dark:border-border-dark">
            {getPlanLabel(planTier)}
          </span>
          <EvidenceDiffTabs
            diffEnabled={diffEnabled}
            diffActive={diffActive}
            removedCount={removedItems?.length}
            onToggleDiff={onToggleDiff}
          />
          {activeItem && onRequestOpenPdf ? (
            <button
              type="button"
              className="rounded-md border border-border-light px-2 py-1 font-semibold text-text-secondaryLight transition-motion-fast hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary"
              onClick={() => onRequestOpenPdf(activeItem.urnId)}
            >
              원문 새 창에서 보기
            </button>
          ) : null}
        </div>
      </header>

      {renderAnchorMismatchBanner()}

      <div className="grid gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-3">{renderList()}</div>
        <div className="flex flex-col gap-3">
          {renderLockedBanner()}
          {renderPdfPane()}
        </div>
      </div>
    </section>
  );
}

export type { EvidenceItem as EvidencePanelItem };

type EvidenceListItemProps = {
  item: EvidenceItem;
  isActive: boolean;
  diffActive: boolean;
  observerRef: (element: HTMLLIElement | null) => void;
  onSelect: (urnId: string) => void;
  onHover?: (urnId: string | undefined) => void;
  onRequestUpgrade?: (tier: PlanTier) => void;
};

function EvidenceListItem({
  item,
  isActive,
  diffActive,
  observerRef,
  onSelect,
  onHover,
  onRequestUpgrade,
}: EvidenceListItemProps) {
  const reliabilityTone = item.sourceReliability ? RELIABILITY_TONE[item.sourceReliability] : null;
  const verdictTone = item.selfCheck?.verdict ? VERDICT_TONE[item.selfCheck.verdict] : null;
  const diffKey = item.diffType as NonNullable<EvidenceItem["diffType"]> | undefined;
  const diffTone = diffActive && diffKey ? DIFF_TONE[diffKey] ?? null : null;
  const changedFields = Array.isArray(item.diffChangedFields) ? item.diffChangedFields : [];
  const changedSummary =
    diffActive && changedFields.length
      ? changedFields.map((field) => DIFF_FIELD_LABELS[field] ?? field).join(", ")
      : null;
  const itemClass = `group relative rounded-lg border px-3 py-3 transition-motion-medium ${
    isActive
      ? "border-primary bg-primary/5 text-text-primaryLight shadow-card dark:border-primary.dark dark:bg-primary/10 dark:text-text-primaryDark"
      : "border-border-light bg-white text-text-secondaryLight shadow-sm hover:border-primary/50 dark:border-border-dark dark:bg-white/5 dark:text-text-secondaryDark"
  }${diffTone ? ` ${diffTone.card}` : ""}`;
  const quoteClass =
    diffActive && diffTone
      ? `mt-2 whitespace-pre-line rounded-md border border-border-light/60 px-3 py-2 text-sm leading-6 ${diffTone.quote}`
      : "mt-2 whitespace-pre-line text-sm leading-6 text-text-secondaryLight dark:text-text-secondaryDark";

  const handleMouseLeave = () => onHover?.(undefined);
  const handleMouseEnter = () => onHover?.(item.urnId);

  return (
    <li ref={observerRef} className={itemClass}>
      {item.locked ? (
        <div className="pointer-events-none absolute inset-0 rounded-lg border border-dashed border-border-light/90 bg-white/70 backdrop-blur-[2px] dark:border-border-dark/80 dark:bg-white/10" />
      ) : null}
      <button
        type="button"
        className="relative z-10 w-full text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        onClick={() => onSelect(item.urnId)}
        onMouseEnter={handleMouseEnter}
        onFocus={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onBlur={handleMouseLeave}
      >
        <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wide text-primary">
          <span>{item.section ?? "문장"}</span>
          {item.pageNumber ? <span>p.{item.pageNumber}</span> : null}
        </div>
        <p className={quoteClass}>{item.quote}</p>
      </button>

      {diffActive && item.diffType === "updated" && item.previousQuote ? (
        <div className="relative z-10 mt-2 rounded-md border border-dashed border-border-light/70 bg-white/60 p-2 text-[11px] text-text-tertiaryLight dark:border-border-dark/60 dark:bg-white/10 dark:text-text-ter티aryDark">
          <span className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">이전 문장</span>
          <p className="mt-1 whitespace-pre-line line-through decoration-destructive/70 decoration-1">{item.previousQuote}</p>
          {(item.previousSection && item.previousSection !== item.section) ||
          (item.previousPageNumber && item.previousPageNumber !== item.pageNumber) ? (
            <p className="mt-1 text-[10px] uppercase text-text-tertiaryLight dark:text-text-ter티aryDark">
              위치: {item.previousSection ?? "—"} / {item.previousPageNumber ? `p.${item.previousPageNumber}` : "페이지 정보 없음"}
            </p>
          ) : null}
        </div>
      ) : null}

      {diffActive && item.diffType === "created" ? (
        <p className="relative z-10 mt-2 text-[11px] font-semibold text-emerald-600 dark:text-emerald-300">이번에 새로 담긴 문장이에요.</p>
      ) : null}
      {diffActive && item.diffType === "unchanged" ? (
        <p className="relative z-10 mt-2 text-[11px] text-text-ter티aryLight dark:text-text-ter티aryDark">이전 스냅샷과 같아요.</p>
      ) : null}

      <div className="relative z-10 mt-3 flex flex-wrap items-center gap-2 text-[11px]">
        {diffActive && diffTone ? (
          <span className={`inline-flex items-center rounded-md border px-2 py-0.5 font-semibold ${diffTone.badge}`}>{diffTone.label}</span>
        ) : null}
        {verdictTone ? (
          <span className={`inline-flex items-center rounded-md border px-2 py-0.5 font-semibold ${verdictTone.badge}`}>{verdictTone.label}</span>
        ) : null}
        {reliabilityTone ? (
          <span className={`inline-flex items-center rounded-md border px-2 py-0.5 font-semibold ${reliabilityTone.badge}`}>{reliabilityTone.label}</span>
        ) : null}
        {formatSimilarity(item.anchor) ? (
          <span className="rounded-md border border-border-light px-2 py-0.5 font-semibold text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
            {formatSimilarity(item.anchor)}
          </span>
        ) : null}
        {item.chunkId ? (
          <span className="rounded-md border border-border-light px-2 py-0.5 text-[10px] text-text-tertiaryLight dark:border-border-dark dark:text-text-ter티aryDark">
            #{item.chunkId}
          </span>
        ) : null}
      </div>

      {diffActive && changedSummary ? (
        <p className="relative z-10 mt-2 text-[11px] text-text-ter티aryLight dark:text-text-ter티aryDark">달라진 부분: {changedSummary}</p>
      ) : null}

      {item.locked && onRequestUpgrade ? (
        <div className="relative z-10 mt-3 flex flex-wrap items-center justify-between gap-2 rounded-md border border-dashed border-border-light/70 bg-white/60 px-3 py-2 text-[11px] dark:border-border-dark/60 dark:bg-white/10">
          <span className="text-text-secondaryLight dark:text-text-secondaryDark">이 하이라이트는 Pro 이상 플랜에서 확인하실 수 있어요.</span>
          <button
            type="button"
            className="rounded-md border border-primary/60 px-2 py-1 text-[11px] font-semibold text-primary transition-motion-fast hover:bg-primary/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            onClick={() => onRequestUpgrade?.("pro")}
          >
            플랜 상담하기
          </button>
        </div>
      ) : null}
    </li>
  );
}

type EvidenceRemovedListProps = {
  diffActive?: boolean;
  items: EvidenceItem[];
};

function EvidenceRemovedList({ diffActive, items }: EvidenceRemovedListProps) {
  if (!diffActive || items.length === 0) {
    return null;
  }
  return (
    <div className="rounded-lg border border-dashed border-border-light/70 bg-white/60 px-3 py-3 text-xs text-text-secondaryLight dark:border-border-dark/60 dark:bg-white/10 dark:text-text-secondaryDark">
      <p className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">이전 버전에서 빠진 문장 {items.length}개</p>
      <ul className="mt-2 space-y-1">
        {items.map((entry) => (
          <li key={`removed-${entry.urnId}`} className="leading-5">
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">{entry.section ?? "문장"}</span>
              {entry.pageNumber ? (
                <span className="text-[10px] uppercase text-text-tertiaryLight dark:text-text-ter티aryDark">p.{entry.pageNumber}</span>
              ) : null}
            </div>
            {entry.quote ? <p className="mt-1 text-[11px] text-text-ter티aryLight dark:text-text-ter티aryDark">{entry.quote}</p> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}


