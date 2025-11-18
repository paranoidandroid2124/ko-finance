"use client";

import { LegalText } from "./LegalText";

export function AdminConsoleNotice({ className }: { className?: string }) {
  return (
    <LegalText
      section="admin"
      item="consoleHeader"
      as="div"
      className={className ?? "text-xs text-text-secondaryLight dark:text-text-secondaryDark"}
    />
  );
}

export function AuditDetailUsageNotice({ className }: { className?: string }) {
  return (
    <LegalText
      section="admin"
      item="auditDetail"
      as="div"
      className={className ?? "text-[11px] text-text-secondaryLight dark:text-text-secondaryDark"}
    />
  );
}

