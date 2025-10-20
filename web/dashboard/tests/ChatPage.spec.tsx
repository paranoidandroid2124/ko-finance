import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ChatPage from "@/app/chat/page";
import { useChatStore, type ChatSession } from "@/store/chatStore";

const searchParamsState = { value: "" };

vi.mock("next/navigation", () => ({
  useSearchParams: () => {
    const params = new URLSearchParams(searchParamsState.value);
    return {
      get: (key: string) => params.get(key)
    };
  }
}));

vi.mock("@/components/layout/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div data-testid="app-shell">{children}</div>
}));

vi.mock("@/components/chat/ChatHistoryList", () => ({
  ChatHistoryList: ({
    sessions,
    selectedId,
    onSelect,
    onNewSession
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
  )
}));

vi.mock("@/components/chat/ChatInput", () => ({
  ChatInput: ({ onSubmit }: { onSubmit?: (value: string) => void }) => (
    <button onClick={() => onSubmit?.("user question")}>send-message</button>
  )
}));

vi.mock("@/components/chat/ChatMessage", () => ({
  ChatMessageBubble: ({ content }: { content: string }) => <div>{content}</div>
}));

vi.mock("@/components/chat/ChatContextPanel", () => ({
  ChatContextPanel: () => <aside data-testid="context-panel" />
}));

const resetStore = () => {
  useChatStore.setState({ sessions: [], activeSessionId: null });
};

const setSearchParams = (value: string) => {
  searchParamsState.value = value;
};

describe("ChatPage", () => {
  beforeEach(() => {
    resetStore();
    setSearchParams("");
  });

  afterEach(() => {
    cleanup();
  });

  // 정상 흐름: URL 쿼리에 전달된 세션이 있으면 해당 세션이 활성화되어야 한다.
  it("activates session from query parameter", () => {
    const existingSession: ChatSession = {
      id: "chat-100",
      title: "세션A",
      updatedAt: "방금",
      messages: [
        {
          id: "msg-1",
          role: "assistant" as const,
          content: "existing message",
          timestamp: "09:00"
        }
      ],
      context: { type: "custom" as const }
    };

    useChatStore.setState({ sessions: [existingSession], activeSessionId: null });
    setSearchParams("session=chat-100");

    render(<ChatPage />);

    expect(screen.getByText("existing message")).toBeInTheDocument();
  });

  // 사용자 입력: 새 세션 버튼을 누르면 createSession이 호출되어 세션이 추가된다.
  it("creates a new session from history control", () => {
    render(<ChatPage />);

    fireEvent.click(screen.getByText("new-session"));

    expect(useChatStore.getState().sessions.length).toBeGreaterThan(0);
  });

  // 정상 흐름: 메시지를 전송하면 사용자/어시스턴트 메시지가 세션에 누적된다.
  it("appends user and assistant messages on send", () => {
    const session: ChatSession = {
      id: "chat-200",
      title: "세션B",
      updatedAt: "방금",
      messages: [],
      context: { type: "custom" as const }
    };

    useChatStore.setState({ sessions: [session], activeSessionId: "chat-200" });
    render(<ChatPage />);

    fireEvent.click(screen.getByText("send-message"));

    const updated = useChatStore.getState().sessions.find((item) => item.id === "chat-200");

    expect(updated?.messages.filter((message) => message.role === "user").length).toBe(1);
    expect(updated?.messages.filter((message) => message.role === "assistant").length).toBeGreaterThanOrEqual(1);
  });
});
