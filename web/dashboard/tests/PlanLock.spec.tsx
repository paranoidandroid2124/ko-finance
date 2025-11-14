import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PlanLock } from "@/components/ui/PlanLock";
import { usePlanStore } from "@/store/planStore";
import { renderWithProviders } from "./testUtils";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

const mockUsePlanCatalog = vi.fn();
vi.mock("@/hooks/usePlanCatalog", () => ({
  usePlanCatalog: () => mockUsePlanCatalog(),
}));

const mockUsePlanTrialCta = vi.fn();
vi.mock("@/hooks/usePlanTrialCta", () => ({
  usePlanTrialCta: () => mockUsePlanTrialCta(),
}));

const initialPlanState = usePlanStore.getState();

describe("PlanLock", () => {
  beforeEach(() => {
    usePlanStore.setState(initialPlanState, true);
    pushMock.mockReset();
    mockUsePlanCatalog.mockReturnValue({ catalog: null });
  });

  it("starts the Pro trial when CTA is clicked", async () => {
    const user = userEvent.setup();
    const startTrialCta = vi.fn().mockResolvedValue(undefined);
    mockUsePlanTrialCta.mockReturnValue({
      trialAvailable: true,
      trialStarting: false,
      startTrialCta,
    });
    usePlanStore.setState({ planTier: "free" });

    renderWithProviders(<PlanLock requiredTier="pro" />);

    const cta = screen.getByRole("button", { name: "7일 무료 체험" });
    await user.click(cta);

    expect(startTrialCta).toHaveBeenCalledWith({ source: "plan-lock" });
  });

  it("swallows errors coming from trial start failures", async () => {
    const user = userEvent.setup();
    const startTrialCta = vi.fn().mockRejectedValue(new Error("network"));
    mockUsePlanTrialCta.mockReturnValue({
      trialAvailable: true,
      trialStarting: false,
      startTrialCta,
    });
    usePlanStore.setState({ planTier: "free" });

    renderWithProviders(<PlanLock requiredTier="pro" />);

    const cta = screen.getByRole("button", { name: "7일 무료 체험" });
    await expect(user.click(cta)).resolves.toBeUndefined();

    expect(startTrialCta).toHaveBeenCalledWith({ source: "plan-lock" });
  });
});
