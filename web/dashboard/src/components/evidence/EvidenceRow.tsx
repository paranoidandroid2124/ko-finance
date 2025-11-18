"use client";

import { PlanLockCTA } from "./PlanLockCTA";
import { SelfCheckBadge } from "./SelfCheckBadge";
import { RELIABILITY_TONE, DIFF_TONE, DIFF_FIELD_LABELS } from "./constants";
import { formatSimilarity } from "./utils";
import type { EvidenceItem, EvidenceListItemProps } from "./types";

type DiffVisual = (typeof DIFF_TONE)[keyof typeof DIFF_TONE] | null;

export function EvidenceRow({
  item,
  isActive,
  diffActive,
  observerRef,
  onSelect,
  onHover,
  onRequestUpgrade,
  planTier,
}: EvidenceListItemProps) {
  const diffTone = diffActive && item.diffType ? DIFF_TONE[item.diffType] ?? null : null;
  const itemClass = buildItemClass(isActive, diffTone);
  const quoteClass = buildQuoteClass(diffActive, diffTone);

  const handleMouseEnter = () => onHover?.(item.urnId);
  const handleMouseLeave = () => onHover?.(undefined);

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

      {renderDiffDetails(item, diffActive)}

      <div className="relative z-10 mt-3 flex flex-wrap items-center gap-2 text-[11px]">
        {diffActive && diffTone ? (
          <span className={`inline-flex items-center rounded-md border px-2 py-0.5 font-semibold ${diffTone.badge}`}>
            {diffTone.label}
          </span>
        ) : null}
        <SelfCheckBadge value={item.selfCheck} />
        {renderReliabilityBadge(item)}
        {renderSimilarityBadge(item)}
        {item.chunkId ? (
          <span className="rounded-md border border-border-light px-2 py-0.5 text-[10px] text-text-tertiaryLight dark:border-border-dark dark:text-text-tertiaryDark">
            #{item.chunkId}
          </span>
        ) : null}
      </div>

      {diffActive ? renderChangedSummary(item) : null}

      {item.locked && onRequestUpgrade ? (
        <PlanLockCTA
          currentTier={planTier}
          description={item.lockedMessage ?? "이 하이라이트는 Pro 이상 플랜에서 확인하실 수 있어요."}
          onUpgrade={onRequestUpgrade}
          className="relative z-10 mt-3 flex flex-wrap items-center justify-between gap-2 rounded-md border border-dashed border-border-light/70 bg-white/60 px-3 py-2 text-[11px] text-text-secondaryLight dark:border-border-dark/60 dark:bg-white/10 dark:text-text-secondaryDark"
        >
          <button
            type="button"
            className="rounded-md border border-primary/60 px-2 py-1 text-[11px] font-semibold text-primary transition-motion-fast hover:bg-primary/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            onClick={() => onRequestUpgrade?.("pro")}
          >
            팀과 상담하기
          </button>
        </PlanLockCTA>
      ) : null}
    </li>
  );
}

function buildItemClass(isActive: boolean, diffTone: DiffVisual) {
  const base = isActive
    ? "border-primary bg-primary/5 text-text-primaryLight shadow-card dark:border-primary.dark dark:bg-primary/10 dark:text-text-primaryDark"
    : "border-border-light bg-white text-text-secondaryLight shadow-sm hover:border-primary/50 dark:border-border-dark dark:bg-white/5 dark:text-text-secondaryDark";
  return `group relative rounded-lg border px-3 py-3 transition-motion-medium ${base}${diffTone ? ` ${diffTone.card}` : ""}`;
}

function buildQuoteClass(diffActive: boolean, diffTone: DiffVisual) {
  if (diffActive && diffTone) {
    return `mt-2 whitespace-pre-line rounded-md border border-border-light/60 px-3 py-2 text-sm leading-6 ${diffTone.quote}`;
  }
  return "mt-2 whitespace-pre-line text-sm leading-6 text-text-secondaryLight dark:text-text-secondaryDark";
}

function renderDiffDetails(item: EvidenceItem, diffActive: boolean) {
  if (!diffActive) {
    return null;
  }
  if (item.diffType === "updated" && item.previousQuote) {
    return (
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
    );
  }
  if (item.diffType === "created") {
    return (
      <p className="relative z-10 mt-2 text-[11px] font-semibold text-emerald-600 dark:text-emerald-300">
        이번에 새로 담긴 문장이에요.
      </p>
    );
  }
  if (item.diffType === "unchanged") {
    return (
      <p className="relative z-10 mt-2 text-[11px] text-text-ter티aryLight dark:text-text-ter티aryDark">이전 스냅샷과 같아요.</p>
    );
  }
  return null;
}

function renderChangedSummary(item: EvidenceItem) {
  const changedFields = Array.isArray(item.diffChangedFields) ? item.diffChangedFields : [];
  if (!changedFields.length) {
    return null;
  }
  const changedSummary = changedFields.map((field) => DIFF_FIELD_LABELS[field] ?? field).join(", ");
  return (
    <p className="relative z-10 mt-2 text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
      달라진 부분: {changedSummary}
    </p>
  );
}

function renderReliabilityBadge(item: EvidenceItem) {
  if (!item.sourceReliability) {
    return null;
  }
  const tone = RELIABILITY_TONE[item.sourceReliability];
  if (!tone) {
    return null;
  }
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 font-semibold ${tone.badge}`}>{tone.label}</span>
  );
}

function renderSimilarityBadge(item: EvidenceItem) {
  const similarity = formatSimilarity(item.anchor);
  if (!similarity) {
    return null;
  }
  return (
    <span className="rounded-md border border-border-light px-2 py-0.5 font-semibold text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
      {similarity}
    </span>
  );
}
