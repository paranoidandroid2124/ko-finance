"use client";

import { useMemo } from "react";
import classNames from "classnames";

import { InlinePdfViewer } from "@/components/evidence/InlinePdfViewer";
import { useEvidenceWorkspaceStore } from "@/store/evidenceWorkspaceStore";
import type { EvidencePanelItem } from "@/components/evidence";

type EvidenceDetailPanelProps = {
  pdfUrl?: string | null;
  pdfDownloadUrl?: string | null;
};

const toExternalLink = (url?: string | null) => {
  if (!url) {
    return null;
  }
  const target = url.startsWith("http") ? url : `${url}`;
  return (
    <a
      href={target}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center rounded-md border border-border-light px-3 py-1.5 text-xs font-semibold text-primary transition-colors hover:border-primary hover:text-primary dark:border-border-dark"
    >
      원문 열기
    </a>
  );
};

const TablePreview = ({ evidence }: { evidence: EvidencePanelItem }) => {
  if (!evidence.tableReference) {
    return null;
  }
  const headers = evidence.tableReference.columnHeaders ?? [];
  const focusCells = evidence.tableReference.focusRowCells ?? [];
  return (
    <section className="rounded-xl border border-border-light bg-background-cardLight/70 p-4 dark:border-border-dark dark:bg-background-cardDark/40">
      <header className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-primary/80">표 미리보기</p>
          <h3 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">
            {evidence.tableReference.title ?? "표 행 요약"}
          </h3>
        </div>
        {evidence.tableReference.explorerUrl ? (
          <a
            href={evidence.tableReference.explorerUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-semibold text-primary hover:underline"
          >
            Table Explorer
          </a>
        ) : null}
      </header>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[360px] text-left text-xs">
          <thead>
            <tr>
              {focusCells.map((cell, index) => (
                <th key={cell.columnIndex ?? index} className="border-b border-border-light px-2 py-1 dark:border-border-dark">
                  {headers[cell.columnIndex ?? index]?.join(" / ") || "열"}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              {focusCells.map((cell, index) => (
                <td
                  key={cell.columnIndex ?? index}
                  className="border-b border-dashed border-border-light px-2 py-1 text-sm text-text-primaryLight dark:border-border-dark dark:text-text-primaryDark"
                >
                  {cell.value ?? "—"}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
};

const DiffBlock = ({ evidence }: { evidence: EvidencePanelItem }) => {
  const previousChanged =
    evidence.diffType === "updated" &&
    (evidence.previousQuote || evidence.previousSection || evidence.previousPageNumber);
  if (!previousChanged) {
    return null;
  }
  return (
    <div className="rounded-xl border border-border-light bg-background-cardLight/60 p-4 dark:border-border-dark dark:bg-background-cardDark/50">
      <p className="text-xs font-semibold uppercase tracking-wide text-primary/70">이전 버전</p>
      <p className="mt-2 rounded-lg bg-background canvas px-3 py-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
        {evidence.previousQuote}
      </p>
      <div className="mt-1 text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
        {evidence.previousSection ?? "섹션 정보 없음"} · {evidence.previousPageNumber ? `${evidence.previousPageNumber}쪽` : "페이지 미상"}
      </div>
    </div>
  );
};

export function EvidenceDetailPanel({ pdfUrl, pdfDownloadUrl }: EvidenceDetailPanelProps) {
  const { evidenceItems, selectedEvidenceUrn } = useEvidenceWorkspaceStore();
  const selected = useMemo(
    () => evidenceItems.find((item) => item.urnId === selectedEvidenceUrn),
    [evidenceItems, selectedEvidenceUrn],
  );

  if (!selected) {
    return (
      <div className="rounded-xl border border-dashed border-border-light/70 p-6 text-sm text-text-secondaryLight dark:border-border-dark/60 dark:text-text-secondaryDark">
        선택된 Evidence가 없습니다. 왼쪽 목록에서 항목을 선택해 주세요.
      </div>
    );
  }

  const documentUrl = selected.documentUrl ?? pdfUrl ?? null;
  const downloadUrl = selected.documentDownloadUrl ?? pdfDownloadUrl ?? null;
  const pdfPage = selected.anchor?.pdfRect?.page ?? selected.pageNumber ?? undefined;
  const highlightRect = selected.anchor?.pdfRect ?? undefined;

  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-xl border border-border-light bg-background-cardLight/70 p-4 dark:border-border-dark dark:bg-background-cardDark/50">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-primary/70">문서</p>
            <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">
              {selected.documentTitle ?? "근거 문서"}
            </h2>
            {selected.documentMeta?.ticker ? (
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                {selected.documentMeta.ticker}
                {selected.documentMeta.corpName ? ` · ${selected.documentMeta.corpName}` : ""}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {documentUrl ? toExternalLink(documentUrl) : null}
            {downloadUrl ? (
              <a
                href={downloadUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center rounded-md border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark"
              >
                PDF 받기
              </a>
            ) : null}
          </div>
        </header>
        <div className="mt-3 rounded-lg border border-border-light bg-white/80 p-3 text-sm leading-relaxed text-text-secondaryLight shadow-sm dark:border-border-dark dark:bg-background-cardDark/60 dark:text-text-secondaryDark">
          “{selected.quote}”
        </div>
        <div className="mt-2 flex flex-wrap gap-3 text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
          <span>{selected.section ?? "섹션 정보 없음"}</span>
          <span>{selected.pageNumber ? `${selected.pageNumber}쪽` : "페이지 미상"}</span>
          {selected.sourceReliability ? <span>신뢰도: {selected.sourceReliability}</span> : null}
          {selected.selfCheck?.verdict ? <span>Self-check: {selected.selfCheck.verdict}</span> : null}
        </div>
      </section>
      <DiffBlock evidence={selected} />
      <TablePreview evidence={selected} />
      <section className="rounded-xl border border-border-light bg-background-cardLight/80 p-4 dark:border-border-dark dark:bg-background-cardDark/40">
        <header className="mb-3 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-primary/70">PDF 미리보기</p>
            <h3 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">
              {selected.documentTitle ?? "증거 문단"}
            </h3>
          </div>
          {downloadUrl ? (
            <a
              href={downloadUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-semibold text-primary hover:underline"
            >
              PDF 다운로드
            </a>
          ) : null}
        </header>
        {documentUrl ? (
          <InlinePdfViewer
            key={`${selected.urnId}-${documentUrl}-${pdfPage ?? "page"}`}
            src={documentUrl}
            page={pdfPage}
            highlightRect={highlightRect}
            className="h-[520px]"
          />
        ) : (
          <div className="rounded-lg border border-dashed border-border-light/70 p-4 text-sm text-text-secondaryLight dark:border-border-dark/70 dark:text-text-secondaryDark">
            연동된 PDF URL이 없어 미리보기를 표시할 수 없습니다.
          </div>
        )}
      </section>
    </div>
  );
}
