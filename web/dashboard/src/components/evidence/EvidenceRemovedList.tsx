"use client";

import { DIFF_TONE } from "./constants";
import type { EvidenceItem } from "./types";

type EvidenceRemovedListProps = {
  diffActive?: boolean;
  items?: EvidenceItem[];
};

export function EvidenceRemovedList({ diffActive, items }: EvidenceRemovedListProps) {
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

