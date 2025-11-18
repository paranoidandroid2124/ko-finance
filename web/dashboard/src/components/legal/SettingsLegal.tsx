"use client";

import { LegalText } from "./LegalText";

export function SettingsDataRetentionList({ className }: { className?: string }) {
  return (
    <ul className={className ?? "space-y-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark"}>
      <li>
        <LegalText section="settings" item="accountRetention" as="span" />
      </li>
      <li>
        <LegalText section="settings" item="logRetention" as="span" />
      </li>
      <li>
        <LegalText section="settings" item="contentRetention" as="span" />
      </li>
      <li>
        <LegalText section="settings" item="llmToggle" as="span" />
      </li>
    </ul>
  );
}

