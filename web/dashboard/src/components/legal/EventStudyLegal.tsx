"use client";

import { LegalText } from "./LegalText";

export function EventStudyBoardHeader({ className }: { className?: string }) {
  return (
    <LegalText
      section="eventStudy"
      item="boardHeader"
      as="div"
      className={className ?? "text-xs text-text-secondaryLight dark:text-text-secondaryDark"}
    />
  );
}

export function RestatementRadarFooter({ className }: { className?: string }) {
  return (
    <LegalText
      section="eventStudy"
      item="radarFooter"
      as="div"
      className={className ?? "text-[11px] text-text-secondaryLight dark:text-text-secondaryDark"}
    />
  );
}

