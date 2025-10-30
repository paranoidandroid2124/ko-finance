import { beforeEach, describe, expect, it } from "vitest";
import { resetChatStores } from "./setupTests";
import {
  type ChatSession,
  type RagEvidenceState,
  selectContextPanelData,
  selectGuardrailTelemetry,
  selectMetricTelemetry,
  useChatStore
} from "@/store/chatStore";

const makeEvidence = (
  overrides: Partial<RagEvidenceState> = {}
): RagEvidenceState => {
  const base: RagEvidenceState = {
    status: "idle",
    items: [],
    activeId: undefined,
    confidence: undefined,
    documentTitle: undefined,
    documentUrl: undefined
  };
  return { ...base, ...overrides } as RagEvidenceState;
};

const makeTelemetry = (
  overrides: Partial<ChatSession["telemetry"]> = {}
): ChatSession["telemetry"] => ({
  guardrail: { status: "idle", ...(overrides.guardrail ?? {}) },
  metrics: { status: "idle", items: [], ...(overrides.metrics ?? {}) }
});

const makeSession = (overrides: Partial<ChatSession> = {}): ChatSession => ({
  id: overrides.id ?? "session-default",
  title: overrides.title ?? "Sample Session",
  version: overrides.version,
  updatedAt: overrides.updatedAt ?? "2025-01-01T00:00:00Z",
  lastMessageAt: overrides.lastMessageAt ?? null,
  context: overrides.context ?? { type: "custom", summary: null },
  messages: overrides.messages ?? [],
  messagesLoaded: overrides.messagesLoaded ?? true,
  evidence: makeEvidence(
    typeof overrides.evidence !== "undefined" ? overrides.evidence : {}
  ),
  telemetry: makeTelemetry(
    typeof overrides.telemetry !== "undefined" ? overrides.telemetry : {}
  )
});

describe("chatStore", () => {
  beforeEach(() => {
    resetChatStores();
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
      company: "Contoso",
      title: "Contoso Q3 Filing",
      summary: "Key highlights from the latest filing."
    };

    const sessionId = await useChatStore.getState().startFilingConversation(
      payload
    );
    const created = useChatStore
      .getState()
      .sessions.find((session) => session.id === sessionId);

    expect(created?.context?.type).toBe("filing");
    if (created?.context?.type === "filing") {
      expect(created.context.referenceId).toBe(payload.filingId);
      expect(created.context.summary).toBe(payload.summary);
    }
    expect(created?.messages[0]?.content).toContain(payload.title);
  });

  it("ignores addMessage when the session id does not exist", () => {
    const timestamp = "10:30";
    useChatStore.getState().addMessage("unknown-session", {
      id: "msg-unknown",
      role: "user",
      content: "orphan message",
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
      content: "question about filings",
      timestamp
    });

    const session = useChatStore
      .getState()
      .sessions.find((item) => item.id === sessionId);

    expect(session?.messages.some((message) => message.id === "msg-1")).toBe(
      true
    );
    expect(session?.updatedAt).toBe(timestamp);
  });

  it("updates active evidence id when focus_evidence_item is called", () => {
    const sessionId = "session-focus";
    useChatStore.setState({
      sessions: [
        makeSession({
          id: sessionId,
          title: "Session With Evidence",
          evidence: makeEvidence({
            status: "ready",
            items: [
              { id: "ev-a", title: "Evidence A", snippet: "Snippet A" },
              { id: "ev-b", title: "Evidence B", snippet: "Snippet B" }
            ],
            confidence: 0.5
          })
        })
      ],
      activeSessionId: sessionId,
      hydrated: true,
      loading: false,
      error: null
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
        makeSession({
          id: sessionId,
          title: "Session With Telemetry",
          telemetry: makeTelemetry({
            guardrail: {
              status: "ready",
              level: "fail",
              message: "Sensitive content detected"
            },
            metrics: {
              status: "ready",
              items: [
                {
                  id: "mrr",
                  label: "MRR",
                  value: "$520K",
                  change: "+4%",
                  trend: "up"
                }
              ]
            }
          })
        })
      ],
      activeSessionId: sessionId,
      hydrated: true,
      loading: false,
      error: null
    });

    const guardrail = selectGuardrailTelemetry(useChatStore.getState());
    const metrics = selectMetricTelemetry(useChatStore.getState());
    const bundle = selectContextPanelData(useChatStore.getState());

    expect(guardrail.status).toBe("ready");
    expect(guardrail.level).toBe("fail");
    expect(metrics.items[0]?.label).toBe("MRR");
    expect(bundle.guardrail.level).toBe("fail");
    expect(bundle.metrics.items).toHaveLength(1);
    expect(bundle.evidence.status).toBe("idle");
  });

  it("removes sessions and promotes the next session as active", async () => {
    const first = await useChatStore
      .getState()
      .createSession({ title: "First Session" });
    const second = await useChatStore
      .getState()
      .createSession({ title: "Second Session" });

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
    await useChatStore
      .getState()
      .renameSession(sessionId, "Renamed Session Title");

    const updated = useChatStore
      .getState()
      .sessions.find((session) => session.id === sessionId);
    expect(updated?.title).toBe("Renamed Session Title");
  });

  it("caps the stored session history at ten entries", async () => {
    for (let index = 0; index < 12; index += 1) {
      const id = await useChatStore
        .getState()
        .createSession({ title: `Session ${index + 1}` });
      await useChatStore
        .getState()
        .renameSession(id, `Session ${index + 1}`);
    }

    const state = useChatStore.getState();
    expect(state.sessions.length).toBeLessThanOrEqual(10);
  });
});
