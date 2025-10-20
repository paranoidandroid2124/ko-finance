"use client";

import { useMemo } from "react";

export type PdfHighlightRange = {
  id: string;
  page: number;
  yStartPct: number;
  yEndPct: number;
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
  idle: "표시할 하이라이트가 아직 없습니다.",
  loading: "PDF를 준비하는 중입니다.",
  ready: "하이라이트가 준비되었습니다.",
  error: "PDF를 로드하지 못했습니다."
};

const clampPercent = (value: number) => Math.min(100, Math.max(0, value));

function deriveHighlightId(range: PdfHighlightRange) {
  return range.id ?? range.evidenceId ?? "";
}

export function render_pdf_highlight({
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
      Array<PdfHighlightRange & { heightPct: number; topPct: number }>
    >();

    highlightRanges.forEach((range) => {
      const topPct = clampPercent(range.yStartPct);
      const heightPct = clampPercent(range.yEndPct) - topPct;
      const safeHeight = heightPct <= 0 ? 6 : heightPct;
      const entry = pageMap.get(range.page) ?? [];
      entry.push({
        ...range,
        topPct,
        heightPct: safeHeight
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
          className="rounded-md border border-border-light px-3 py-1 text-[11px] font-semibold text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
          disabled
          title="실제 PDF 열기 기능은 준비 중입니다."
        >
          실제 PDF 열기
        </button>
      </header>

      {documentTitle ? (
        <p className="rounded-lg border border-border-light/70 bg-white/60 px-3 py-2 text-[11px] font-medium text-text-secondaryLight dark:border-border-dark/70 dark:bg-white/10 dark:text-text-secondaryDark">
          {documentTitle}
        </p>
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
          guardrail이 활성화되었거나 PDF 소스가 준비되지 않았습니다. 잠시 후 다시 시도해주세요.
        </div>
      ) : null}

      {isEmpty ? (
        <div className="rounded-lg border border-dashed border-border-light px-3 py-6 text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
          선택된 근거에 연결된 하이라이트가 없습니다. 근거 패널에서 다른 항목을 선택해 보세요.
        </div>
      ) : null}

      {status === "ready" && !isEmpty ? (
        <div className="space-y-4">
          {groupedPages.map((pageEntry) => (
            <article key={`pdf-page-${pageEntry.page}`} className="space-y-2">
              <div className="flex items-center justify-between text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
                <span className="font-semibold">페이지 {pageEntry.page}</span>
                {pdfUrl ? <span className="text-text-tertiaryLight dark:text-text-tertiaryDark">모의 미리보기</span> : null}
              </div>
              <div className="relative h-64 w-full overflow-hidden rounded-lg border border-border-light bg-gradient-to-b from-white to-border-light/40 dark:border-border-dark dark:from-background-cardDark dark:to-border-dark/30">
                {pageEntry.ranges.map((range) => {
                  const derivedId = deriveHighlightId(range);
                  const isActive = activeRangeId ? derivedId === activeRangeId : false;
                  return (
                    <button
                      key={derivedId}
                      type="button"
                      className={`absolute left-[8%] right-[8%] rounded-md border px-3 py-2 text-left text-[11px] shadow transition-all ${
                        isActive
                          ? "border-primary bg-primary/20 text-primary"
                          : "border-primary/40 bg-primary/10 text-text-secondaryLight hover:border-primary hover:bg-primary/20 hover:text-primary dark:text-text-secondaryDark"
                      }`}
                      style={{ top: `${range.topPct}%`, height: `${range.heightPct}%` }}
                      onClick={() => handleFocus(range)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          handleFocus(range);
                        }
                      }}
                      aria-label={`${range.summary ?? "요약 없음"} 하이라이트 선택`}
                      aria-pressed={isActive}
                    >
                      <span className="font-semibold">{range.summary ?? "요약 없음"}</span>
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
                        {range.summary ?? "요약 없음"} (위치 {Math.round(range.topPct)}%)
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

export const PdfHighlightMock = render_pdf_highlight;
