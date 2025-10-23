"use client";

import { useMemo } from "react";

export type PdfHighlightRange = {
  id: string;
  page: number;
  yStartPct: number;
  yEndPct: number;
  xStartPct?: number;
  xEndPct?: number;
  summary?: string;
  evidenceId?: string;
};

type PdfHighlightMockProps = {
  documentTitle?: string;
  pdfUrl?: string;
  highlightRanges: PdfHighlightRange[];
  activeRangeId?: string;
  status: "idle" | "loading" | "ready" | "error";
  onFocusHighlight?: (evidenceId: string) => void;
};

const STATUS_LABEL: Record<PdfHighlightMockProps["status"], string> = {
  idle: "표시할 하이라이트가 없습니다.",
  loading: "PDF 하이라이트를 불러오는 중입니다.",
  ready: "하이라이트가 준비되었습니다.",
  error: "PDF 하이라이트를 불러오지 못했습니다."
};


const clampPercent = (value: number) => Math.min(100, Math.max(0, value));

function deriveHighlightId(range: PdfHighlightRange) {
  return range.id ?? range.evidenceId ?? "";
}

export function PdfHighlightMock({
  documentTitle,
  pdfUrl,
  highlightRanges,
  activeRangeId,
  status,
  onFocusHighlight
}: PdfHighlightMockProps) {
  const groupedPages = useMemo(() => {
    const pageMap = new Map<
      number,
      Array<PdfHighlightRange & { heightPct: number; topPct: number; leftPct: number; widthPct: number }>
    >();

    highlightRanges.forEach((range) => {
      const topPct = clampPercent(range.yStartPct);
      const heightPct = clampPercent(range.yEndPct) - topPct;
      const safeHeight = heightPct <= 0 ? 6 : heightPct;
      const leftPct = clampPercent(typeof range.xStartPct === 'number' ? range.xStartPct : 8);
      const rightPct = clampPercent(typeof range.xEndPct === 'number' ? range.xEndPct : 92);
      const rawWidth = Math.max(0, rightPct - leftPct);
      const widthPct = Math.max(4, Math.min(100 - leftPct, rawWidth));
      const entry = pageMap.get(range.page) ?? [];
      entry.push({
        ...range,
        topPct,
        heightPct: safeHeight,
        leftPct,
        widthPct
      });
      pageMap.set(range.page, entry);
    });

    return Array.from(pageMap.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([page, ranges]) => ({
        page,
        ranges: ranges.sort((a, b) => a.topPct - b.topPct)
      }));
  }, [highlightRanges]);

  const showSkeleton = status === "loading";
  const showError = status === "error";
  const isEmpty = (status === "idle" || status === "ready") && highlightRanges.length === 0;
  const showPdfPreview = Boolean(pdfUrl);

  const handleOpenPdf = () => {
    if (!pdfUrl) {
      return;
    }
    window.open(pdfUrl, "_blank", "noopener,noreferrer");
  };

  const handleFocus = (range: PdfHighlightRange) => {
    if (!onFocusHighlight) return;
    const focusId = range.evidenceId ?? deriveHighlightId(range);
    if (focusId) {
      onFocusHighlight(focusId);
    }
  };

  return (
    <section className="space-y-3 rounded-xl border border-border-light bg-white/70 p-3 text-xs shadow-sm transition-colors dark:border-border-dark dark:bg-white/5">
      <header className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase text-primary">PDF 하이라이트</p>
          <p className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">{STATUS_LABEL[status]}</p>
        </div>
        <button
          type="button"
          className="rounded-md border border-border-light px-3 py-1 text-[11px] font-semibold text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark disabled:cursor-not-allowed disabled:opacity-60"
          disabled={!pdfUrl}
          onClick={handleOpenPdf}
          title={pdfUrl ? "새 창에서 PDF 열기" : "연결된 PDF가 없습니다."}
        >
          PDF 열기
        </button>
      </header>

      {documentTitle ? (
        <p className="rounded-lg border border-border-light/70 bg-white/60 px-3 py-2 text-[11px] font-medium text-text-secondaryLight dark:border-border-dark/70 dark:bg-white/10 dark:text-text-secondaryDark">
          {documentTitle}
        </p>
      ) : null}

      {showPdfPreview ? (
        <div className="overflow-hidden rounded-lg border border-border-light/70 dark:border-border-dark/60">
          <iframe
            src={`${pdfUrl}#toolbar=0&navpanes=0&view=FitH`}
            title="PDF 미리보기"
            className="h-80 w-full bg-white"
          />
        </div>
      ) : null}

      {showSkeleton ? (
        <div className="space-y-3">
          {Array.from({ length: 2 }).map((_, index) => (
            <div
              key={`pdf-skeleton-${index}`}
              className="animate-pulse rounded-lg border border-border-light/70 bg-background-cardLight p-4 dark:border-border-dark/60 dark:bg-background-cardDark"
            >
              <div className="h-4 w-24 rounded bg-border-light/70 dark:bg-border-dark/40" />
              <div className="mt-3 h-48 rounded bg-border-light/40 dark:bg-border-dark/30" />
            </div>
          ))}
        </div>
      ) : null}

      {showError ? (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-4 text-text-secondaryLight dark:border-destructive/50 dark:bg-destructive/10 dark:text-text-secondaryDark">
          PDF 하이라이트를 가져오는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.
        </div>
      ) : null}

      {isEmpty ? (
        <div className="rounded-lg border border-dashed border-border-light px-3 py-6 text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
          표시할 PDF 하이라이트가 없습니다. 근거 문서를 선택하거나 다른 질문을 시도해 보세요.
        </div>
      ) : null}

      {status === "ready" && !isEmpty ? (
        <div className="space-y-4">
          {groupedPages.map((pageEntry) => (
            <article key={`pdf-page-${pageEntry.page}`} className="space-y-2">
              <div className="flex items-center justify-between text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
                <span className="font-semibold">페이지 {pageEntry.page}</span>
                {pdfUrl ? <span className="text-text-tertiaryLight dark:text-text-tertiaryDark">원문 미리보기</span> : null}
              </div>
              <div className="relative h-64 w-full overflow-hidden rounded-lg border border-border-light bg-gradient-to-b from-white to-border-light/40 dark:border-border-dark dark:from-background-cardDark dark:to-border-dark/30">
                {pageEntry.ranges.map((range) => {
                  const derivedId = deriveHighlightId(range);
                  const isActive = activeRangeId ? derivedId === activeRangeId : false;
                  return (
                    <button
                      key={derivedId}
                      type="button"
                      className={`absolute rounded-md border px-3 py-2 text-left text-[11px] shadow transition-all ${
                        isActive
                          ? "border-primary bg-primary/20 text-primary"
                          : "border-primary/40 bg-primary/10 text-text-secondaryLight hover:border-primary hover:bg-primary/20 hover:text-primary dark:text-text-secondaryDark"
                      }`}
                      style={{
                        top: `${range.topPct}%`,
                        height: `${range.heightPct}%`,
                        left: `${range.leftPct ?? 8}%`,
                        width: `${range.widthPct ?? 84}%`
                      }}
                      onClick={() => handleFocus(range)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          handleFocus(range);
                        }
                      }}
                      aria-label={`${range.summary ?? "하이라이트"} 하이라이트 영역`}
                      aria-pressed={isActive}
                    >
                      <span className="font-semibold">{range.summary ?? "하이라이트"}</span>
                      <span className="mt-1 block text-[10px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                        {Math.round(range.topPct)}% 위치
                      </span>
                    </button>
                  );
                })}
              </div>
              <ul className="space-y-1 text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
                {pageEntry.ranges.map((range) => {
                  const derivedId = deriveHighlightId(range);
                  const isActive = activeRangeId ? derivedId === activeRangeId : false;
                  return (
                    <li key={`summary-${derivedId}`}>
                      <button
                        type="button"
                        className={`w-full text-left underline-offset-2 ${
                          isActive ? "text-primary underline" : "text-text-secondaryLight hover:text-primary hover:underline dark:text-text-secondaryDark"
                        }`}
                        onClick={() => handleFocus(range)}
                      >
                        {range.summary ?? "하이라이트"} (위치 {Math.round(range.topPct)}%)
                      </button>
                    </li>
                  );
                })}
              </ul>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}

