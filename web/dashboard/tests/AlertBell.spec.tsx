import React from "react";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useChatStore, type ChatSession } from "@/store/chatStore";
import { AlertBell } from "@/components/ui/AlertBell";
import { renderWithProviders } from "./testUtils";
import { resetChatStores } from "./setupTests";

const pushMock = vi.fn();
let pathnameValue = "/dashboard";

const overviewMock = vi.fn();
const alertRulesMock = vi.fn();
const updateRuleMock = vi.fn();
const deleteRuleMock = vi.fn();

const basePlan = {
  planTier: "pro",
  maxAlerts: 5,
  remainingAlerts: 5,
  channels: ["email", "slack"],
  maxDailyTriggers: 10,
  defaultEvaluationIntervalMinutes: 5,
  defaultWindowMinutes: 60,
  defaultCooldownMinutes: 60,
  minEvaluationIntervalMinutes: 1,
  minCooldownMinutes: 0,
  nextEvaluationAt: null
};

const mockChannelSchema = {
  channels: [
    {
      type: "email",
      requiresTarget: true,
      targetRules: [
        { type: "required", message: "수신자를 한 명 이상 입력해주세요." },
        { type: "regex", pattern: "^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$", message: "유효하지 않은 이메일: {invalid}", collectInvalid: true },
      ],
      metadataRules: {},
    },
    {
      type: "slack",
      requiresTarget: true,
      targetRules: [
        { type: "required", message: "Webhook URL을 입력해주세요." },
        { type: "regex", pattern: "^https?://[^\\s]+$", flags: "i", message: "유효한 URL을 입력해주세요." },
      ],
      metadataRules: {},
    },
    {
      type: "telegram",
      requiresTarget: false,
      targetRules: [],
      metadataRules: {},
    },
  ],
};

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock
  }),
  usePathname: () => pathnameValue
}));

vi.mock("@/hooks/useDashboardOverview", () => ({
  useDashboardOverview: () => overviewMock()
}));

vi.mock("@/hooks/useAlerts", () => ({
  useAlertRules: () => alertRulesMock(),
  useAlertChannelSchema: () => ({
    data: mockChannelSchema,
    isLoading: false,
  }),
  useCreateAlertRule: () => ({
    mutateAsync: vi.fn().mockResolvedValue({
      id: "new-rule",
      name: "새 알림",
      description: null,
      planTier: "pro"
    }),
    isPending: false
  }),
  useUpdateAlertRule: () => ({
    mutateAsync: updateRuleMock,
    isPending: false
  }),
  useDeleteAlertRule: () => ({
    mutateAsync: deleteRuleMock,
    isPending: false
  })
}));

describe("AlertBell", () => {
  beforeEach(() => {
    pushMock.mockClear();
    overviewMock.mockReset();
    alertRulesMock.mockReset();
    updateRuleMock.mockReset();
    deleteRuleMock.mockReset();
    resetChatStores();
    pathnameValue = "/dashboard";
    overviewMock.mockReturnValue({
      data: {
        alerts: []
      },
      isLoading: false,
      isError: false
    });
    const planClone = JSON.parse(JSON.stringify(basePlan));
    alertRulesMock.mockReturnValue({
      data: {
        items: [],
        plan: planClone
      },
      isLoading: false,
      isError: false
    });
    updateRuleMock.mockResolvedValue(undefined);
    deleteRuleMock.mockResolvedValue(undefined);
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

    const trigger = screen.getByRole("button", { name: "실시간 소식 패널 열기" });
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

    const trigger = screen.getByRole("button", { name: "실시간 소식 패널 열기" });
    fireEvent.focus(trigger);

    await screen.findByText("대화 메모");

    fireEvent.click(screen.getByText("새 대화 열기"));

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

  it("restores focus to create builder button after cancel", async () => {
    renderWithProviders(<AlertBell />);

    const trigger = screen.getByRole("button", { name: "실시간 소식 패널 열기" });
    fireEvent.focus(trigger);

    const createButton = await screen.findByRole("button", { name: "새 알림 만들기" });
    fireEvent.click(createButton);

    const nameField = await screen.findByLabelText("이름");
    expect(document.activeElement).toBe(nameField);

    const cancelButton = await screen.findByRole("button", { name: "취소" });
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "취소" })).not.toBeInTheDocument();
    });

    await waitFor(() => {
      const refreshedCreateButton = screen.getByRole("button", { name: "새 알림 만들기" });
      expect(document.activeElement).toBe(refreshedCreateButton);
    });
  });

  it("returns focus to quick action after closing the builder from edit mode", async () => {
    const planClone = JSON.parse(JSON.stringify(basePlan));
    const sampleRule = {
      id: "rule-1",
      name: "실적 공시 알림",
      description: null,
      planTier: "pro",
      status: "active",
      condition: {
        type: "filing" as const,
        tickers: ["TEST"],
        categories: [],
        sectors: [],
        minSentiment: null
      },
      channels: [
        {
          type: "email" as const,
          target: "alerts@example.com",
          targets: ["alerts@example.com"],
          metadata: {},
          template: "default",
          label: null
        }
      ],
      messageTemplate: null,
      evaluationIntervalMinutes: 5,
      windowMinutes: 60,
      cooldownMinutes: 60,
      maxTriggersPerDay: 5,
      lastTriggeredAt: null,
      lastEvaluatedAt: null,
      throttleUntil: null,
      errorCount: 0,
      extras: {},
      createdAt: null,
      updatedAt: null
    };
    alertRulesMock.mockReturnValue({
      data: {
        items: [sampleRule],
        plan: { ...planClone, remainingAlerts: 4 }
      },
      isLoading: false,
      isError: false
    });

    renderWithProviders(<AlertBell />);

    const trigger = screen.getByRole("button", { name: "실시간 소식 패널 열기" });
    fireEvent.focus(trigger);

    const editButton = await screen.findByRole("button", { name: "알림 수정" });
    fireEvent.click(editButton);

    const nameField = await screen.findByLabelText("이름");
    await waitFor(() => {
      expect(document.activeElement).toBe(nameField);
    });

    const cancelButton = await screen.findByRole("button", { name: "취소" });
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "취소" })).not.toBeInTheDocument();
    });

    await waitFor(() => {
      const refreshedEditButton = screen.getByRole("button", { name: "알림 수정" });
      expect(document.activeElement).toBe(refreshedEditButton);
    });
  });
});
