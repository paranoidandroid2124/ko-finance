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
  diffEnabled: boolean;
  diffActive: boolean;
  removedEvidence: EvidencePanelItem[];
  selectedEvidenceUrn?: string;
  hoveredEvidenceUrn?: string;
  selectedTimelineDate?: string;
  hoveredTimelineDate?: string;
  setEvidence: (
    items: EvidencePanelItem[],
    options?: {
      pdfUrl?: string | null;
      pdfDownloadUrl?: string | null;
      selectedUrnId?: string;
      diffEnabled?: boolean;
      diffActive?: boolean;
      removedEvidence?: EvidencePanelItem[];
    }
  ) => void;
  setTimeline: (points: TimelineSparklinePoint[]) => void;
  selectEvidence: (urnId: string) => void;
  hoverEvidence: (urnId: string | undefined) => void;
  selectTimelinePoint: (date: string, options?: { linkedEvidence?: string[] }) => void;
  hoverTimelinePoint: (date: string | undefined, options?: { linkedEvidence?: string[] }) => void;
  toggleDiff: (nextValue?: boolean) => void;
  reset: () => void;
};

const INITIAL_STATE: Omit<EvidenceWorkspaceState, 'setEvidence' | 'setTimeline' | 'selectEvidence' | 'hoverEvidence' | 'selectTimelinePoint' | 'hoverTimelinePoint' | 'toggleDiff' | 'reset'> = {
  evidenceItems: [],
  timelinePoints: [],
  pdfUrl: undefined,
  pdfDownloadUrl: undefined,
  diffEnabled: false,
  diffActive: false,
  removedEvidence: [],
  selectedEvidenceUrn: undefined,
  hoveredEvidenceUrn: undefined,
  selectedTimelineDate: undefined,
  hoveredTimelineDate: undefined,
};

export const useEvidenceWorkspaceStore = create<EvidenceWorkspaceState>((set, get) => ({
  ...INITIAL_STATE,

  setEvidence(items, options) {
    set((state) => {
      const derivedEnabled =
        options?.diffEnabled ??
        (
          items.some(
            (item) =>
              Boolean(item.diffType && item.diffType !== 'unchanged') ||
              Boolean(item.previousQuote) ||
              Boolean(item.previousSection) ||
              Boolean(item.previousPageNumber),
          ) ||
          Boolean(options?.removedEvidence?.length)
        );
      const requestedActive =
        typeof options?.diffActive === 'boolean' ? options.diffActive : state.diffActive;
      return {
        evidenceItems: items,
        pdfUrl: options?.pdfUrl,
        pdfDownloadUrl: options?.pdfDownloadUrl,
        diffEnabled: derivedEnabled,
        diffActive: derivedEnabled ? requestedActive : false,
        removedEvidence: options?.removedEvidence ?? [],
        selectedEvidenceUrn:
          options?.selectedUrnId ??
          (items.some((item) => item.urnId === state.selectedEvidenceUrn)
            ? state.selectedEvidenceUrn
            : items[0]?.urnId),
      };
    });
  },

  setTimeline(points) {
    set((state) => {
      const latestDate = points[points.length - 1]?.date;
      const selectedStillVisible =
        state.selectedTimelineDate && points.some((point) => point.date === state.selectedTimelineDate);
      const hoveredStillVisible =
        state.hoveredTimelineDate && points.some((point) => point.date === state.hoveredTimelineDate);

      return {
        timelinePoints: points,
        selectedTimelineDate: selectedStillVisible ? state.selectedTimelineDate : latestDate,
        hoveredTimelineDate: hoveredStillVisible ? state.hoveredTimelineDate : undefined,
      };
    });
  },

  selectEvidence(urnId) {
    const current = get();
    if (current.selectedEvidenceUrn === urnId) {
      return;
    }
    set((state) => {
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
        hoveredEvidenceUrn: undefined,
        hoveredTimelineDate: undefined,
      };
    });
  },

  hoverEvidence(urnId) {
    if (!urnId) {
      set({ hoveredEvidenceUrn: undefined, hoveredTimelineDate: undefined });
      return;
    }

    set((state) => {
      const linkedPoint = state.timelinePoints.find((point) => (point.evidenceUrnIds ?? []).includes(urnId));
      return {
        hoveredEvidenceUrn: urnId,
        hoveredTimelineDate: linkedPoint?.date ?? state.hoveredTimelineDate,
      };
    });
  },

  selectTimelinePoint(date, options) {
    const { linkedEvidence } = options ?? {};
    set((state) => {
      const firstEvidence = (linkedEvidence ?? []).find((urn) =>
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
        hoveredTimelineDate: undefined,
        hoveredEvidenceUrn: undefined,
      };
    });
  },

  hoverTimelinePoint(date, options) {
    const { linkedEvidence } = options ?? {};
    if (!date) {
      set({ hoveredTimelineDate: undefined, hoveredEvidenceUrn: undefined });
      return;
    }

    const state = get();
    if (state.hoveredTimelineDate !== date) {
      logEvent('timeline.interact', {
        action: 'hover',
        date,
        evidenceCount: linkedEvidence?.length ?? 0,
      });
    }

    const nextEvidence = linkedEvidence?.find((urn) =>
      state.evidenceItems.some((item) => item.urnId === urn),
    );

    set({
      hoveredTimelineDate: date,
      hoveredEvidenceUrn: nextEvidence,
    });
  },

  toggleDiff(nextValue) {
    set((state) => {
      const desired = typeof nextValue === 'boolean' ? nextValue : !state.diffActive;
      const next = state.diffEnabled ? desired : false;
      if (next !== state.diffActive) {
        logEvent('rag.evidence_diff_toggle', {
          active: next,
          enabled: state.diffEnabled,
          removedCount: state.removedEvidence.length,
        });
      }
      return { diffActive: next };
    });
  },

  reset() {
    set({ ...INITIAL_STATE });
  },
}));
