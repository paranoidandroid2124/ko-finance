import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { fireEvent, screen } from "@testing-library/react";

import { PlanSettingsForm } from "@/components/plan/PlanSettingsForm";
import { usePlanStore, type PlanContextPayload } from "@/store/planStore";
import { useToastStore } from "@/store/toastStore";
import { flushAsync, renderWithProviders } from "../testUtils";

const startCheckoutMock = vi.fn().mockResolvedValue(undefined);

vi.mock("@/hooks/useTossCheckout", () => ({
  useTossCheckout: () => ({
    isPreparing: false,
    lastError: null,
    startCheckout: startCheckoutMock,
    getPreset: (tier: string) => (tier === "free" ? null : { amount: 39000, orderName: "테스트 플랜" }),
    getTierLabel: () => "",
  }),
}));

const originalFetchPlan = usePlanStore.getState().fetchPlan;
const originalSetPlanFromServer = usePlanStore.getState().setPlanFromServer;
const originalSavePlan = usePlanStore.getState().savePlan;

describe("PlanSettingsForm", () => {
  const defaultPayload: PlanContextPayload = {
    planTier: "pro",
    expiresAt: "2026-01-01T00:00:00+00:00",
    entitlements: ["search.compare", "search.alerts"],
    featureFlags: {
      searchCompare: true,
      searchAlerts: true,
      searchExport: false,
      evidenceInlinePdf: false,
      evidenceDiff: false,
      timelineFull: false,
    },
    quota: {
      chatRequestsPerDay: 500,
      ragTopK: 6,
      selfCheckEnabled: true,
      peerExportRowLimit: 120,
    },
    updatedAt: "2025-11-01T09:00:00+00:00",
    updatedBy: "hana@kfinance.ai",
    changeNote: "초기 설정",
    checkoutRequested: false,
  };

  const resetStore = () => {
    usePlanStore.setState(
      {
        planTier: "free",
        expiresAt: null,
        entitlements: [],
        featureFlags: {
          searchCompare: false,
          searchAlerts: false,
          searchExport: false,
          evidenceInlinePdf: false,
          evidenceDiff: false,
          timelineFull: false,
        },
        quota: {
          chatRequestsPerDay: 20,
          ragTopK: 4,
          selfCheckEnabled: false,
          peerExportRowLimit: 0,
        },
        updatedAt: null,
        updatedBy: null,
        changeNote: null,
        checkoutRequested: false,
        initialized: false,
        loading: false,
        saving: false,
        error: undefined,
        saveError: undefined,
        fetchPlan: originalFetchPlan,
        setPlanFromServer: originalSetPlanFromServer,
        savePlan: originalSavePlan,
      },
      true,
    );
  };

  beforeEach(() => {
    startCheckoutMock.mockClear();
    const savePlanMock = vi.fn().mockResolvedValue({
      ...defaultPayload,
      entitlements: [...defaultPayload.entitlements, "timeline.full"],
      updatedAt: "2025-11-03T12:00:00+00:00",
      updatedBy: "sally@kfinance.ai",
      changeNote: "업데이트 테스트",
    });

    usePlanStore.setState({
      ...usePlanStore.getState(),
      ...defaultPayload,
      initialized: true,
      loading: false,
      saving: false,
      error: undefined,
      saveError: undefined,
      savePlan: savePlanMock,
    });
    useToastStore.getState().clear();
  });

  afterEach(() => {
    resetStore();
    useToastStore.getState().clear();
    vi.restoreAllMocks();
  });

  it("표시된 기본값과 마지막 저장 정보를 노출한다", () => {
    renderWithProviders(<PlanSettingsForm />);

    expect(screen.getByText(/플랜 기본값을 바로 손볼 수 있어요/)).toBeInTheDocument();
    expect(screen.getByDisplayValue("2026-01-01T00:00:00+00:00")).toBeInTheDocument();
    expect(screen.getByDisplayValue("hana@kfinance.ai")).toBeInTheDocument();
    expect(screen.getByText(/마지막 저장/)).toBeInTheDocument();
  });

  it("폼을 저장하면 store의 savePlan을 호출하고 토스트를 띄운다", async () => {
    const savePlanSpy = vi.spyOn(usePlanStore.getState(), "savePlan");
    const toastSpy = vi.spyOn(useToastStore.getState(), "show");

    renderWithProviders(<PlanSettingsForm />);

    const user = userEvent.setup();
    const triggerCheckbox = screen.getByLabelText(/토스페이먼츠 연동 준비 신호 보내기/);
    await user.click(triggerCheckbox);

    const ragTopKInput = screen.getByLabelText(/RAG Top-K/);
    fireEvent.input(ragTopKInput, { target: { value: "8" } });

    const noteInput = screen.getByPlaceholderText(/변경 이유/);
    await user.clear(noteInput);
    await user.type(noteInput, "Pro 고객 확장 테스트");

    const contactInput = screen.getByPlaceholderText(/hana@kfinance.ai/);
    await user.clear(contactInput);
    await user.type(contactInput, "sally@kfinance.ai");

    const diffCheckbox = screen.getByLabelText(/증거 Diff 비교/);
    await user.click(diffCheckbox);

    const submit = screen.getByRole("button", { name: "플랜 기본값 저장하기" });
    await user.click(submit);
    await flushAsync();

    expect(savePlanSpy).toHaveBeenCalledTimes(1);
    const payload = savePlanSpy.mock.calls[0][0];
    expect(payload.planTier).toBe("pro");
    expect(payload.triggerCheckout).toBe(true);
    expect(payload.entitlements).toContain("evidence.diff");
    expect(payload.quota.ragTopK).toBe(8);
    expect(payload.updatedBy).toBe("sally@kfinance.ai");
    expect(payload.changeNote).toBe("Pro 고객 확장 테스트");

    expect(startCheckoutMock).toHaveBeenCalledTimes(1);
    expect(startCheckoutMock).toHaveBeenCalledWith(
      expect.objectContaining({
        targetTier: "pro",
        amount: 39000,
      }),
    );

    expect(toastSpy).toHaveBeenCalled();
    expect(
      toastSpy.mock.calls.some(([config]) => config?.id === "plan-settings/checkout-request"),
    ).toBe(true);
  });
});
