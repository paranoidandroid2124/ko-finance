"use client";

import { LegalText } from "./LegalText";

export function NewsCardFooter({ className }: { className?: string }) {
  return (
    <LegalText
      section="news"
      item="cardFooter"
      as="div"
      className={className ?? "text-[11px] text-text-secondaryLight dark:text-text-secondaryDark"}
    />
  );
}

export function NewsPageHeader({ className }: { className?: string }) {
  return (
    <LegalText
      section="news"
      item="pageHeader"
      as="div"
      className={className ?? "text-xs text-text-secondaryLight dark:text-text-secondaryDark"}
    />
  );
}

export function NewsAlertFooter({ className }: { className?: string }) {
  return (
    <LegalText
      section="news"
      item="alertFooter"
      as="div"
      className={className ?? "text-[11px] text-text-secondaryLight dark:text-text-secondaryDark"}
    />
  );
}

