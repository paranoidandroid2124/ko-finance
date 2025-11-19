import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  EvidenceWorkspaceItemPayload,
  EvidenceWorkspaceResponsePayload,
  EvidenceTableCellPayload,
  fetchEvidenceWorkspace,
  EvidenceAnchorPayload,
} from "@/lib/evidenceApi";
import type {
  EvidencePanelItem,
  EvidenceAnchor,
  EvidenceSelfCheck,
  EvidenceTableReference,
  EvidenceTableCell,
  EvidenceDocumentMeta,
} from "@/components/evidence/types";

type MappedWorkspace = {
  evidence: EvidencePanelItem[];
  removed: EvidencePanelItem[];
  pdfUrl?: string | null;
  pdfDownloadUrl?: string | null;
  selectedUrnId?: string | null;
  diffEnabled: boolean;
};

const toPdfRect = (
  rect?: EvidenceAnchorPayload["pdf_rect"],
): EvidenceAnchor["pdfRect"] => {
  if (!rect) {
    return null;
  }
  const { page, x, y, width, height } = rect;
  if (page == null || x == null || y == null || width == null || height == null) {
    return null;
  }
  return { page, x, y, width, height };
};

const toEvidenceAnchor = (anchor?: EvidenceWorkspaceItemPayload["anchor"]): EvidenceAnchor | undefined => {
  if (!anchor) {
    return undefined;
  }
  return {
    paragraphId: anchor.paragraph_id ?? undefined,
    pdfRect: toPdfRect(anchor.pdf_rect),
    similarity: undefined,
  };
};

const toSelfCheck = (
  payload?: EvidenceWorkspaceItemPayload["self_check"]
): EvidenceSelfCheck | undefined => {
  if (!payload) {
    return undefined;
  }
  return {
    verdict: (payload.verdict as EvidenceSelfCheck["verdict"]) ?? null,
    score: payload.score ?? null,
    explanation: payload.explanation ?? null,
  };
};

const parseReliability = (
  value?: string | null,
): EvidencePanelItem["sourceReliability"] => {
  if (value === "high" || value === "medium" || value === "low") {
    return value;
  }
  return null;
};

const parseDiffType = (
  value?: string | null,
): EvidencePanelItem["diffType"] => {
  if (value === "created" || value === "updated" || value === "unchanged" || value === "removed") {
    return value;
  }
  return undefined;
};

const toDocumentMeta = (payload?: EvidenceWorkspaceItemPayload["document"]): EvidenceDocumentMeta | null => {
  if (!payload) {
    return null;
  }
  return {
    documentId: payload.documentId ?? null,
    title: payload.title ?? null,
    corpName: payload.corpName ?? null,
    ticker: payload.ticker ?? null,
    receiptNo: payload.receiptNo ?? null,
    viewerUrl: payload.viewerUrl ?? null,
    downloadUrl: payload.downloadUrl ?? null,
    publishedAt: payload.publishedAt ?? null,
  };
};

const toTableCell = (payload: EvidenceTableCellPayload): EvidenceTableCell => ({
  columnIndex: payload.column_index ?? 0,
  headerPath: payload.header_path ?? [],
  value: payload.value ?? undefined,
  normalizedValue: payload.normalized_value ?? undefined,
  numericValue: payload.numeric_value ?? undefined,
  valueType: payload.value_type ?? undefined,
  confidence: payload.confidence ?? undefined,
});

const toTableReference = (
  payload?: EvidenceWorkspaceItemPayload["table_reference"]
): EvidenceTableReference | null => {
  if (!payload) {
    return null;
  }
  return {
    tableId: payload.table_id ?? null,
    pageNumber: payload.page_number ?? null,
    tableIndex: payload.table_index ?? null,
    title: payload.title ?? null,
    rowCount: payload.row_count ?? null,
    columnCount: payload.column_count ?? null,
    headerRows: payload.header_rows ?? null,
    confidence: payload.confidence ?? null,
    columnHeaders: payload.column_headers ?? [],
    focusRowIndex: payload.focus_row_index ?? null,
    focusRowCells: (payload.focus_row_cells ?? []).map(toTableCell),
    explorerUrl: payload.explorer_url ?? null,
  };
};

const mapEvidenceItem = (payload: EvidenceWorkspaceItemPayload): EvidencePanelItem => {
  const documentMeta = toDocumentMeta(payload.document);
  const documentUrl =
    payload.viewer_url ?? payload.document_url ?? documentMeta?.viewerUrl ?? documentMeta?.downloadUrl ?? null;
  const downloadUrl = payload.download_url ?? documentMeta?.downloadUrl ?? null;
  return {
    urnId: payload.urn_id,
    chunkId: payload.chunk_id ?? undefined,
    quote: payload.quote,
    section: payload.section ?? undefined,
    pageNumber: payload.page_number ?? undefined,
    anchor: toEvidenceAnchor(payload.anchor),
    selfCheck: toSelfCheck(payload.self_check),
    sourceReliability: parseReliability(payload.source_reliability),
    createdAt: payload.created_at ?? undefined,
    diffType: parseDiffType(payload.diff_type),
    diffChangedFields: payload.diff_changed_fields ?? undefined,
    previousQuote: payload.previous_quote ?? undefined,
    previousSection: payload.previous_section ?? undefined,
    previousPageNumber: payload.previous_page_number ?? undefined,
    previousAnchor: toEvidenceAnchor(payload.previous_anchor),
    previousSourceReliability: parseReliability(payload.previous_source_reliability),
    previousSelfCheck: toSelfCheck(payload.previous_self_check),
    documentTitle: payload.document_title ?? documentMeta?.title ?? undefined,
    documentUrl,
    documentDownloadUrl: downloadUrl ?? undefined,
    documentMeta,
    tableReference: toTableReference(payload.table_reference),
  };
};

export const mapWorkspacePayload = (payload: EvidenceWorkspaceResponsePayload): MappedWorkspace => ({
  evidence: payload.evidence.map(mapEvidenceItem),
  removed: (payload.diff?.removed ?? []).map(mapEvidenceItem),
  pdfUrl: payload.pdfUrl ?? undefined,
  pdfDownloadUrl: payload.pdfDownloadUrl ?? undefined,
  selectedUrnId: payload.selectedUrnId ?? undefined,
  diffEnabled: Boolean(payload.diff?.enabled),
});

export const useEvidenceWorkspace = (traceId?: string | null, urnId?: string | null, filingId?: string | null) => {
  const query = useQuery<EvidenceWorkspaceResponsePayload, Error>({
    queryKey: ["evidence-workspace", traceId, filingId, urnId],
    queryFn: () =>
      fetchEvidenceWorkspace({
        traceId: traceId ?? undefined,
        filingId: filingId ?? undefined,
        urnId: urnId ?? undefined,
      }),
    enabled: Boolean(traceId || filingId),
    staleTime: 30_000,
  });

  const data = useMemo(() => (query.data ? mapWorkspacePayload(query.data) : undefined), [query.data]);

  return {
    data,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
};

export default useEvidenceWorkspace;
