import { beforeEach, describe, expect, it } from "vitest";
import {
  selectContextPanelData,
  selectGuardrailTelemetry,
  selectMetricTelemetry,
  useChatStore
} from "@/store/chatStore";

const resetStore = () => {
  useChatStore.setState({
    sessions: [],
    activeSessionId: null,
    persistenceError: null,
    hydrated: true
  });
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

  // 근거 선택 로직: focus_evidence_item이 activeId를 갱신하여 패널/하이라이트 동기화가 가능해야 한다.
  it("updates active evidence id when focus_evidence_item is called", () => {
    const sessionId = "session-focus";
    useChatStore.setState({
      sessions: [
        {
          id: sessionId,
          title: "샘플 세션",
          updatedAt: "지금",
          messages: [],
          context: { type: "custom" },
          evidence: {
            status: "ready",
            items: [
              {
                id: "ev-a",
                title: "테스트 근거 A",
                snippet: "A 설명"
              },
              {
                id: "ev-b",
                title: "테스트 근거 B",
                snippet: "B 설명"
              }
            ],
            activeId: undefined,
            confidence: 0.5,
            documentTitle: "샘플 문서"
          }
        }
      ],
      activeSessionId: sessionId
    });

    useChatStore.getState().focus_evidence_item("ev-b");
    const updated = useChatStore.getState().sessions[0]?.evidence?.activeId;

    expect(updated).toBe("ev-b");
  });

  it("provides safe defaults for guardrail and metrics telemetry", () => {
    const guardrail = selectGuardrailTelemetry(useChatStore.getState());
    const metrics = selectMetricTelemetry(useChatStore.getState());

    expect(guardrail.status).toBe("idle");
    expect(metrics.status).toBe("idle");
    expect(metrics.items).toHaveLength(0);
  });

  it("selects active telemetry snapshot when present", () => {
    const sessionId = "telemetry-session";
    useChatStore.setState({
      sessions: [
        {
          id: sessionId,
          title: "텔레메트리 세션",
          updatedAt: "지금",
          messages: [],
          context: { type: "custom" },
          telemetry: {
            guardrail: {
              status: "ready",
              level: "fail",
              message: "보안 정책으로 응답이 제한되었습니다."
            },
            metrics: {
              status: "ready",
              items: [
                {
                  id: "mrr",
                  label: "월간 반복 매출",
                  value: "₩520억",
                  change: "+4%",
                  trend: "up"
                }
              ]
            }
          }
        }
      ],
      activeSessionId: sessionId
    });

    const guardrail = selectGuardrailTelemetry(useChatStore.getState());
    const metrics = selectMetricTelemetry(useChatStore.getState());
    const bundle = selectContextPanelData(useChatStore.getState());

    expect(guardrail.status).toBe("ready");
    expect(guardrail.level).toBe("fail");
    expect(metrics.items[0]?.label).toBe("월간 반복 매출");
    expect(bundle.guardrail.level).toBe("fail");
    expect(bundle.metrics.items).toHaveLength(1);
    expect(bundle.evidence.status).toBe("idle");
  });

  it("removes sessions and promotes the next session as active", () => {
    const first = useChatStore.getState().createSession("첫 번째");
    const second = useChatStore.getState().createSession("두 번째");

    useChatStore.setState({ activeSessionId: first });
    useChatStore.getState().removeSession(first);

    const state = useChatStore.getState();
    expect(state.sessions.some((session) => session.id === first)).toBe(false);
    expect(state.activeSessionId).toBe(second);
  });

  it("clears all sessions and resets the active identifier", () => {
    useChatStore.getState().createSession();
    useChatStore.getState().clearSessions();

    const state = useChatStore.getState();
    expect(state.sessions).toHaveLength(0);
    expect(state.activeSessionId).toBeNull();
  });

  it("renames sessions using the renameSession action", () => {
    const sessionId = useChatStore.getState().createSession();
    useChatStore.getState().renameSession(sessionId, "업데이트된 제목");

    const updated = useChatStore.getState().sessions.find((session) => session.id === sessionId);
    expect(updated?.title).toBe("업데이트된 제목");
  });

  it("caps the stored session history at ten entries", () => {
    Array.from({ length: 12 }).forEach((_, index) => {
      const id = useChatStore.getState().createSession(`세션 ${index + 1}`);
      useChatStore.getState().renameSession(id, `세션 ${index + 1}`);
    });

    const state = useChatStore.getState();
    expect(state.sessions.length).toBeLessThanOrEqual(10);
  });
});
