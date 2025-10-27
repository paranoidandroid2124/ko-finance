import React from "react";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useChatStore, type ChatSession } from "@/store/chatStore";
import { AlertBell } from "@/components/ui/AlertBell";
import { renderWithProviders } from "./testUtils";

const pushMock = vi.fn();
let pathnameValue = "/dashboard";

const overviewMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock
  }),
  usePathname: () => pathnameValue
}));

vi.mock("@/hooks/useDashboardOverview", () => ({
  useDashboardOverview: () => overviewMock()
}));

const resetStore = () => {
  useChatStore.setState({
    sessions: [],
    activeSessionId: null,
    hydrated: true,
    loading: false,
    error: null
  });
};

describe("AlertBell", () => {
  beforeEach(() => {
    pushMock.mockClear();
    overviewMock.mockReset();
    resetStore();
    pathnameValue = "/dashboard";
    overviewMock.mockReturnValue({
      data: {
        alerts: []
      },
      isLoading: false,
      isError: false
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("opens panel on focus and navigates when alert clicked", async () => {
    overviewMock.mockReturnValue({
      data: {
        alerts: [
          {
            id: "alert-1",
            title: "긴급 공시",
            body: "새로운 공시가 등록되었습니다.",
            timestamp: "방금 전",
            tone: "warning",
            targetUrl: "/filings/123"
          }
        ]
      },
      isLoading: false,
      isError: false
    });

    renderWithProviders(<AlertBell />);

    const trigger = screen.getByRole("button", { name: "실시간 신호 패널 열기" });
    fireEvent.focus(trigger);

    await screen.findByText("긴급 공시");

    fireEvent.click(screen.getByText("긴급 공시"));

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/filings/123");
    });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("creates new chat session and closes panel", async () => {
    const sessions: ChatSession[] = [
      {
        id: "session-1",
        title: "현재 세션",
        updatedAt: "방금 전",
        context: { type: "custom" },
        messages: [],
        messagesLoaded: false,
        lastMessageAt: null,
        version: 1,
        evidence: { status: "idle", items: [] },
        telemetry: {
          guardrail: { status: "idle" },
          metrics: { status: "idle", items: [] }
        }
      }
    ];

    useChatStore.setState({
      sessions,
      activeSessionId: "session-1",
      hydrated: true,
      loading: false,
      error: null
    });

    renderWithProviders(<AlertBell />);

    const trigger = screen.getByRole("button", { name: "실시간 신호 패널 열기" });
    fireEvent.focus(trigger);

    await screen.findByText("대화형 분석");

    fireEvent.click(screen.getByText("새 대화 시작"));

    await waitFor(() => {
      expect(useChatStore.getState().activeSessionId).toMatch(/^session-/);
    });
    const activeSessionId = useChatStore.getState().activeSessionId;

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith(`/chat?session=${activeSessionId}`);
    });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });
});

