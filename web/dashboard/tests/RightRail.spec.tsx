import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RightRail } from "@/components/layout/RightRail";
import { useChatStore, type ChatSession } from "@/store/chatStore";

const pushMock = vi.fn();
let pathnameValue = "/chat";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock
  }),
  usePathname: () => pathnameValue
}));

const resetStore = () => {
  useChatStore.setState({ sessions: [], activeSessionId: null });
};

describe("RightRail", () => {
  beforeEach(() => {
    pushMock.mockClear();
    pathnameValue = "/chat";
    resetStore();
  });

  afterEach(() => {
    cleanup();
  });

  it("shows active session information", () => {
    const sessions: ChatSession[] = [
      {
        id: "chat-1",
        title: "활성 세션",
        updatedAt: "방금",
        messages: [],
        context: { type: "custom" }
      },
      {
        id: "chat-2",
        title: "다른 세션",
        updatedAt: "1시간 전",
        messages: [],
        context: { type: "custom" }
      }
    ];

    useChatStore.setState({ sessions, activeSessionId: "chat-1" });

    render(<RightRail />);

    expect(screen.getByText("활성 세션")).toBeInTheDocument();
    expect(screen.getByText("1시간 전")).toBeInTheDocument();
  });

  it("creates new session and navigates to chat with query when off chat page", () => {
    pathnameValue = "/dashboard";
    render(<RightRail />);

    fireEvent.click(screen.getByText("새 대화 시작"));

    const activeSessionId = useChatStore.getState().activeSessionId;
    expect(activeSessionId).toBeTruthy();
    expect(pushMock).toHaveBeenCalledWith(`/chat?session=${activeSessionId}`);
  });

  it("does not navigate when already on chat and selecting another session", () => {
    const sessions: ChatSession[] = [
      { id: "chat-1", title: "세션1", updatedAt: "방금", messages: [], context: { type: "custom" } },
      { id: "chat-2", title: "세션2", updatedAt: "5분 전", messages: [], context: { type: "custom" } }
    ];

    useChatStore.setState({ sessions, activeSessionId: "chat-1" });

    render(<RightRail />);

    fireEvent.click(screen.getByText("세션2"));

    expect(useChatStore.getState().activeSessionId).toBe("chat-2");
    expect(pushMock).not.toHaveBeenCalled();
  });
});
