"use client";

import { createLegalText } from "./LegalText";

const SECONDARY_TEXT = "text-xs text-text-secondaryLight dark:text-text-secondaryDark";
const TERTIARY_TEXT = "text-[11px] text-text-secondaryLight dark:text-text-secondaryDark";

export const FilingHeaderNotice = createLegalText("filing", "header", { defaultAs: "div", defaultClassName: SECONDARY_TEXT });
export const FilingPdfDownloadNotice = createLegalText("filing", "pdfDownload", { defaultAs: "div", defaultClassName: TERTIARY_TEXT });
export const FilingKoglBadge = createLegalText("filing", "koglType1", { defaultAs: "div", defaultClassName: TERTIARY_TEXT });

export const AdminConsoleNotice = createLegalText("admin", "consoleHeader", { defaultAs: "div", defaultClassName: SECONDARY_TEXT });
export const AuditDetailUsageNotice = createLegalText("admin", "auditDetail", { defaultAs: "div", defaultClassName: TERTIARY_TEXT });

export const AlertRuleBuilderFooter = createLegalText("alerts", "ruleBuilderFooter", { defaultAs: "div", defaultClassName: SECONDARY_TEXT });
export const AlertNotificationFooter = createLegalText("alerts", "notificationFooter", { defaultAs: "div", defaultClassName: TERTIARY_TEXT });

export const ChatInputDisclaimer = createLegalText("chat", "inputDisclaimer", { defaultAs: "p" });
export const ChatAnswerBadge = createLegalText("chat", "answerBadge", { defaultAs: "div", defaultClassName: TERTIARY_TEXT });
export const ChatEvidencePanelNotice = createLegalText("chat", "evidencePanel", { defaultAs: "div", defaultClassName: TERTIARY_TEXT });

export const DigestPdfFooter = createLegalText("digest", "pdfFooter", { defaultAs: "div", defaultClassName: SECONDARY_TEXT });
export const DigestExportHelper = createLegalText("digest", "exportHelper", { defaultAs: "div", defaultClassName: TERTIARY_TEXT });

export const EventStudyBoardHeader = createLegalText("eventStudy", "boardHeader", { defaultAs: "div", defaultClassName: SECONDARY_TEXT });
export const RestatementRadarFooter = createLegalText("eventStudy", "radarFooter", { defaultAs: "div", defaultClassName: TERTIARY_TEXT });

export const BoardHeaderNotice = createLegalText("board", "header", { defaultAs: "div", defaultClassName: SECONDARY_TEXT });
export const BoardShareModalNotice = createLegalText("board", "shareModal", { defaultAs: "div", defaultClassName: TERTIARY_TEXT });

export const NewsCardFooter = createLegalText("news", "cardFooter", { defaultAs: "div", defaultClassName: TERTIARY_TEXT });
export const NewsPageHeader = createLegalText("news", "pageHeader", { defaultAs: "div", defaultClassName: SECONDARY_TEXT });
export const NewsAlertFooter = createLegalText("news", "alertFooter", { defaultAs: "div", defaultClassName: TERTIARY_TEXT });

export const AuthSignupHelper = createLegalText("auth", "signupHelper", { defaultAs: "div", defaultClassName: SECONDARY_TEXT });
export const AuthTermsCheckboxLabel = createLegalText("auth", "termsCheckbox", { defaultAs: "span" });
export const AuthPrivacyCheckboxLabel = createLegalText("auth", "privacyCheckbox", { defaultAs: "span" });
export const AuthMarketingCheckboxLabel = createLegalText("auth", "marketingCheckbox", { defaultAs: "span" });

const SettingsAccountRetention = createLegalText("settings", "accountRetention", { defaultAs: "span" });
const SettingsLogRetention = createLegalText("settings", "logRetention", { defaultAs: "span" });
const SettingsContentRetention = createLegalText("settings", "contentRetention", { defaultAs: "span" });
const SettingsLlmToggle = createLegalText("settings", "llmToggle", { defaultAs: "span" });

export function SettingsDataRetentionList({ className }: { className?: string }) {
  return (
    <ul className={className ?? "space-y-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark"}>
      <li>
        <SettingsAccountRetention />
      </li>
      <li>
        <SettingsLogRetention />
      </li>
      <li>
        <SettingsContentRetention />
      </li>
      <li>
        <SettingsLlmToggle />
      </li>
    </ul>
  );
}
