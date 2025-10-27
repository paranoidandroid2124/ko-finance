"use client";

import { useEffect } from "react";
import { EvidencePanel, type EvidencePanelItem, type PlanTier } from "@/components/evidence/EvidencePanel";
import { TimelineSparkline, type TimelineSparklinePoint } from "@/components/company/TimelineSparkline";
import { useEvidenceWorkspaceStore } from "@/store/evidenceWorkspaceStore";

type EvidenceWorkspaceProps = {
  planTier: PlanTier;
  evidence: EvidencePanelItem[];
  timeline: TimelineSparklinePoint[];
  pdfUrl?: string | null;
  pdfDownloadUrl?: string | null;
  evidenceStatus?: "loading" | "ready" | "empty" | "anchor-mismatch";
  timelineLocked?: boolean;
  onRequestUpgrade?: () => void;
  diffEnabled?: boolean;
  diffActive?: boolean;
  diffRemoved?: EvidencePanelItem[];
};

export function EvidenceWorkspace({
  planTier,
  evidence,
  timeline,
  pdfUrl,
  pdfDownloadUrl,
  evidenceStatus = "ready",
  timelineLocked = false,
  onRequestUpgrade,
  diffEnabled,
  diffActive,
  diffRemoved,
}: EvidenceWorkspaceProps) {
  const {
    evidenceItems,
    timelinePoints,
    selectedEvidenceUrn,
    selectedTimelineDate,
    hoveredTimelineDate,
    pdfUrl: storePdfUrl,
    pdfDownloadUrl: storePdfDownloadUrl,
    diffEnabled: storeDiffEnabled,
    diffActive: storeDiffActive,
    removedEvidence,
    setEvidence,
    setTimeline,
    selectEvidence,
    hoverEvidence,
    selectTimelinePoint,
    hoverTimelinePoint,
    toggleDiff,
  } = useEvidenceWorkspaceStore();

  useEffect(() => {
    setEvidence(evidence, {
      pdfUrl,
      pdfDownloadUrl,
      diffEnabled,
      diffActive,
      removedEvidence: diffRemoved,
    });
  }, [evidence, pdfUrl, pdfDownloadUrl, diffEnabled, diffActive, diffRemoved, setEvidence]);

  useEffect(() => {
    setTimeline(timeline);
  }, [timeline, setTimeline]);

  const highlightDate = hoveredTimelineDate ?? selectedTimelineDate;
  const activeTimelinePoint = timelinePoints.find((point) => point.date === highlightDate) ?? null;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,0.55fr)_minmax(0,0.45fr)] xl:grid-cols-[minmax(0,0.5fr)_minmax(0,0.5fr)]">
      <EvidencePanel
        planTier={planTier}
        status={evidenceStatus === "ready" && evidenceItems.length === 0 ? "empty" : evidenceStatus}
        items={evidenceItems}
        selectedUrnId={selectedEvidenceUrn}
        inlinePdfEnabled={Boolean(storePdfUrl)}
        pdfUrl={storePdfUrl}
        pdfDownloadUrl={storePdfDownloadUrl}
        diffEnabled={storeDiffEnabled}
        diffActive={storeDiffActive}
        onSelectEvidence={(urnId) => selectEvidence(urnId)}
        onHoverEvidence={(urnId) => hoverEvidence(urnId)}
        onToggleDiff={toggleDiff}
        removedItems={removedEvidence}
        onRequestUpgrade={onRequestUpgrade}
      />
      <div className="flex flex-col gap-4">
        <TimelineSparkline
          planTier={planTier}
          points={timelinePoints}
          locked={timelineLocked}
          highlightDate={highlightDate}
          onSelectPoint={(point) =>
            selectTimelinePoint(point.date, { linkedEvidence: point.evidenceUrnIds })
          }
          onHoverPoint={(point) => {
            if (point) {
              hoverTimelinePoint(point.date, { linkedEvidence: point.evidenceUrnIds });
              return;
            }
            hoverTimelinePoint(undefined);
          }}
        />
        {activeTimelinePoint ? (
          <div className="rounded-lg border border-border-light bg-background-cardLight p-3 text-xs text-text-secondaryLight dark:border-border-dark dark:bg-background-cardDark dark:text-text-secondaryDark">
            <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
              {activeTimelinePoint.date}
            </p>
            <dl className="mt-2 space-y-1">
              <div className="flex justify-between">
                <dt>감성 온도</dt>
                <dd>{activeTimelinePoint.sentimentZ?.toFixed(2) ?? "–"}</dd>
              </div>
              <div className="flex justify-between">
                <dt>가격</dt>
                <dd>
                  {typeof activeTimelinePoint.priceClose === "number"
                    ? activeTimelinePoint.priceClose.toLocaleString()
                    : "–"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt>거래량</dt>
                <dd>
                  {typeof activeTimelinePoint.volume === "number"
                    ? activeTimelinePoint.volume.toLocaleString()
                    : "–"}
                </dd>
              </div>
              {activeTimelinePoint.eventType ? (
                <div className="flex justify-between">
                  <dt>기록된 소식</dt>
                  <dd>{activeTimelinePoint.eventType}</dd>
                </div>
              ) : null}
              {activeTimelinePoint.evidenceUrnIds && activeTimelinePoint.evidenceUrnIds.length ? (
                <div className="flex justify-between">
                  <dt>함께 읽을 문장</dt>
                  <dd>{activeTimelinePoint.evidenceUrnIds.length}개</dd>
                </div>
              ) : null}
            </dl>
          </div>
        ) : null}
      </div>
    </div>
  );
}
