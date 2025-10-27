'use client';

import { create } from 'zustand';
import type { EvidencePanelItem } from '@/components/evidence';
import type { TimelineSparklinePoint } from '@/components/company/TimelineSparkline';
import { logEvent } from '@/lib/telemetry';

type EvidenceWorkspaceState = {
  evidenceItems: EvidencePanelItem[];
  timelinePoints: TimelineSparklinePoint[];
  pdfUrl?: string | null;
  pdfDownloadUrl?: string | null;
  selectedEvidenceUrn?: string;
  hoveredEvidenceUrn?: string;
  selectedTimelineDate?: string;
  hoveredTimelineDate?: string;
  setEvidence: (
    items: EvidencePanelItem[],
    options?: { pdfUrl?: string | null; pdfDownloadUrl?: string | null; selectedUrnId?: string }
  ) => void;
  setTimeline: (points: TimelineSparklinePoint[]) => void;
  selectEvidence: (urnId: string) => void;
  hoverEvidence: (urnId: string | undefined) => void;
  selectTimelinePoint: (date: string, options?: { linkedEvidence?: string[] }) => void;
  hoverTimelinePoint: (date: string | undefined, options?: { linkedEvidence?: string[] }) => void;
  reset: () => void;
};

const INITIAL_STATE: Omit<EvidenceWorkspaceState, 'setEvidence' | 'setTimeline' | 'selectEvidence' | 'hoverEvidence' | 'selectTimelinePoint' | 'hoverTimelinePoint' | 'reset'> = {
  evidenceItems: [],
  timelinePoints: [],
  pdfUrl: undefined,
  pdfDownloadUrl: undefined,
  selectedEvidenceUrn: undefined,
  hoveredEvidenceUrn: undefined,
  selectedTimelineDate: undefined,
  hoveredTimelineDate: undefined,
};

export const useEvidenceWorkspaceStore = create<EvidenceWorkspaceState>((set, get) => ({
  ...INITIAL_STATE,

  setEvidence(items, options) {
    set((state) => ({
      evidenceItems: items,
      pdfUrl: options?.pdfUrl,
      pdfDownloadUrl: options?.pdfDownloadUrl,
      selectedEvidenceUrn:
        options?.selectedUrnId ??
        (items.some((item) => item.urnId === state.selectedEvidenceUrn)
          ? state.selectedEvidenceUrn
          : items[0]?.urnId),
    }));
  },

  setTimeline(points) {
    set({
      timelinePoints: points,
      selectedTimelineDate: points[points.length - 1]?.date,
    });
  },

  selectEvidence(urnId) {
    set((state) => {
      if (state.selectedEvidenceUrn === urnId) {
        return null;
      }
      const evidence = state.evidenceItems.find((item) => item.urnId === urnId);
      if (evidence) {
        logEvent('rag.evidence_view', {
          urnId,
          section: evidence.section,
          pageNumber: evidence.pageNumber,
          sourceReliability: evidence.sourceReliability,
        });
      }

      const linkedPoint = state.timelinePoints.find((point) => (point.evidenceUrnIds ?? []).includes(urnId));
      return {
        selectedEvidenceUrn: urnId,
        selectedTimelineDate: linkedPoint?.date ?? state.selectedTimelineDate,
      };
    });
  },

  hoverEvidence(urnId) {
    set({ hoveredEvidenceUrn: urnId });
  },

  selectTimelinePoint(date, options) {
    const { evidenceUrnIds } = options ?? {};
    set((state) => {
      const firstEvidence = (evidenceUrnIds ?? []).find((urn) =>
        state.evidenceItems.some((item) => item.urnId === urn),
      );
      const timelinePoint = state.timelinePoints.find((point) => point.date === date);
      logEvent('timeline.interact', {
        action: 'select',
        date,
        evidenceCount: timelinePoint?.evidenceUrnIds?.length ?? 0,
        eventType: timelinePoint?.eventType,
      });
      return {
        selectedTimelineDate: date,
        selectedEvidenceUrn: firstEvidence ?? state.selectedEvidenceUrn,
      };
    });
  },

  hoverTimelinePoint(date, options) {
    const { evidenceUrnIds } = options ?? {};
    const currentEvidence = get().hoveredEvidenceUrn;
    const nextEvidence = evidenceUrnIds?.[0];
    if (date) {
      logEvent('timeline.interact', {
        action: 'hover',
        date,
        evidenceCount: evidenceUrnIds?.length ?? 0,
      });
    }
    set({
      hoveredTimelineDate: date,
      hoveredEvidenceUrn: nextEvidence ?? currentEvidence,
    });
  },

  reset() {
    set({ ...INITIAL_STATE });
  },
}));
