import "@testing-library/jest-dom";
import React from "react";
import { beforeEach, vi } from "vitest";
import type { ApiChatMessage, ApiChatSession } from "@/lib/chatApi";

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ children, href, ...rest }: { children: React.ReactNode; href: string }) =>
    React.createElement("a", { href, ...rest }, children)
}));

let sessionCounter = 1;
let messageCounter = 1;

const sessionStore: ApiChatSession[] = [];
const messageStore = new Map<string, ApiChatMessage[]>();

const now = () => new Date().toISOString();

const resetStores = () => {
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
    updated_at: timestamp
  };
  sessionStore.unshift(session);
  return session;
});

const fetchSessionsMock = vi.fn(async () => ({
  sessions: [...sessionStore],
  next_cursor: null
}));

const fetchSessionMessagesMock = vi.fn(async (sessionId: string) => ({
  messages: [...(messageStore.get(sessionId) ?? [])],
  next_seq: null
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
      created_at: timestamp
    };
    const list = messageStore.get(input.session_id) ?? [];
    list.push(message);
    messageStore.set(input.session_id, list);
    return message;
  }
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
  resetStores();
});

const postRagQueryMock = vi.fn(async () => ({
  answer: "mock answer",
  context: [],
  highlights: [],
  warnings: []
}));

const streamRagQueryMock = vi.fn(async (_payload, handlers: { onEvent: (event: { event: string; [key: string]: unknown }) => void }) => {
  handlers.onEvent({
    event: "done",
    id: "mock-stream",
    turn_id: "turn",
    payload: {}
  });
});

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

const globalFetchMock = vi.fn(async () =>
  new Response(
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
  )
);

global.fetch = globalFetchMock as unknown as typeof fetch;

beforeEach(() => {
  resetStores();
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
