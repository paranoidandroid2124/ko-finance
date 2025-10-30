import { render, screen } from "@testing-library/react";
import { beforeEach, afterEach, describe, expect, it } from "vitest";

import { PlanSummaryCard } from "@/components/plan/PlanSummaryCard";
import { usePlanStore } from "@/store/planStore";

const initialState = usePlanStore.getState();

describe("PlanSummaryCard", () => {
  beforeEach(() => {
    usePlanStore.setState(initialState, true);
  });

  afterEach(() => {
    usePlanStore.setState(initialState, true);
  });

  it("shows tier label, entitlements, and quota values", () => {
    usePlanStore.setState({
      planTier: "enterprise",
      expiresAt: "2026-01-05T00:00:00+00:00",
      entitlements: ["search.export", "timeline.full"],
      quota: {
        chatRequestsPerDay: null,
        ragTopK: 12,
        selfCheckEnabled: true,
        peerExportRowLimit: null,
      },
      initialized: true,
      loading: false,
      error: undefined,
    });

    render(<PlanSummaryCard />);

    expect(screen.getByText("Enterprise")).toBeInTheDocument();
    expect(screen.getByText("데이터 내보내기")).toBeInTheDocument();
    expect(screen.getByText("전체 타임라인")).toBeInTheDocument();
    expect(screen.getAllByText("무제한").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("12개")).toBeInTheDocument();
  });
});
