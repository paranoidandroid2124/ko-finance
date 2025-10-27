"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useIntersectionObserver } from "@/hooks/useIntersectionObserver";
import { InlinePdfViewer } from "./InlinePdfViewer";

export type PlanTier = "free" | "pro" | "enterprise";

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
  onSelectEvidence?: (urnId: string) => void;
  onRequestOpenPdf?: (urnId: string) => void;
  onRequestUpgrade?: () => void;
  onToggleDiff?: (nextValue: boolean) => void;
};

const PLAN_LABEL: Record<PlanTier, string> = {
  free: "Free",
  pro: "Pro",
  enterprise: "Enterprise",
};

const RELIABILITY_TONE: Record<
  NonNullable<EvidenceItem["sourceReliability"]>,
  { badge: string; label: string }
> = {
  high: {
    badge:
      "border-emerald-400 bg-emerald-500/10 text-emerald-600 dark:border-emerald-300/40 dark:bg-emerald-500/10 dark:text-emerald-200",
    label: "신뢰도 높음",
  },
  medium: {
    badge:
      "border-amber-400 bg-amber-500/10 text-amber-600 dark:border-amber-300/40 dark:bg-amber-500/10 dark:text-amber-100",
    label: "신뢰도 보통",
  },
  low: {
    badge:
      "border-destructive/60 bg-destructive/10 text-destructive dark:border-destructive/60 dark:bg-destructive/15 dark:text-destructive",
    label: "신뢰도 낮음",
  },
};

const VERDICT_TONE: Record<
  NonNullable<EvidenceSelfCheck["verdict"]>,
  { badge: string; label: string }
> = {
  pass: {
    badge:
      "border-emerald-400 bg-emerald-500/10 text-emerald-600 dark:border-emerald-300/40 dark:bg-emerald-500/10 dark:text-emerald-200",
    label: "Self-check 통과",
  },
  warn: {
    badge:
      "border-amber-400 bg-amber-500/10 text-amber-600 dark:border-amber-300/40 dark:bg-amber-500/10 dark:text-amber-100",
    label: "Self-check 주의",
  },
  fail: {
    badge:
      "border-destructive/60 bg-destructive/10 text-destructive dark:border-destructive/60 dark:bg-destructive/15 dark:text-destructive",
    label: "Self-check 실패",
  },
};

function formatSimilarity(anchor?: EvidenceAnchor | null) {
  if (!anchor || anchor.similarity === null || anchor.similarity === undefined) {
    return null;
  }
  return `${Math.round(anchor.similarity * 100)}% 매칭`;
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
  onSelectEvidence,
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
      if (!isControlled) {
        setInternalSelection(urnId);
      }
    },
    [isControlled, onSelectEvidence],
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
      <div className="flex flex-col gap-3 rounded-lg border border-dashed border-border-light/80 bg-white/80 p-4 text-xs text-text-secondaryLight dark:border-border-dark/70 dark:bg-white/10 dark:text-text-secondaryDark">
        <div>
          <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
            상위 플랜 전용 근거
          </p>
          <p className="mt-1 text-text-secondaryLight dark:text-text-secondaryDark">
            {activeItem.lockedMessage ??
              "Pro 이상 요금제에서 근거 하이라이트와 PDF 미리보기를 이용할 수 있어요."}
          </p>
        </div>
        <button
          type="button"
          className="inline-flex w-fit items-center gap-2 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-white transition-motion-fast hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          onClick={onRequestUpgrade}
        >
          업그레이드 안내 받기
        </button>
      </div>
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
          PDF 새 창에서 열기
        </a>
      );

    if (!inlineAllowed) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border-light/70 bg-background-cardLight/60 p-4 text-center text-sm text-text-secondaryLight dark:border-border-dark/60 dark:bg-background-cardDark/50 dark:text-text-secondaryDark">
          <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">PDF 미리보기 미지원</p>
          <p className="text-xs leading-5">
            {activeItem?.locked
              ? "상위 플랜에서 해당 근거의 PDF 하이라이트를 확인할 수 있어요."
              : pdfUrl
              ? "이 뷰에서는 PDF.js 미리보기가 비활성화되어 있습니다. 새 창에서 원문을 열어 확인해 주세요."
              : "연결된 PDF 리소스를 찾지 못했습니다. 다운로드 링크를 통해 문서를 확인해 주세요."}
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
            <p className="font-semibold">PDF 뷰어를 불러오지 못했습니다.</p>
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
                ? "PDF.js로 문서를 불러오는 중입니다…"
                : pdfStatus === "ready"
                ? "하이라이트 영역을 클릭해 문단과 PDF를 동시에 검토할 수 있습니다."
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
        하이라이트 좌표를 찾지 못했습니다. PDF 뷰어에서 직접 검색하거나 다운로드 링크를 이용해 주세요.
      </div>
    );
  };

  const renderList = () => {
    if (status === "loading") {
      return (
        <ul className="space-y-2">
          {SKELETON_ROWS.map((_, index) => (
            <li
              key={`skeleton-${index}`}
              className="animate-pulse rounded-lg border border-border-light/60 bg-background-cardLight px-3 py-4 dark:border-border-dark/60 dark:bg-background-cardDark"
            >
              <div className="h-3 w-20 rounded bg-border-light/70 dark:bg-border-dark/40" />
              <div className="mt-2 h-3 w-full rounded bg-border-light/60 dark:bg-border-dark/30" />
              <div className="mt-2 h-3 w-2/3 rounded bg-border-light/50 dark:bg-border-dark/30" />
            </li>
          ))}
        </ul>
      );
    }

    if (status === "empty" || items.length === 0) {
      return (
        <div className="rounded-lg border border-dashed border-border-light px-4 py-6 text-center text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
          아직 표시할 근거가 없습니다. 질문을 보낸 뒤 다시 확인해 주세요.
        </div>
      );
    }

    return (
      <ul className="space-y-2">
        {items.map((item) => {
          const isActive = item.urnId === activeUrn;
          const reliabilityTone = item.sourceReliability ? RELIABILITY_TONE[item.sourceReliability] : null;
          const verdictTone = item.selfCheck?.verdict ? VERDICT_TONE[item.selfCheck.verdict] : null;

          return (
            <li
              key={item.urnId}
              ref={bindObserver(item.urnId)}
              className={`group relative rounded-lg border px-3 py-3 transition-motion-medium ${
                isActive
                  ? "border-primary bg-primary/5 text-text-primaryLight shadow-card dark:border-primary.dark dark:bg-primary/10 dark:text-text-primaryDark"
                  : "border-border-light bg-white text-text-secondaryLight shadow-sm hover:border-primary/50 dark:border-border-dark dark:bg-white/5 dark:text-text-secondaryDark"
              }`}
            >
              {item.locked ? (
                <div className="pointer-events-none absolute inset-0 rounded-lg border border-dashed border-border-light/90 bg-white/70 backdrop-blur-[2px] dark:border-border-dark/80 dark:bg-white/10" />
              ) : null}
              <button
                type="button"
                className="relative z-10 w-full text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                onClick={() => handleSelect(item.urnId)}
              >
                <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wide text-primary">
                  <span>{item.section ?? "문단"}</span>
                  {item.pageNumber ? <span>p.{item.pageNumber}</span> : null}
                </div>
                <p className="mt-2 whitespace-pre-line text-sm leading-6 text-text-secondaryLight dark:text-text-secondaryDark">
                  {item.quote}
                </p>
              </button>

              <div className="relative z-10 mt-3 flex flex-wrap items-center gap-2 text-[11px]">
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

              {item.locked && onRequestUpgrade ? (
                <div className="relative z-10 mt-3 flex flex-wrap items-center justify-between gap-2 rounded-md border border-dashed border-border-light/70 bg-white/60 px-3 py-2 text-[11px] dark:border-border-dark/60 dark:bg-white/10">
                  <span className="text-text-secondaryLight dark:text-text-secondaryDark">
                    상위 플랜에서 하이라이트를 확인할 수 있어요.
                  </span>
                  <button
                    type="button"
                    className="rounded-md border border-primary/60 px-2 py-1 text-[11px] font-semibold text-primary transition-motion-fast hover:bg-primary/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                    onClick={onRequestUpgrade}
                  >
                    업그레이드
                  </button>
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    );
  };

  return (
    <section className="grid h-full gap-4 rounded-xl border border-border-light bg-white/80 p-4 shadow-card transition-colors transition-motion-medium dark:border-border-dark dark:bg-background-cardDark/80">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase text-primary">Evidence Panel</p>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            {status === "loading"
              ? "근거를 불러오는 중입니다…"
              : status === "empty"
              ? "표시할 근거가 없습니다."
              : status === "anchor-mismatch"
              ? "하이라이트 정보를 찾지 못했습니다."
              : "답변에 인용된 근거를 검토해 주세요."}
          </p>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
          <span className="rounded-md border border-border-light px-2 py-1 font-semibold uppercase dark:border-border-dark">
            {PLAN_LABEL[planTier]}
          </span>
          {diffEnabled ? (
            <button
              type="button"
              className={`rounded-md border px-2 py-1 font-semibold transition-motion-fast ${
                diffActive
                  ? "border-primary bg-primary/10 text-primary hover:bg-primary/15"
                  : "border-border-light text-text-secondaryLight hover:border-primary/60 hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary"
              }`}
              onClick={() => onToggleDiff?.(!diffActive)}
            >
              증거 비교
            </button>
          ) : null}
          {activeItem && onRequestOpenPdf ? (
            <button
              type="button"
              className="rounded-md border border-border-light px-2 py-1 font-semibold text-text-secondaryLight transition-motion-fast hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary"
              onClick={() => onRequestOpenPdf(activeItem.urnId)}
            >
              PDF 새 창
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
