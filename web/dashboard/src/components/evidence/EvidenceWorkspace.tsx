"use client";

import { useEffect } from "react";
import { EvidencePanel, type EvidencePanelItem } from "@/components/evidence/EvidencePanel";
import type { PlanTier } from "@/store/planStore/types";
import { useEvidenceWorkspaceStore } from "@/store/evidenceWorkspaceStore";
import { EvidenceDetailPanel } from "@/components/evidence/EvidenceDetailPanel";
import { EvidenceLayout } from "@/components/evidence/EvidenceLayout";

type EvidenceWorkspaceProps = {
  planTier: PlanTier;
  evidence: EvidencePanelItem[];
  pdfUrl?: string | null;
  pdfDownloadUrl?: string | null;
  evidenceStatus?: "loading" | "ready" | "empty" | "anchor-mismatch";
  onRequestUpgrade?: (tier: PlanTier) => void;
  diffEnabled?: boolean;
  diffActive?: boolean;
  diffRemoved?: EvidencePanelItem[];
  selectedUrnId?: string;
};

export function EvidenceWorkspace({
  planTier,
  evidence,
  pdfUrl,
  pdfDownloadUrl,
  evidenceStatus = "ready",
  onRequestUpgrade,
  diffEnabled,
  diffActive,
  diffRemoved,
  selectedUrnId,
}: EvidenceWorkspaceProps) {
  const {
    evidenceItems,
    selectedEvidenceUrn,
    pdfUrl: storePdfUrl,
    pdfDownloadUrl: storePdfDownloadUrl,
    diffEnabled: storeDiffEnabled,
    diffActive: storeDiffActive,
    removedEvidence,
    setEvidence,
    selectEvidence,
    hoverEvidence,
    toggleDiff,
  } = useEvidenceWorkspaceStore();

  useEffect(() => {
    setEvidence(evidence, {
      pdfUrl,
      pdfDownloadUrl,
      diffEnabled,
      diffActive,
      removedEvidence: diffRemoved,
      selectedUrnId,
    });
  }, [evidence, pdfUrl, pdfDownloadUrl, diffEnabled, diffActive, diffRemoved, selectedUrnId, setEvidence]);

  return (
    <EvidenceLayout
      list={
        <EvidencePanel
          planTier={planTier}
          status={evidenceStatus === "ready" && evidenceItems.length === 0 ? "empty" : evidenceStatus}
          items={evidenceItems}
          selectedUrnId={selectedEvidenceUrn}
          inlinePdfEnabled={false}
          pdfUrl={undefined}
          pdfDownloadUrl={storePdfDownloadUrl}
          diffEnabled={storeDiffEnabled}
          diffActive={storeDiffActive}
          onSelectEvidence={(urnId) => selectEvidence(urnId)}
          onHoverEvidence={(urnId) => hoverEvidence(urnId)}
          onToggleDiff={toggleDiff}
          removedItems={removedEvidence}
          onRequestUpgrade={onRequestUpgrade}
        />
      }
      detail={<EvidenceDetailPanel pdfUrl={storePdfUrl ?? pdfUrl} pdfDownloadUrl={storePdfDownloadUrl ?? pdfDownloadUrl} />}
    />
  );
}
