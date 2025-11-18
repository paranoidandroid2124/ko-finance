"use client";

import { LegalText } from "./LegalText";

export function ChatInputDisclaimer({ className }: { className?: string }) {
  return <LegalText section="chat" item="inputDisclaimer" as="p" className={className} />;
}

export function ChatAnswerBadge({ className }: { className?: string }) {
  return (
    <LegalText
      section="chat"
      item="answerBadge"
      as="div"
      className={className ?? "text-[11px] text-text-secondaryLight dark:text-text-secondaryDark"}
    />
  );
}

export function ChatEvidencePanelNotice({ className }: { className?: string }) {
  return (
    <LegalText
      section="chat"
      item="evidencePanel"
      as="div"
      className={className ?? "text-[11px] text-text-secondaryLight dark:text-text-secondaryDark"}
    />
  );
}

