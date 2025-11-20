import React from "react";
import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import SettingsPage from "@/app/settings/page";
import { renderWithProviders } from "./testUtils";
import { usePlanStore, type PlanContextPayload } from "@/store/planStore";

let themeValue = "light";
const setThemeMock = vi.fn();

vi.mock("next-themes", () => ({
  useTheme: () => ({
    theme: themeValue,
    setTheme: setThemeMock
  })
}));

vi.mock("@/components/layout/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div data-testid="app-shell">{children}</div>
}));

const mockedPlan: PlanContextPayload = {
  planTier: "pro",
  expiresAt: "2025-12-31T00:00:00+00:00",
  entitlements: ["search.compare", "search.alerts", "search.export", "evidence.inline_pdf", "rag.core", "reports.event_export"],
  featureFlags: {
    searchCompare: true,
    searchAlerts: true,
    searchExport: true,
    ragCore: true,
    evidenceInlinePdf: true,
    evidenceDiff: false,
    timelineFull: false,
    reportsEventExport: true,
  },
  memoryFlags: {
    watchlist: true,
    chat: true,
  },
  quota: {
    chatRequestsPerDay: 500,
    ragTopK: 6,
    selfCheckEnabled: true,
    peerExportRowLimit: 120,
  },
};

const mockAlertPlan = {
  planTier: "pro",
  maxAlerts: 10,
  remainingAlerts: 7,
  channels: ["email", "slack"],
  maxDailyTriggers: 5,
  defaultEvaluationIntervalMinutes: 5,
  defaultWindowMinutes: 60,
  defaultCooldownMinutes: 30,
  minEvaluationIntervalMinutes: 1,
  minCooldownMinutes: 5,
  nextEvaluationAt: null,
};

vi.mock("@/hooks/useAlerts", () => ({
  useAlertRules: () => ({
    data: { items: [], plan: mockAlertPlan },
    isLoading: false,
    isError: false,
  }),
}));

describe("SettingsPage", () => {
  beforeEach(() => {
    themeValue = "light";
    setThemeMock.mockClear();
    usePlanStore.setState({
      planTier: mockedPlan.planTier,
      expiresAt: mockedPlan.expiresAt,
      entitlements: mockedPlan.entitlements,
      featureFlags: mockedPlan.featureFlags,
      memoryFlags: mockedPlan.memoryFlags,
      quota: mockedPlan.quota,
      initialized: true,
      loading: false,
      error: undefined,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("toggles theme when button is clicked", async () => {
    renderWithProviders(<SettingsPage />);

    const button = await screen.findByRole("button", { name: "다크 테마로 눈을 쉬게 하기" });
    fireEvent.click(button);

    expect(setThemeMock).toHaveBeenCalledWith("dark");
  });

  it("renders plan summary and alert overview cards", async () => {
    renderWithProviders(<SettingsPage />);

    expect(await screen.findByText(/내 플랜/)).toBeInTheDocument();
    expect(screen.getByText(/플랜에 맞춘 자동화 한도/)).toBeInTheDocument();
    expect(screen.getByText(/플랜 기본값을 바로 손볼 수 있어요/)).toBeInTheDocument();
    expect(screen.getByText(/다가오는 연동/)).toBeInTheDocument();
  });
});
