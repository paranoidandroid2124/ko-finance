import { describe, expect, it, beforeEach, vi } from "vitest";
import { useEvidenceWorkspaceStore } from "@/store/evidenceWorkspaceStore";
import * as telemetry from "@/lib/telemetry";

const baseState = {
  evidenceItems: [],
  timelinePoints: [],
  pdfUrl: undefined,
  pdfDownloadUrl: undefined,
  selectedEvidenceUrn: undefined,
  hoveredEvidenceUrn: undefined,
  selectedTimelineDate: undefined,
  hoveredTimelineDate: undefined,
  diffEnabled: false,
  diffActive: false,
  removedEvidence: [],
} as const;

const sampleEvidence = [
  {
    urnId: "urn:sample:0",
    quote: "Placeholder",
    section: "Intro",
    pageNumber: 1,
    anchor: undefined,
    selfCheck: undefined,
    sourceReliability: "medium" as const,
    createdAt: "2025-01-01T00:00:00Z",
    chunkId: "chunk-0",
  },
  {
    urnId: "urn:sample:1",
    quote: "Sample quote",
    section: "Sample Section",
    pageNumber: 5,
    anchor: undefined,
    selfCheck: undefined,
    sourceReliability: "high" as const,
    createdAt: "2025-01-01T00:00:00Z",
    chunkId: "chunk-1",
  },
] as const;

const sampleTimeline = [
  {
    date: "2025-01-01",
    sentimentZ: 0.2,
    priceClose: undefined,
    volume: undefined,
    eventType: "Sample Section",
    evidenceUrnIds: ["urn:sample:1"],
  },
] as const;

describe("evidenceWorkspaceStore telemetry", () => {
  const logSpy = vi.spyOn(telemetry, "logEvent").mockImplementation(() => {});

  beforeEach(() => {
    useEvidenceWorkspaceStore.setState(baseState);
    logSpy.mockClear();
  });

  it("logs rag.evidence_view when selecting evidence", () => {
    const store = useEvidenceWorkspaceStore.getState();
    store.setEvidence(sampleEvidence.slice(), { selectedUrnId: sampleEvidence[0].urnId });

    store.selectEvidence(sampleEvidence[1].urnId);

    expect(logSpy).toHaveBeenCalledWith(
      "rag.evidence_view",
      expect.objectContaining({
        urnId: sampleEvidence[1].urnId,
        section: "Sample Section",
        pageNumber: 5,
        sourceReliability: "high",
      }),
    );
  });

  it("logs timeline.interact when selecting timeline point", () => {
    const store = useEvidenceWorkspaceStore.getState();
    store.setEvidence(sampleEvidence.slice());
    store.setTimeline(sampleTimeline.slice());

    store.selectTimelinePoint("2025-01-01", { linkedEvidence: ["urn:sample:1"] });

    expect(logSpy).toHaveBeenCalledWith(
      "timeline.interact",
      expect.objectContaining({
        action: "select",
        date: "2025-01-01",
        evidenceCount: 1,
        eventType: "Sample Section",
      }),
    );
  });

  it("logs timeline.interact on hover", () => {
    const store = useEvidenceWorkspaceStore.getState();
    store.setEvidence(sampleEvidence.slice());
    store.setTimeline(sampleTimeline.slice());

    store.hoverTimelinePoint("2025-01-01", { linkedEvidence: ["urn:sample:1"] });

    expect(logSpy).toHaveBeenCalledWith(
      "timeline.interact",
      expect.objectContaining({
        action: "hover",
        date: "2025-01-01",
      }),
    );
  });

  it("logs diff toggle events", () => {
    const store = useEvidenceWorkspaceStore.getState();
    store.setEvidence(sampleEvidence.slice(), { diffEnabled: true });
    logSpy.mockClear();

    store.toggleDiff(true);

    expect(useEvidenceWorkspaceStore.getState().diffActive).toBe(true);
    expect(logSpy).toHaveBeenCalledWith(
      "rag.evidence_diff_toggle",
      expect.objectContaining({
        active: true,
        enabled: true,
      }),
    );
  });

  it("syncs hovered evidence with timeline date", () => {
    const store = useEvidenceWorkspaceStore.getState();
    store.setEvidence(sampleEvidence.slice());
    store.setTimeline(sampleTimeline.slice());

    store.hoverEvidence("urn:sample:1");

    const state = useEvidenceWorkspaceStore.getState();
    expect(state.hoveredTimelineDate).toBe("2025-01-01");
    expect(state.hoveredEvidenceUrn).toBe("urn:sample:1");
  });

  it("clears hover state when leaving timeline", () => {
    const store = useEvidenceWorkspaceStore.getState();
    store.setEvidence(sampleEvidence.slice());
    store.setTimeline(sampleTimeline.slice());

    store.hoverTimelinePoint("2025-01-01", { linkedEvidence: ["urn:sample:1"] });
    store.hoverTimelinePoint(undefined);

    const state = useEvidenceWorkspaceStore.getState();
    expect(state.hoveredTimelineDate).toBeUndefined();
    expect(state.hoveredEvidenceUrn).toBeUndefined();
  });

  it("keeps selected timeline date if still present after refresh", () => {
    const store = useEvidenceWorkspaceStore.getState();
    store.setEvidence(sampleEvidence.slice());
    store.setTimeline(sampleTimeline.slice());
    store.selectTimelinePoint("2025-01-01", { linkedEvidence: ["urn:sample:1"] });

    store.setTimeline([
      ...sampleTimeline,
      {
        date: "2025-01-02",
        sentimentZ: 0,
        priceClose: 1000,
        volume: 200,
        eventType: "Other",
        evidenceUrnIds: [],
      },
    ]);

    const state = useEvidenceWorkspaceStore.getState();
    expect(state.selectedTimelineDate).toBe("2025-01-01");
  });
});
