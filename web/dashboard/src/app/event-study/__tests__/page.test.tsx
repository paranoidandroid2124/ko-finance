import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/dynamic", () => {
  return {
    __esModule: true,
    default: () => () => <div data-testid="mock-chart" />,
  };
});

const windowStub = {
  defaultKey: "window_short",
  windows: [{ key: "window_short", label: "[-5,+5]", start: -5, end: 5, description: null }],
};

const metricsStub = {
  windowLabel: "[-5,+5]",
  windowKey: "window_short",
  start: -5,
  end: 5,
  eventType: "BUYBACK",
  ticker: "TEST",
  capBucket: null,
  scope: "market",
  significance: 0.1,
  n: 0,
  hitRate: 0,
  meanCaar: 0,
  ciLo: 0,
  ciHi: 0,
  pValue: 1,
  aar: [],
  caar: [],
  dist: [],
  events: {
    total: 0,
    limit: 50,
    offset: 0,
    windowEnd: 5,
    events: [],
  },
};

vi.mock("@/hooks/useEventStudy", () => ({
  useEventStudyWindows: () => ({ data: windowStub, isLoading: false }),
  useEventStudyMetrics: () => ({
    data: metricsStub,
    isLoading: false,
    isFetching: false,
    isError: false,
    error: null,
  }),
}));

vi.mock("@/components/onboarding/OnboardingModal", () => {
  const Mock = () => null;
  return {
    __esModule: true,
    default: Mock,
    OnboardingModal: Mock,
  };
});

vi.mock("@/components/layout/AppShell", () => {
  const MockShell = ({ children }: { children: React.ReactNode }) => <div data-testid="app-shell">{children}</div>;
  return {
    __esModule: true,
    default: MockShell,
    AppShell: MockShell,
  };
});

import EventStudyPage from "../page";

describe("EventStudyPage", () => {
  it("renders the empty state without crashing", () => {
    render(<EventStudyPage />);
    expect(screen.getByText("분석할 티커를 입력해주세요")).toBeInTheDocument();
  });
});
