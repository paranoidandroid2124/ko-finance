import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

import { PlanQuickActionsPanel } from "@/components/admin/PlanQuickActionsPanel";
import { usePlanStore } from "@/store/planStore";
import { renderWithProviders } from "../testUtils";

const initialState = usePlanStore.getState();

const mutateAsyncMock = vi.fn(async () => ({
  planTier: "enterprise",
  entitlements: ["search.compare", "search.export"],
  featureFlags: {
    searchCompare: true,
    searchAlerts: false,
    searchExport: true,
    evidenceInlinePdf: false,
    evidenceDiff: false,
    timelineFull: false,
  },
  quota: {
    chatRequestsPerDay: null,
    ragTopK: 6,
    selfCheckEnabled: true,
    peerExportRowLimit: null,
  },
  updatedAt: null,
  updatedBy: "qa-admin@kfinance.ai",
  changeNote: null,
  checkoutRequested: false,
  expiresAt: null,
}));

vi.mock("@/hooks/useAdminQuickActions", () => ({
  usePlanQuickAdjust: () => ({
    mutateAsync: mutateAsyncMock,
    isPending: false,
  }),
  useTossWebhookAudit: vi.fn(),
}));

describe("PlanQuickActionsPanel", () => {
  beforeEach(() => {
    usePlanStore.setState(initialState, true);
    usePlanStore.setState({
      planTier: "pro",
      entitlements: ["search.compare"],
      quota: {
        chatRequestsPerDay: 500,
        ragTopK: 6,
        selfCheckEnabled: true,
        peerExportRowLimit: 120,
      },
      initialized: true,
      loading: false,
      fetchPlan: async () => {},
    });
  });

  afterEach(() => {
    usePlanStore.setState(initialState, true);
    mutateAsyncMock.mockClear();
  });

  it("locks base entitlements for the selected tier", () => {
    renderWithProviders(<PlanQuickActionsPanel />);

    const compareCheckbox = screen.getByLabelText("?? ??") as HTMLInputElement;
    expect(compareCheckbox).toBeChecked();
    expect(compareCheckbox).toBeDisabled();

    const exportCheckbox = screen.getByLabelText("??? ????") as HTMLInputElement;
    expect(exportCheckbox).toBeDisabled();
  });

  it("adds enterprise entitlements and locks them when tier changes", () => {
    renderWithProviders(<PlanQuickActionsPanel />);

    const tierSelect = screen.getByLabelText("??? ?? ??");
    fireEvent.change(tierSelect, { target: { value: "enterprise" } });

    const exportCheckbox = screen.getByLabelText("??? ????") as HTMLInputElement;
    expect(exportCheckbox).toBeChecked();
    expect(exportCheckbox).toBeDisabled();
  });
});
