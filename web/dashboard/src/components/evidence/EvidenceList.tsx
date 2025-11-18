"use client";

import { EvidenceRow } from "./EvidenceRow";
import { EvidenceRemovedList } from "./EvidenceRemovedList";
import type { EvidenceItem, EvidencePanelProps, PlanTier } from "./types";

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
