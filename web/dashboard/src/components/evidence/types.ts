"use client";

import type { PlanTier as PlanTierType } from "@/store/planStore";

export type PlanTier = PlanTierType;

export type EvidenceAnchor = {
  paragraphId?: string | null;
  pdfRect?: {
    page: number;
    x: number;
    y: number;
    width: number;
    height: number;
  } | null;
  similarity?: number | null;
};

export type EvidenceSelfCheck = {
  score?: number | null;
  verdict?: "pass" | "warn" | "fail" | null;
  explanation?: string | null;
};

export type EvidenceDocumentMeta = {
  documentId?: string | null;
  title?: string | null;
  corpName?: string | null;
  ticker?: string | null;
  receiptNo?: string | null;
  viewerUrl?: string | null;
  downloadUrl?: string | null;
  publishedAt?: string | null;
};

export type EvidenceTableCell = {
  columnIndex: number;
  headerPath: string[];
  value?: string | null;
  normalizedValue?: string | null;
  numericValue?: number | null;
  valueType?: string | null;
  confidence?: number | null;
};

export type EvidenceTableReference = {
  tableId?: string | null;
  pageNumber?: number | null;
  tableIndex?: number | null;
  title?: string | null;
  rowCount?: number | null;
  columnCount?: number | null;
  headerRows?: number | null;
  confidence?: number | null;
  columnHeaders?: string[][];
  focusRowIndex?: number | null;
  focusRowCells?: EvidenceTableCell[];
  explorerUrl?: string | null;
};

export type EvidenceItem = {
  urnId: string;
  quote: string;
  section?: string | null;
  pageNumber?: number | null;
  anchor?: EvidenceAnchor | null;
  selfCheck?: EvidenceSelfCheck | null;
  sourceReliability?: "high" | "medium" | "low" | null;
  createdAt?: string | null;
  chunkId?: string | null;
  locked?: boolean;
  lockedMessage?: string | null;
  diffType?: "created" | "updated" | "unchanged" | "removed" | null;
  diffChangedFields?: string[] | null;
  previousQuote?: string | null;
  previousSection?: string | null;
  previousPageNumber?: number | null;
  previousAnchor?: EvidenceAnchor | null;
  previousSourceReliability?: "high" | "medium" | "low" | null;
  previousSelfCheck?: EvidenceSelfCheck | null;
  documentTitle?: string | null;
  documentUrl?: string | null;
  documentDownloadUrl?: string | null;
  documentMeta?: EvidenceDocumentMeta | null;
  tableReference?: EvidenceTableReference | null;
};

export type EvidencePanelStatus = "loading" | "ready" | "empty" | "anchor-mismatch";

export type EvidencePdfStatus = "idle" | "loading" | "ready" | "error";

export type EvidencePanelProps = {
  planTier: PlanTier;
  status: EvidencePanelStatus;
  items: EvidenceItem[];
  selectedUrnId?: string;
  inlinePdfEnabled?: boolean;
  pdfUrl?: string | null;
  pdfDownloadUrl?: string | null;
  diffEnabled?: boolean;
  diffActive?: boolean;
  removedItems?: EvidenceItem[];
  onSelectEvidence?: (urnId: string) => void;
  onHoverEvidence?: (urnId: string | undefined) => void;
  onRequestOpenPdf?: (urnId: string) => void;
  onRequestUpgrade?: (tier: PlanTier) => void;
  onToggleDiff?: (nextValue: boolean) => void;
};

export type EvidenceListItemProps = {
  item: EvidenceItem;
  isActive: boolean;
  diffActive: boolean;
  observerRef: (element: HTMLLIElement | null) => void;
  onSelect: (urnId: string) => void;
  onHover?: (urnId: string | undefined) => void;
  onRequestUpgrade?: (tier: PlanTier) => void;
  planTier: PlanTier;
};

export type EvidencePanelItem = EvidenceItem;
