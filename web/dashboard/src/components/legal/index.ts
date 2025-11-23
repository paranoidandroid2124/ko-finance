import { createLegalText } from "./LegalText";

export { LegalText, createLegalText } from "./LegalText";
export type { LegalTextProps } from "./LegalText";
export { LEGAL_COPY } from "./LegalCopy";

export const ChatInputDisclaimer = createLegalText("chat", "inputDisclaimer");
export const ChatEvidencePanelNotice = createLegalText("chat", "evidenceNotice");
export const FilingHeaderNotice = createLegalText("filing", "headerNotice");
export const FilingPdfDownloadNotice = createLegalText("filing", "pdfDownloadNotice");
export const FilingKoglBadge = createLegalText("filing", "koglBadge");
export const SettingsDataRetentionList = createLegalText("settings", "dataRetentionList", {
  defaultAs: "div",
});
