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
    hydrated: true,
    loading: false,
    error: null
  });
};

describe("chatStore", () => {
  beforeEach(() => {
    resetStore();
  });

  it("creates a new empty session with assistant greeting", async () => {
    const sessionId = await useChatStore.getState().createSession();
    const state = useChatStore.getState();
    const created = state.sessions.find((session) => session.id === sessionId);

    expect(created).toBeDefined();
    expect(state.activeSessionId).toBe(sessionId);
    expect(created?.messages[0]?.role).toBe("assistant");
  });

  it("starts a filing conversation with supplied metadata", async () => {
    const payload = {
      filingId: "F-999",
      company: "테스트기업",
      title: "테스트 공시",
      summary: "요약 본문"
    };

    const sessionId = await useChatStore.getState().startFilingConversation(payload);
    const created = useChatStore.getState().sessions.find((session) => session.id === sessionId);

    expect(created?.context?.referenceId).toBe(payload.filingId);
    expect(created?.context?.summary).toBe(payload.summary);
    expect(created?.messages[0]?.content).toContain(payload.title);
  });

  it("ignores addMessage when the session id does not exist", () => {
    const timestamp = "10:30";
    useChatStore.getState().addMessage("unknown-session", {
      id: "msg-unknown",
      role: "user",
      content: "잘못된 세션",
      timestamp
    });

    expect(useChatStore.getState().sessions).toHaveLength(0);
  });

  it("appends messages to existing sessions and updates timestamp", async () => {
    const sessionId = await useChatStore.getState().createSession();
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

  it("updates active evidence id when focus_evidence_item is called", () => {
    const sessionId = "session-focus";
    useChatStore.setState({
      sessions: [
        {
          id: sessionId,
          title: "샘플 세션",
          updatedAt: "방금",
          messages: [],
          context: { type: "custom" },
          evidence: {
            status: "ready",
            items: [
              { id: "ev-a", title: "근거 A", snippet: "A 설명" },
              { id: "ev-b", title: "근거 B", snippet: "B 설명" }
            ],
            activeId: undefined,
            confidence: 0.5,
            documentTitle: "샘플 문서"
          }
        }
      ],
      activeSessionId: sessionId,
      hydrated: true,
      loading: false,
      error: null,
      persistenceError: null
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
      activeSessionId: sessionId,
      hydrated: true,
      loading: false,
      error: null,
      persistenceError: null
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

  it("removes sessions and promotes the next session as active", async () => {
    const first = await useChatStore.getState().createSession({ title: "첫 번째" });
    const second = await useChatStore.getState().createSession({ title: "두 번째" });

    useChatStore.setState({ activeSessionId: first });
    await useChatStore.getState().removeSession(first);

    const state = useChatStore.getState();
    expect(state.sessions.some((session) => session.id === first)).toBe(false);
    expect(state.activeSessionId).toBe(second);
  });

  it("clears all sessions and resets the active identifier", async () => {
    await useChatStore.getState().createSession();
    await useChatStore.getState().clearSessions();

    const state = useChatStore.getState();
    expect(state.sessions).toHaveLength(0);
    expect(state.activeSessionId).toBeNull();
  });

  it("renames sessions using the renameSession action", async () => {
    const sessionId = await useChatStore.getState().createSession();
    await useChatStore.getState().renameSession(sessionId, "업데이트된 제목");

    const updated = useChatStore.getState().sessions.find((session) => session.id === sessionId);
    expect(updated?.title).toBe("업데이트된 제목");
  });

  it("caps the stored session history at ten entries", async () => {
    for (let index = 0; index < 12; index += 1) {
      const id = await useChatStore.getState().createSession({ title: `세션 ${index + 1}` });
      await useChatStore.getState().renameSession(id, `세션 ${index + 1}`);
    }

    const state = useChatStore.getState();
    expect(state.sessions.length).toBeLessThanOrEqual(10);
  });
});
