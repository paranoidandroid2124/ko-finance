"use client";

import { InlinePdfViewer } from "./InlinePdfViewer";
import { PlanLockCTA } from "./PlanLockCTA";
import type { EvidenceItem, EvidencePdfStatus, PlanTier } from "./types";

type HighlightRect = {
  page: number;
  x: number;
  y: number;
  width: number;
  height: number;
};

type EvidencePdfPanelProps = {
  planTier: PlanTier;
  activeItem?: EvidenceItem;
  inlinePdfEnabled: boolean;
  pdfUrl?: string | null;
  pdfDownloadUrl?: string | null;
  pdfStatus: EvidencePdfStatus;
  pdfError: string | null;
  pdfPage?: number;
  highlightRect?: HighlightRect | null;
  onRequestUpgrade?: (tier: PlanTier) => void;
  onRequestOpenPdf?: (urnId: string) => void;
};

export function EvidencePdfPanel({
  planTier,
  activeItem,
  inlinePdfEnabled,
  pdfUrl,
  pdfDownloadUrl,
  pdfStatus,
  pdfError,
  pdfPage,
  highlightRect,
  onRequestUpgrade,
  onRequestOpenPdf,
}: EvidencePdfPanelProps) {
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
        <PlanLockCTA
          currentTier={planTier}
          description={
            activeItem.lockedMessage ?? "Pro 이상의 플랜에서 PDF 전체를 열람하고 하이라이트를 확인할 수 있어요."
          }
          onUpgrade={onRequestUpgrade}
          className="flex h-full flex-col justify-center"
        >
          {downloadLink}
        </PlanLockCTA>
      );
    }
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border-light/70 bg-background-cardLight/60 p-4 text-center text-sm text-text-secondaryLight dark:border-border-dark/60 dark:bg-background-cardDark/50 dark:text-text-secondaryDark">
        <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">PDF 뷰어를 열지 못했어요.</p>
        <p className="text-xs leading-5">
          {pdfUrl
            ? "PDF 링크는 준비됐지만 하이라이트 위치를 찾지 못했어요. 하단 링크로 원문을 직접 확인해 주세요."
            : "PDF 링크가 아직 제공되지 않았습니다. 다른 하이라이트나 문서를 선택해 보세요."}
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
        highlightRect={highlightRect ?? undefined}
        className="flex-1"
      />
      {pdfStatus === "error" ? (
        <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-3 text-xs text-destructive dark:border-destructive/50 dark:bg-destructive/10">
          <p className="font-semibold">PDF 뷰어를 열지 못했어요.</p>
          {pdfError ? <p className="mt-1 text-[11px] text-destructive/80 dark:text-destructive/70">{pdfError}</p> : null}
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
      {activeItem && onRequestOpenPdf ? (
        <button
          type="button"
          className="rounded-md border border-border-light px-2 py-1 text-[11px] font-semibold text-text-secondaryLight transition-motion-fast hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary"
          onClick={() => onRequestOpenPdf(activeItem.urnId)}
        >
          원문 새 창에서 보기
        </button>
      ) : null}
    </div>
  );
}
