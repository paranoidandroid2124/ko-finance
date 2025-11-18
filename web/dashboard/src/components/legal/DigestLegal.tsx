"use client";

import { LegalText } from "./LegalText";

export function DigestPdfFooter({ className }: { className?: string }) {
  return (
    <LegalText
      section="digest"
      item="pdfFooter"
      as="div"
      className={className ?? "text-xs text-text-secondaryLight dark:text-text-secondaryDark"}
    />
  );
}

export function DigestExportHelper({ className }: { className?: string }) {
  return (
    <LegalText
      section="digest"
      item="exportHelper"
      as="div"
      className={className ?? "text-[11px] text-text-secondaryLight dark:text-text-secondaryDark"}
    />
  );
}

