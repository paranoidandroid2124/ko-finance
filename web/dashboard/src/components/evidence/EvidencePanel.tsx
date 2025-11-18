"use client";

import { getPlanLabel } from "@/lib/planTier";

import { EvidenceDiffTabs } from "./EvidenceDiffTabs";
import { EvidencePanelStoreProvider } from "./EvidencePanelStore";
import { EvidenceList } from "./EvidenceList";
import { EvidencePdfPanel } from "./EvidencePdfPanel";
import type { EvidencePanelProps, EvidenceItem, PlanTier } from "./types";
import { useEvidencePanelController } from "./useEvidencePanelController";

export function EvidencePanel(props: EvidencePanelProps) {
  const initialSelected = props.selectedUrnId ?? props.items[0]?.urnId;
  return (
    <EvidencePanelStoreProvider initialState={{ selectedUrnId: initialSelected, diffActive: props.diffActive ?? false }}>
      <EvidencePanelContent {...props} initialSelectedUrn={initialSelected} />
    </EvidencePanelStoreProvider>
  );
}

type EvidencePanelContentProps = EvidencePanelProps & { initialSelectedUrn?: string };

function EvidencePanelContent({
  planTier,
  status,
  items,
  selectedUrnId,
  initialSelectedUrn,
  inlinePdfEnabled = true,
  pdfUrl,
  pdfDownloadUrl,
  diffEnabled,
  diffActive: diffActiveProp,
  removedItems,
  onSelectEvidence,
  onHoverEvidence,
  onRequestOpenPdf,
  onRequestUpgrade,
  onToggleDiff,
}: EvidencePanelContentProps) {
  const controller = useEvidencePanelController({
    items,
    selectedUrnId,
    initialSelectedUrn,
    inlinePdfEnabled,
    pdfUrl,
    diffActiveProp,
    onSelectEvidence,
    onHoverEvidence,
    onToggleDiff,
  });

  return (
    <section className="grid h-full gap-4 rounded-xl border border-border-light bg-white/80 p-4 shadow-card transition-colors transition-motion-medium dark:border-border-dark dark:bg-background-cardDark/80">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase text-primary">Evidence 상태</p>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{renderStatusCopy(status)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
          <span className="rounded-md border border-border-light px-2 py-1 font-semibold uppercase dark:border-border-dark">
            {getPlanLabel(planTier)}
          </span>
          <EvidenceDiffTabs
            diffEnabled={diffEnabled}
            removedCount={removedItems?.length}
            onToggleDiff={controller.handleDiffToggle}
          />
          {controller.activeItem && onRequestOpenPdf ? (
            <button
              type="button"
              className="rounded-md border border-border-light px-2 py-1 font-semibold text-text-secondaryLight transition-motion-fast hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary"
              onClick={() => onRequestOpenPdf(controller.activeItem!.urnId)}
            >
              원문 PDF에서 보기
            </button>
          ) : null}
        </div>
      </header>

      {renderAnchorMismatchBanner(status, controller.activeItem, pdfUrl)}

      <div className="grid gap-4 md:grid-cols-2">
        <EvidenceList
          status={status}
          items={items}
          activeUrn={controller.activeUrn}
          diffActive={controller.resolvedDiffActive}
          planTier={planTier}
          bindObserver={controller.bindObserver}
          onSelect={controller.handleSelect}
          onHover={onHoverEvidence}
          onRequestUpgrade={onRequestUpgrade}
          removedItems={removedItems}
        />
        <EvidencePdfPanel
          planTier={planTier}
          activeItem={controller.activeItem}
          inlinePdfEnabled={inlinePdfEnabled}
          pdfUrl={pdfUrl}
          pdfDownloadUrl={pdfDownloadUrl}
          pdfStatus={controller.pdfStatus}
          pdfError={controller.pdfError}
          pdfPage={controller.pdfPage}
          highlightRect={controller.highlightRect ?? undefined}
          onRequestUpgrade={onRequestUpgrade}
          onRequestOpenPdf={onRequestOpenPdf}
        />
      </div>
    </section>
  );
}


function renderStatusCopy(status: EvidencePanelProps["status"]) {
  switch (status) {
    case "loading":
      return "근거를 차분히 모으는 중이에요…";
    case "empty":
      return "아직 보여드릴 근거가 없어요.";
    case "anchor-mismatch":
      return "하이라이트 위치를 찾지 못했어요. 원문을 바로 열어 확인해 주세요.";
    default:
      return "챗봇이 참고한 문장을 함께 살펴봐요.";
  }
}


function renderAnchorMismatchBanner(status: EvidencePanelProps["status"], activeItem?: EvidenceItem, pdfUrl?: string | null) {
  if (status !== "anchor-mismatch" || !activeItem) {
    return null;
  }
  return (
    <div className="rounded-lg border border-amber-400/60 bg-amber-50/60 px-4 py-3 text-xs text-amber-700 dark:border-amber-300/40 dark:bg-amber-400/10 dark:text-amber-100">
      <p className="font-semibold">PDF 하이라이트 위치를 찾지 못했어요.</p>
      <p className="mt-1">
        문장이 포함된 영역을 찾는 데 실패했어요. <strong>원문 새 창에서 보기</strong>를 눌러 직접 확인해 주세요.
        {pdfUrl ? " PDF 뷰어가 열리지 않는다면 새로고침 후 다시 시도해 주세요." : ""}
      </p>
    </div>
  );
}


export type { EvidenceItem as EvidencePanelItem } from "./types";
