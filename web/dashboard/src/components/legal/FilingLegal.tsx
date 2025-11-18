"use client";

import { LegalText } from "./LegalText";

export function FilingHeaderNotice({ className }: { className?: string }) {
  return (
    <LegalText
      section="filing"
      item="header"
      as="div"
      className={className ?? "text-xs text-text-secondaryLight dark:text-text-secondaryDark"}
    />
  );
}

export function FilingPdfDownloadNotice({ className }: { className?: string }) {
  return (
    <LegalText
      section="filing"
      item="pdfDownload"
      as="div"
      className={className ?? "text-[11px] text-text-secondaryLight dark:text-text-secondaryDark"}
    />
  );
}

export function FilingKoglBadge({ className }: { className?: string }) {
  return (
    <LegalText
      section="filing"
      item="koglType1"
      as="div"
      className={className ?? "text-[11px] text-text-secondaryLight dark:text-text-secondaryDark"}
    />
  );
}

