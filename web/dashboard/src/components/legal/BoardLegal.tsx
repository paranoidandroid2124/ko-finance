"use client";

import { LegalText } from "./LegalText";

export function BoardHeaderNotice({ className }: { className?: string }) {
  return (
    <LegalText
      section="board"
      item="header"
      as="div"
      className={className ?? "text-xs text-text-secondaryLight dark:text-text-secondaryDark"}
    />
  );
}

export function BoardShareModalNotice({ className }: { className?: string }) {
  return (
    <LegalText
      section="board"
      item="shareModal"
      as="div"
      className={className ?? "text-[11px] text-text-secondaryLight dark:text-text-secondaryDark"}
    />
  );
}

