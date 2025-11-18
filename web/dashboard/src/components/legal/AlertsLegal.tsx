"use client";

import { LegalText } from "./LegalText";

export function AlertRuleBuilderFooter({ className }: { className?: string }) {
  return (
    <LegalText
      section="alerts"
      item="ruleBuilderFooter"
      as="div"
      className={className ?? "text-xs text-text-secondaryLight dark:text-text-secondaryDark"}
    />
  );
}

export function AlertNotificationFooter({ className }: { className?: string }) {
  return (
    <LegalText
      section="alerts"
      item="notificationFooter"
      as="div"
      className={className ?? "text-[11px] text-text-secondaryLight dark:text-text-secondaryDark"}
    />
  );
}

