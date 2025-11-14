import "@testing-library/jest-dom";
import React from "react";
import { beforeEach, vi } from "vitest";
import type { ApiChatMessage, ApiChatSession } from "@/lib/chatApi";
import { useChatStore } from "@/store/chatStore";
import { usePlanStore } from "@/store/planStore";

const {
  sessionStore,
  messageStore,
  resetMockStores,
  createSessionMock,
  fetchSessionsMock,
  fetchSessionMessagesMock,
  createMessageMock,
  renameSessionMock,
  deleteSessionMock,
  clearSessionsMock,
  postRagQueryMock,
  streamRagQueryMock,
} = vi.hoisted(() => {
  let sessionCounter = 1;
  let messageCounter = 1;

  const sessionStore: ApiChatSession[] = [];
  const messageStore = new Map<string, ApiChatMessage[]>();

  const now = () => new Date().toISOString();

  const resetMockStores = () => {
    sessionStore.length = 0;
    messageStore.clear();
    sessionCounter = 1;
    messageCounter = 1;
  };

  const createSessionMock = vi.fn(async (input?: { title?: string | null; context_type?: string | null; context_id?: string | null }) => {
    const id = `session-${sessionCounter++}`;
    const timestamp = now();
    const session: ApiChatSession = {
      id,
      title: input?.title ?? "새 대화",
      summary: null,
      context_type: input?.context_type ?? null,
      context_id: input?.context_id ?? null,
      message_count: 0,
      token_budget: null,
      summary_tokens: null,
      last_message_at: null,
      last_read_at: null,
      version: 1,
      archived_at: null,
      created_at: timestamp,
      updated_at: timestamp,
    };
    sessionStore.unshift(session);
    return session;
  });

  const fetchSessionsMock = vi.fn(async () => ({
    sessions: [...sessionStore],
    next_cursor: null,
  }));

  const fetchSessionMessagesMock = vi.fn(async (sessionId: string) => ({
    messages: [...(messageStore.get(sessionId) ?? [])],
    next_seq: null,
  }));

  const createMessageMock = vi.fn(
    async (input: {
      session_id: string;
      role: string;
      content?: string | null;
      turn_id: string;
      reply_to_message_id?: string | null;
      retry_of_message_id?: string | null;
      state?: string;
      meta?: Record<string, unknown>;
      idempotency_key?: string;
    }) => {
      const timestamp = now();
      const message: ApiChatMessage = {
        id: `msg-${messageCounter++}`,
        session_id: input.session_id,
        seq: messageCounter,
        turn_id: input.turn_id,
        retry_of_message_id: input.retry_of_message_id ?? null,
        reply_to_message_id: input.reply_to_message_id ?? null,
        role: input.role,
        state: input.state ?? "ready",
        error_code: null,
        error_message: null,
        content: input.content ?? null,
        meta: input.meta ?? {},
        idempotency_key: input.idempotency_key ?? null,
        created_at: timestamp,
      };
      const list = messageStore.get(input.session_id) ?? [];
      list.push(message);
      messageStore.set(input.session_id, list);
      return message;
    },
  );

  const renameSessionMock = vi.fn(async (sessionId: string, title: string, version?: number) => {
    const session = sessionStore.find((item) => item.id === sessionId);
    if (!session) {
      throw new Error("session not found");
    }
    session.title = title;
    session.version = version ?? session.version ?? 1;
    session.updated_at = now();
    return session;
  });

  const deleteSessionMock = vi.fn(async (sessionId: string) => {
    const index = sessionStore.findIndex((item) => item.id === sessionId);
    if (index >= 0) {
      sessionStore.splice(index, 1);
    }
    messageStore.delete(sessionId);
  });

  const clearSessionsMock = vi.fn(async () => {
    resetMockStores();
  });

  const postRagQueryMock = vi.fn(async () => ({
    answer: "mock answer",
    context: [],
    highlights: [],
    warnings: [],
  }));

  const streamRagQueryMock = vi.fn(async (_payload, handlers: { onEvent: (event: { event: string; [key: string]: unknown }) => void }) => {
    handlers.onEvent({
      event: "done",
      id: "mock-stream",
      turn_id: "turn",
      payload: {},
    });
  });

  return {
    sessionStore,
    messageStore,
    resetMockStores,
    createSessionMock,
    fetchSessionsMock,
    fetchSessionMessagesMock,
    createMessageMock,
    renameSessionMock,
    deleteSessionMock,
    clearSessionsMock,
    postRagQueryMock,
    streamRagQueryMock,
  };
});

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ children, href, ...rest }: { children: React.ReactNode; href: string }) =>
    React.createElement("a", { href, ...rest }, children)
}));

export const resetChatStores = () => {
  resetMockStores();
  useChatStore.setState({
    sessions: [],
    activeSessionId: null,
    hydrated: false,
    loading: false,
    error: null,
  });
  usePlanStore.setState((state) => ({
    ...state,
    planTier: "pro",
    initialized: true,
    loading: false,
    error: null,
    featureFlags: {
      ...state.featureFlags,
      ragCore: true,
    },
  }));
};

vi.mock("@/lib/chatApi", () => ({
  createSession: createSessionMock,
  fetchSessions: fetchSessionsMock,
  fetchSessionMessages: fetchSessionMessagesMock,
  createMessage: createMessageMock,
  renameSession: renameSessionMock,
  deleteSession: deleteSessionMock,
  clearSessions: clearSessionsMock,
  postRagQuery: postRagQueryMock,
  streamRagQuery: streamRagQueryMock
}));

const mockChannelSchema = {
  channels: [
    {
      type: "email",
      requiresTarget: true,
      targetRules: [
        { type: "required", message: "수신자를 한 명 이상 입력해주세요." },
        {
          type: "regex",
          pattern: "^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$",
          message: "유효하지 않은 이메일 주소가 있어요: {invalid}",
          collectInvalid: true
        }
      ],
      metadataRules: {
        subject_template: [
          {
            type: "min_length",
            value: 3,
            message: "제목 템플릿은 3자 이상 입력해주세요.",
            optional: true
          }
        ],
        reply_to: [
          {
            type: "regex",
            pattern: "^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$",
            message: "Reply-To 주소가 올바르지 않아요.",
            collectInvalid: true,
            optional: true
          }
        ]
      }
    },
    {
      type: "telegram",
      requiresTarget: false,
      targetRules: [],
      metadataRules: {}
    },
    {
      type: "slack",
      requiresTarget: true,
      targetRules: [
        { type: "required", message: "수신자를 한 명 이상 입력해주세요." },
        {
          type: "regex",
          pattern: "^https?://[^\\s]+$",
          flags: "i",
          message: "유효한 URL을 입력해주세요."
        }
      ],
      metadataRules: {}
    },
    {
      type: "webhook",
      requiresTarget: true,
      targetRules: [
        { type: "required", message: "수신자를 한 명 이상 입력해주세요." },
        {
          type: "regex",
          pattern: "^https?://[^\\s]+$",
          flags: "i",
          message: "유효한 URL을 입력해주세요."
        }
      ],
      metadataRules: {}
    },
    {
      type: "pagerduty",
      requiresTarget: true,
      targetRules: [
        { type: "required", message: "수신자를 한 명 이상 입력해주세요." },
        {
          type: "regex",
          pattern: "^[a-z0-9]{16,}$",
          flags: "i",
          message: "PagerDuty Routing Key는 16자 이상의 영숫자로 입력해주세요."
        }
      ],
      metadataRules: {
        severity: [
          {
            type: "enum",
            values: ["info", "warning", "error", "critical"],
            message: "지원하지 않는 Severity 값입니다.",
            optional: true
          }
        ]
      }
    }
  ]
};

const globalFetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
  const url =
    typeof input === "string"
      ? input
      : input instanceof URL
        ? input.href
        : typeof input === "object" && input !== null && "url" in input
          ? String((input as { url?: string }).url ?? "")
          : "";
  if (url.includes("/plan/context")) {
    return new Response(
      JSON.stringify({
        planTier: "pro",
        expiresAt: "2025-12-31T00:00:00+00:00",
        entitlements: ["search.compare", "search.alerts", "search.export", "evidence.inline_pdf", "rag.core"],
        featureFlags: {
          searchCompare: true,
          searchAlerts: true,
          searchExport: false,
          ragCore: true,
          evidenceInlinePdf: true,
          evidenceDiff: false,
          timelineFull: false,
        },
        quota: {
          chatRequestsPerDay: 500,
          ragTopK: 6,
          selfCheckEnabled: true,
          peerExportRowLimit: 120,
        },
        memoryFlags: {
          watchlist: true,
          digest: true,
          chat: true,
        },
        trial: {
          tier: "pro",
          startsAt: null,
          endsAt: null,
          durationDays: 7,
          active: false,
          used: false,
        },
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    );
  }
  if (url.includes("/alerts/channels/schema")) {
    return new Response(JSON.stringify(mockChannelSchema), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  }
  return new Response(
    JSON.stringify({
      metrics: [],
      alerts: [],
      news: []
    }),
    {
      status: 200,
      headers: {
        "Content-Type": "application/json"
      }
    }
  );
});

global.fetch = globalFetchMock as unknown as typeof fetch;

beforeEach(() => {
  resetChatStores();
  createSessionMock.mockClear();
  fetchSessionsMock.mockClear();
  fetchSessionMessagesMock.mockClear();
  createMessageMock.mockClear();
  renameSessionMock.mockClear();
  deleteSessionMock.mockClear();
  clearSessionsMock.mockClear();
  postRagQueryMock.mockClear();
  streamRagQueryMock.mockClear();
  globalFetchMock.mockClear();
});
