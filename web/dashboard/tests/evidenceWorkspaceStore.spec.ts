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
});
