import React from "react";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ChatPage from "@/app/chat/page";
import { useChatStore, type ChatSession } from "@/store/chatStore";
import { createSession as createSessionApi } from "@/lib/chatApi";
import { renderWithProviders } from "./testUtils";
import { resetChatStores } from "./setupTests";

const searchParamsState = { value: "" };
const replaceMock = vi.fn();
const pushMock = vi.fn();
const PATHNAME = "/chat";

vi.mock("next/navigation", () => ({
  useSearchParams: () => {
    const params = new URLSearchParams(searchParamsState.value);
    return {
      get: (key: string) => params.get(key),
    };
  },
  useRouter: () => ({
    replace: replaceMock,
    push: pushMock,
  }),
  usePathname: () => PATHNAME,
}));

vi.mock("@/components/layout/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div data-testid="app-shell">{children}</div>,
}));

vi.mock("@/components/chat/ChatHistoryList", () => ({
  ChatHistoryList: ({
    sessions,
    selectedId,
    onSelect,
    onNewSession,
  }: {
    sessions: { id: string; title: string; updatedAt: string }[];
    selectedId?: string;
    onSelect?: (id: string) => void;
    onNewSession?: () => void;
  }) => (
    <div data-testid="history">
      <div data-testid="selected">{selectedId ?? "none"}</div>
      {sessions.map((session) => (
        <button key={session.id} onClick={() => onSelect?.(session.id)}>
          select-{session.id}
        </button>
      ))}
      <button onClick={() => onNewSession?.()}>new-session</button>
    </div>
  ),
}));

vi.mock("@/components/chat/ChatInput", () => ({
  ChatInput: ({ onSubmit }: { onSubmit?: (value: string) => void }) => (
    <button onClick={() => onSubmit?.("user question")}>send-message</button>
  ),
}));

vi.mock("@/components/chat/ChatMessage", () => ({
  ChatMessageBubble: ({ content }: { content: string }) => <div>{content}</div>,
}));

vi.mock("@/components/chat/ChatContextPanel", () => ({
  ChatContextPanel: () => <aside data-testid="context-panel" />,
}));

const emptyEvidence: ChatSession["evidence"] = {
  status: "idle",
  items: [],
  activeId: undefined,
  confidence: undefined,
  documentTitle: undefined,
  documentUrl: undefined,
};

const idleTelemetry: ChatSession["telemetry"] = {
  guardrail: { status: "idle" },
  metrics: { status: "idle", items: [] },
};

const setSearchParams = (value: string) => {
  searchParamsState.value = value;
};

const withDefaults = (session: Omit<ChatSession, "messagesLoaded" | "evidence" | "telemetry">): ChatSession => ({
  ...session,
  messagesLoaded: session.messages.length > 0,
  evidence: { ...emptyEvidence },
  telemetry: { ...idleTelemetry },
});

describe("ChatPage", () => {
  beforeEach(() => {
    resetChatStores();
    setSearchParams("");
    replaceMock.mockClear();
    pushMock.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  it("activates session from query parameter", () => {
    const existingSession = withDefaults({
      id: "chat-100",
      title: "�,,�.~A",
      updatedAt: "��c�,^",
      context: { type: "custom" },
      messages: [
        {
          id: "msg-1",
          role: "assistant",
          content: "existing message",
          timestamp: "09:00",
        },
      ],
    });

    useChatStore.setState({ sessions: [existingSession], activeSessionId: null, hydrated: true, loading: false, error: null });
    setSearchParams("session=chat-100");

    renderWithProviders(<ChatPage />);

    expect(screen.getByText("existing message")).toBeInTheDocument();
  });

  it("creates a new session from history control", async () => {
    renderWithProviders(<ChatPage />);

    fireEvent.click(screen.getByText("new-session"));

    await waitFor(() => {
      expect(useChatStore.getState().sessions.length).toBeGreaterThan(0);
    });
    await waitFor(() => {
      expect(pushMock).toHaveBeenCalled();
    });
    const targetPath = pushMock.mock.calls.at(-1)?.[0];
    expect(targetPath).toContain(`${PATHNAME}?`);
    expect(targetPath).toContain("session=");
  });

  it("appends user and assistant messages on send", async () => {
    const apiSession = await createSessionApi({ title: "existing session" });
    const session = {
      ...withDefaults({
        id: apiSession.id,
        title: apiSession.title ?? "existing session",
        updatedAt: apiSession.updated_at ?? new Date().toISOString(),
        context: { type: "custom" },
        messages: [],
      }),
      version: apiSession.version ?? 1,
    };

    useChatStore.setState({ sessions: [session], activeSessionId: session.id, hydrated: true, loading: false, error: null });
    setSearchParams(`session=${session.id}`);
    renderWithProviders(<ChatPage />);

    fireEvent.click(screen.getByText("send-message"));

    await waitFor(() => {
      const updated = useChatStore.getState().sessions.find((item) => item.id === session.id);
      expect(updated?.messages.filter((message) => message.role === "user").length).toBe(1);
      expect(updated?.messages.filter((message) => message.role === "assistant").length).toBeGreaterThanOrEqual(1);
    });

    expect(pushMock).not.toHaveBeenCalledWith(expect.stringContaining("undefined"));
  });
});
