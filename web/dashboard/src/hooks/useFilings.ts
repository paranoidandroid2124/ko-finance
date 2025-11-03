import { useQuery } from "@tanstack/react-query";

import { resolveApiBase } from "@/lib/apiBase";
import { formatKoreanDateTime } from "@/lib/datetime";

export type FilingSentimentFilter = "all" | "positive" | "negative";

type FilingListParams = {
  days?: number;
  limit?: number;
  ticker?: string;
  corpCode?: string;
  startDate?: string;
  endDate?: string;
  sentiment?: FilingSentimentFilter;
};

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
  sentiment?: FilingSentiment | null;
  sentiment_reason?: string | null;
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

const CATEGORY_TRANSLATIONS: Record<string, string> = {
  capital_increase: "증자",
  "증자": "증자",
  buyback: "자사주 매입/소각",
  share_buyback: "자사주 매입/소각",
  "자사주 매입/소각": "자사주 매입/소각",
  cb_bw: "전환사채·신주인수권부사채",
  convertible: "전환사채·신주인수권부사채",
  "전환사채·신주인수권부사채": "전환사채·신주인수권부사채",
  large_contract: "대규모 공급·수주 계약",
  major_contract: "대규모 공급·수주 계약",
  "대규모 공급·수주 계약": "대규모 공급·수주 계약",
  litigation: "소송/분쟁",
  lawsuit: "소송/분쟁",
  "소송/분쟁": "소송/분쟁",
  mna: "M&A/합병·분할",
  "m&a": "M&A/합병·분할",
  merger: "M&A/합병·분할",
  "M&A/합병·분할": "M&A/합병·분할",
  governance: "지배구조·임원 변경",
  governance_change: "지배구조·임원 변경",
  "지배구조·임원 변경": "지배구조·임원 변경",
  audit_opinion: "감사 의견",
  "감사 의견": "감사 의견",
  periodic_report: "정기·수시 보고서",
  regular_report: "정기·수시 보고서",
  "정기·수시 보고서": "정기·수시 보고서",
  securities_registration: "증권신고서/투자설명서",
  registration: "증권신고서/투자설명서",
  "증권신고서/투자설명서": "증권신고서/투자설명서",
  insider_ownership: "임원·주요주주 지분 변동",
  insider_trading: "임원·주요주주 지분 변동",
  "임원·주요주주 지분 변동": "임원·주요주주 지분 변동",
  correction: "정정 공시",
  revision: "정정 공시",
  "정정 공시": "정정 공시",
  ir_presentation: "IR/설명회",
  ir: "IR/설명회",
  "IR/설명회": "IR/설명회",
  dividend: "배당/주주환원",
  shareholder_return: "배당/주주환원",
  "배당/주주환원": "배당/주주환원",
  other: "기타",
  "기타": "기타",
};

const POSITIVE_CATEGORY_LABELS = new Set(["자사주 매입/소각", "대규모 공급·수주 계약", "배당/주주환원", "M&A/합병·분할"]);
const NEGATIVE_CATEGORY_LABELS = new Set(["소송/분쟁", "감사 의견", "정정 공시"]);

const normalizeCategoryLabel = (raw?: string | null): string | undefined => {
  if (!raw) {
    return undefined;
  }
  const trimmed = raw.trim();
  const lower = trimmed.toLowerCase();
  return CATEGORY_TRANSLATIONS[lower] ?? CATEGORY_TRANSLATIONS[trimmed] ?? trimmed;
};

const deriveSentiment = (analysisStatus?: string, category?: string | null): FilingSentiment => {
  const normalizedStatus = (analysisStatus ?? "").toUpperCase();
  if (normalizedStatus === "FAILED" || normalizedStatus === "ERROR") {
    return "negative";
  }
  const label = normalizeCategoryLabel(category);
  if (label) {
    if (POSITIVE_CATEGORY_LABELS.has(label)) {
      return "positive";
    }
    if (NEGATIVE_CATEGORY_LABELS.has(label)) {
      return "negative";
    }
  }
  return "neutral";
};

const toListItem = (item: ApiFilingBrief): FilingListItem => {
  const categoryLabel = normalizeCategoryLabel(item.category);
  return {
    id: item.id,
    company: item.corp_name || item.ticker || "미확인 기업",
    title: item.report_name || item.title || "제목 미정",
    type: categoryLabel || item.report_name || item.title || "분류 없음",
    filedAt: formatKoreanDateTime(item.filed_at, { fallback: "날짜 미상", keepInvalid: false }),
    sentiment: item.sentiment ?? deriveSentiment(item.analysis_status, item.category),
    sentimentReason: item.sentiment_reason ?? undefined,
  };
};

const buildSummaryText = (summary?: ApiSummary | null) => {
  if (!summary) {
    return "요약을 생성하는 중입니다.";
  }

  const candidates = [
    summary.insight,
    summary.what,
    summary.why,
    summary.how,
    [summary.who, summary.when, summary.where].filter(Boolean).join(" · "),
  ].filter((entry) => Boolean(entry && entry.trim())) as string[];

  if (candidates.length === 0) {
    return "요약을 생성하는 중입니다.";
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

const buildQueryString = (params: FilingListParams) => {
  const search = new URLSearchParams();
  search.set("limit", String(params.limit ?? 100));
  if (params.days !== undefined) {
    search.set("days", String(params.days));
  }
  if (params.ticker) {
    search.set("ticker", params.ticker);
  }
  if (params.corpCode) {
    search.set("corp_code", params.corpCode);
  }
  if (params.startDate) {
    search.set("start_date", params.startDate);
  }
  if (params.endDate) {
    search.set("end_date", params.endDate);
  }
  if (params.sentiment && params.sentiment !== "all") {
    search.set("sentiment", params.sentiment);
  }
  return search.toString();
};

const fetchFilings = async (params: FilingListParams): Promise<FilingListItem[]> => {
  const baseUrl = resolveApiBase();
  const query = buildQueryString(params);
  const response = await fetch(`${baseUrl}/api/v1/filings/?${query}`);
  if (!response.ok) {
    throw new Error("공시 목록을 불러오지 못했습니다.");
  }
  const payload: ApiFilingBrief[] = await response.json();
  return payload.map(toListItem);
};

const fetchFilingDetail = async (filingId: string): Promise<FilingDetail> => {
  const baseUrl = resolveApiBase();
  const response = await fetch(`${baseUrl}/api/v1/filings/${filingId}`);
  if (!response.ok) {
    throw new Error("공시 상세를 불러오지 못했습니다.");
  }
  const payload: ApiFilingDetail = await response.json();
  return toDetail(payload);
};

export function useFilings(params: FilingListParams = {}) {
  return useQuery({
    queryKey: ["filings", params],
    queryFn: () => fetchFilings(params)
  });
}

export function useFilingDetail(filingId?: string) {
  return useQuery({
    queryKey: ["filing-detail", filingId],
    queryFn: () => fetchFilingDetail(filingId as string),
    enabled: Boolean(filingId)
  });
}
