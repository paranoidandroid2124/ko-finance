/**
 * Constants for filing-related operations
 */

export const REPORT_TYPE_LABELS: Record<string, string> = {
    annual: "사업보고서",
    semi_annual: "반기보고서",
    quarterly: "분기보고서",
} as const;

export type ReportType = keyof typeof REPORT_TYPE_LABELS;
