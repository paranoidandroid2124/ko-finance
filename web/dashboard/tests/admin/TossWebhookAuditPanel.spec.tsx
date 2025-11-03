import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TossWebhookAuditPanel } from "@/components/admin/TossWebhookAuditPanel";

const refetchMock = vi.fn();
const hookMock = vi.fn();

vi.mock("@/hooks/useAdminSession", () => ({
  useAdminSession: () => ({
    data: { actor: "ops@kfinance.ai", issuedAt: new Date().toISOString(), tokenHint: null },
    isLoading: false,
    isUnauthorized: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

vi.mock("@/hooks/useAdminQuickActions", () => ({
  useTossWebhookAudit: (...args: unknown[]) => hookMock(...args),
  usePlanQuickAdjust: vi.fn(),
}));

vi.mock("@/lib/adminApi", () => ({
  requestTossWebhookReplay: vi.fn(),
}));

describe("TossWebhookAuditPanel", () => {
  it("shows empty state when there are no entries", () => {
    hookMock.mockReturnValue({ data: [], isLoading: false, refetch: refetchMock, isFetching: false });

    render(<TossWebhookAuditPanel />);

    expect(
      screen.getByText("최근 감사 로그가 아직 없어요. Toss 웹훅이 도착하면 이곳에서 바로 확인하실 수 있어요."),
    ).toBeInTheDocument();
  });

  it("renders audit rows when data is available", () => {
    hookMock.mockReturnValue({
      data: [
        {
          loggedAt: "2025-01-01T00:00:00+00:00",
          result: "processed",
          message: null,
          context: { order_id: "kfinance-pro-001", status: "DONE", transmission_id: "abc" },
        },
      ],
      isLoading: false,
      refetch: refetchMock,
      isFetching: false,
    });

    render(<TossWebhookAuditPanel />);

    expect(screen.getByText("kfinance-pro-001")).toBeInTheDocument();
    expect(screen.getByText("processed")).toBeInTheDocument();
  });
});
