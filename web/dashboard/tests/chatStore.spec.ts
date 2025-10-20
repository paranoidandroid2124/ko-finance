import { beforeEach, describe, expect, it } from "vitest";
import { useChatStore } from "@/store/chatStore";

const resetStore = () => {
  useChatStore.setState({ sessions: [], activeSessionId: null });
};

describe("chatStore", () => {
  beforeEach(() => {
    resetStore();
  });

  // 정상 흐름: createSession 호출 시 신규 세션과 초기 메시지가 추가된다.
  it("creates a new empty session with assistant greeting", () => {
    const sessionId = useChatStore.getState().createSession();
    const state = useChatStore.getState();
    const created = state.sessions.find((session) => session.id === sessionId);

    expect(created).toBeDefined();
    expect(state.activeSessionId).toBe(sessionId);
    expect(created?.messages[0]?.role).toBe("assistant");
  });

  // 엣지 케이스: startFilingConversation이 공시 메타데이터를 세션에 반영하는지 확인한다.
  it("starts a filing conversation with supplied metadata", () => {
    const payload = {
      filingId: "F-999",
      company: "테스트기업",
      title: "테스트 공시",
      summary: "잠정 실적 보고 요약"
    };

    const sessionId = useChatStore.getState().startFilingConversation(payload);
    const created = useChatStore.getState().sessions.find((session) => session.id === sessionId);

    expect(created?.context?.referenceId).toBe(payload.filingId);
    expect(created?.context?.summary).toBe(payload.summary);
    expect(created?.messages[0]?.content).toContain(payload.title);
  });

  // 오류 입력: 존재하지 않는 세션에 addMessage를 호출하면 아무 변화가 없어야 한다.
  it("ignores addMessage when the session id does not exist", () => {
    const timestamp = "10:30";
    useChatStore.getState().addMessage("unknown-session", {
      id: "msg-unknown",
      role: "user",
      content: "테스트",
      timestamp
    });

    expect(useChatStore.getState().sessions).toHaveLength(0);
  });

  // 정상 흐름: addMessage가 세션 업데이트 시점도 최신화하는지 검증한다.
  it("appends messages to existing sessions and updates timestamp", () => {
    const sessionId = useChatStore.getState().createSession();
    const timestamp = "11:45";

    useChatStore.getState().addMessage(sessionId, {
      id: "msg-1",
      role: "user",
      content: "추가 질문",
      timestamp
    });

    const session = useChatStore.getState().sessions.find((item) => item.id === sessionId);

    expect(session?.messages.some((message) => message.id === "msg-1")).toBe(true);
    expect(session?.updatedAt).toBe(timestamp);
  });
});
