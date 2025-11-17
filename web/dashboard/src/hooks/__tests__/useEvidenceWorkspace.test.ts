import { describe, expect, it } from "vitest";

import type { EvidenceWorkspaceResponsePayload } from "@/lib/evidenceApi";
import { mapWorkspacePayload } from "../useEvidenceWorkspace";

describe("useEvidenceWorkspace mapping", () => {
  it("includes removed evidence entries", () => {
    const payload: EvidenceWorkspaceResponsePayload = {
      traceId: "trace-123",
      evidence: [
        {
          urn_id: "urn:current",
          quote: "current quote",
        },
      ],
      diff: {
        enabled: true,
        removed: [
          {
            urn_id: "urn:removed",
            quote: "old quote",
            diff_type: "removed",
          },
        ],
      },
      pdfUrl: null,
      pdfDownloadUrl: null,
      selectedUrnId: null,
    };

    const result = mapWorkspacePayload(payload);
    expect(result.diffEnabled).toBe(true);
    expect(result.removed).toHaveLength(1);
    expect(result.removed[0].urnId).toBe("urn:removed");
    expect(result.removed[0].diffType).toBe("removed");
  });
});
