"use client";

import { EvidenceRow } from "./EvidenceRow";
import type { EvidenceItem, EvidencePanelProps, PlanTier } from "./types";
import { DIFF_TONE } from "./constants";

type EvidenceListProps = {
  status: EvidencePanelProps["status"];
  items: EvidenceItem[];
  activeUrn?: string;
  diffActive?: boolean;
  planTier: PlanTier;
  bindObserver: (urnId: string) => (element: HTMLLIElement | null) => void;
  onSelect: (urnId: string) => void;
  onHover?: (urnId: string | undefined) => void;
  onRequestUpgrade?: (tier: PlanTier) => void;
  removedItems?: EvidenceItem[];
};

export function EvidenceList({
  status,
  items,
  activeUrn,
  diffActive,
  planTier,
  bindObserver,
  onSelect,
  onHover,
  onRequestUpgrade,
  removedItems,
}: EvidenceListProps) {
  if (status === "loading") {
    return (
      <ul className="space-y-2">
        {items.map((item) => (
          <li
            key={item.urnId}
            className="rounded-lg border border-dashed border-border-light/70 p-3 text-sm text-text-secondaryLight dark:border-border-dark/60 dark:text-text-secondaryDark"
          >
            {item.quote || "근거를 불러오는 중입니다…"}
          </li>
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
        <EvidenceRemovedList diffActive={diffActive} items={removedItems} />
      </>
    );
  }

  return (
    <>
      <ul className="space-y-2">
        {items.map((item) => (
          <EvidenceRow
            key={item.urnId}
            item={item}
            isActive={item.urnId === activeUrn}
            diffActive={Boolean(diffActive)}
            observerRef={bindObserver(item.urnId)}
            onSelect={onSelect}
            onHover={onHover}
            onRequestUpgrade={onRequestUpgrade}
            planTier={planTier}
          />
        ))}
      </ul>
      <EvidenceRemovedList diffActive={diffActive} items={removedItems} />
    </>
  );
}

type EvidenceRemovedListProps = {
  diffActive?: boolean;
  items?: EvidenceItem[];
};

function EvidenceRemovedList({ diffActive, items }: EvidenceRemovedListProps) {
  if (!diffActive || !items?.length) {
    return null;
  }
  return (
    <div className="rounded-lg border border-dashed border-border-light/70 bg-background-cardLight/60 p-3 text-xs text-text-secondaryLight dark:border-border-dark/60 dark:bg-background-cardDark/50 dark:text-text-secondaryDark">
      <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">이전 스냅샷에서 사라진 문장</p>
      <ul className="mt-3 space-y-2">
        {items.map((item) => {
          const tone = DIFF_TONE.removed;
          return (
            <li key={item.urnId} className="rounded-md border border-dashed border-border-light/70 px-3 py-2">
              <div className="flex flex-wrap items-center gap-2 text-[11px]">
                <span className={`inline-flex items-center rounded-md border px-2 py-0.5 font-semibold ${tone.badge}`}>
                  {tone.label}
                </span>
                {item.section ? (
                  <span className="text-text-tertiaryLight dark:text-text-tertiaryDark">{item.section}</span>
                ) : null}
              </div>
              <p className="mt-2 whitespace-pre-line text-sm leading-6 text-text-secondaryLight dark:text-text-secondaryDark">
                {item.quote}
              </p>
              {item.pageNumber ? (
                <p className="mt-1 text-[10px] uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
                  페이지: p.{item.pageNumber}
                </p>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
