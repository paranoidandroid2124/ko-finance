import { useQuery } from "@tanstack/react-query";

export type FilingSentiment = "positive" | "neutral" | "negative";

export type FilingFact = {
  label: string;
  value: string;
  anchor?: string;
};

export type FilingListItem = {
  id: string;
  company: string;
  title: string;
  type: string;
  filedAt: string;
  sentiment: FilingSentiment;
  sentimentReason?: string;
};

export type FilingDetail = FilingListItem & {
  summary: string;
  facts: FilingFact[];
  pdfViewerUrl?: string;
  pdfDownloadUrl?: string;
};

type ApiFilingBrief = {
  id: string;
  corp_name?: string | null;
  ticker?: string | null;
  report_name?: string | null;
  title?: string | null;
  category?: string | null;
  filed_at?: string | null;
  status: string;
  analysis_status: string;
  sentiment?: FilingSentiment;
  sentiment_reason?: string | null;
};

type ApiSummary = {
  insight?: string | null;
  what?: string | null;
  why?: string | null;
  how?: string | null;
  who?: string | null;
  when?: string | null;
  where?: string | null;
};

type ApiFact = {
  fact_type: string;
  value: string;
  anchor_page?: number | null;
  anchor_quote?: string | null;
};

type ApiFilingDetail = ApiFilingBrief & {
  summary?: ApiSummary | null;
  facts?: ApiFact[];
  urls?: Record<string, string | null> | null;
  source_files?: Record<string, string | null> | null;
};

const resolveApiBase = () => {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!base) {
    return "";
  }
  return base.endsWith("/") ? base.slice(0, -1) : base;
};

const formatDateTime = (value?: string | null) => {
  if (!value) {
    return "Unknown";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(parsed);
};

const deriveSentiment = (analysisStatus?: string, category?: string | null): FilingSentiment => {
  const normalizedStatus = (analysisStatus ?? "").toUpperCase();
  if (normalizedStatus === "FAILED" || normalizedStatus === "ERROR") {
    return "negative";
  }
  const normalizedCategory = (category ?? "").toLowerCase();
  if (
    normalizedCategory.includes("warning") ||
    normalizedCategory.includes("litigation") ||
    normalizedCategory.includes("lawsuit") ||
    normalizedCategory.includes("correction")
  ) {
    return "negative";
  }
  if (normalizedCategory.includes("positive") || normalizedCategory.includes("benefit") || normalizedCategory.includes("buyback")) {
    return "positive";
  }
  return "neutral";
};

const toListItem = (item: ApiFilingBrief): FilingListItem => ({
  id: item.id,
  company: item.corp_name || item.ticker || "Unknown company",
  title: item.report_name || item.title || "Untitled filing",
  type: item.category || item.report_name || "Unclassified",
  filedAt: formatDateTime(item.filed_at),
  sentiment: item.sentiment ?? deriveSentiment(item.analysis_status, item.category),
  sentimentReason: item.sentiment_reason ?? undefined
});

const buildSummaryText = (summary?: ApiSummary | null) => {
  if (!summary) {
    return "Summary is being generated.";
  }

  const candidates = [
    summary.insight,
    summary.what,
    summary.why,
    summary.how,
    [summary.who, summary.when, summary.where].filter(Boolean).join(" · ")
  ].filter((entry) => Boolean(entry && entry.trim())) as string[];

  if (candidates.length === 0) {
    return "Summary is being generated.";
  }
  return candidates[0];
};

const formatAnchor = (fact: ApiFact) => {
  if (fact.anchor_quote) {
    return fact.anchor_quote;
  }
  if (fact.anchor_page) {
    return `p.${fact.anchor_page}`;
  }
  return undefined;
};

const toDetail = (detail: ApiFilingDetail): FilingDetail => {
  const listItem = toListItem(detail);
  const facts = (detail.facts ?? []).map((fact) => ({
    label: fact.fact_type,
    value: fact.value,
    anchor: formatAnchor(fact)
  }));

  const urls = detail.urls ?? {};
  const sourceFiles = detail.source_files ?? {};
  const pdfViewerUrl =
    urls.viewer || urls.minio_url || (typeof sourceFiles.pdf === "string" && sourceFiles.pdf.startsWith("http") ? sourceFiles.pdf : undefined);
  const pdfDownloadUrl =
    urls.minio_url || urls.download || (typeof sourceFiles.pdf === "string" && sourceFiles.pdf.startsWith("http") ? sourceFiles.pdf : undefined);

  return {
    ...listItem,
    summary: buildSummaryText(detail.summary),
    facts,
    pdfViewerUrl: pdfViewerUrl ?? undefined,
    pdfDownloadUrl: pdfDownloadUrl ?? pdfViewerUrl ?? undefined
  };
};

const fetchFilings = async (): Promise<FilingListItem[]> => {
  const baseUrl = resolveApiBase();
  const response = await fetch(`${baseUrl}/api/v1/filings/?limit=50`);
  if (!response.ok) {
    throw new Error("Failed to load filing list.");
  }
  const payload: ApiFilingBrief[] = await response.json();
  return payload.map(toListItem);
};

const fetchFilingDetail = async (filingId: string): Promise<FilingDetail> => {
  const baseUrl = resolveApiBase();
  const response = await fetch(`${baseUrl}/api/v1/filings/${filingId}`);
  if (!response.ok) {
    throw new Error("Failed to load filing detail.");
  }
  const payload: ApiFilingDetail = await response.json();
  return toDetail(payload);
};

export function useFilings() {
  return useQuery({
    queryKey: ["filings"],
    queryFn: fetchFilings
  });
}

export function useFilingDetail(filingId?: string) {
  return useQuery({
    queryKey: ["filings", filingId],
    queryFn: () => fetchFilingDetail(filingId as string),
    enabled: Boolean(filingId)
  });
}
