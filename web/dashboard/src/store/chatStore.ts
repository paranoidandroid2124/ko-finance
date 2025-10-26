'use client';

import { create } from 'zustand';
import { nanoid } from 'nanoid';
import { CHAT_STRINGS } from '@/i18n/ko';
import {
  ApiChatMessage,
  ApiChatSession,
  createMessage,
  createSession as apiCreateSession,
  fetchSessionMessages,
  fetchSessions,
  renameSession as apiRenameSession,
  clearSessions as apiClearSessions,
  deleteSession as apiDeleteSession,
} from '@/lib/chatApi';

export type ChatRole = 'user' | 'assistant';

export type ChatMessageStatus = 'pending' | 'streaming' | 'ready' | 'error' | 'blocked';

export type ChatMessageMeta = {
  status?: ChatMessageStatus;
  errorMessage?: string;
  retryable?: boolean;
  question?: string;
  userMessageId?: string;
  judgeDecision?: string | null;
  judgeReason?: string | null;
  traceId?: string | null;
  warnings?: string[];
  citations?: Record<string, string[]>;
  model?: string | null;
  [key: string]: unknown;
};

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: string;
  meta?: ChatMessageMeta;
};

export type EvidenceHighlight = {
  id: string;
  page: number;
  yStartPct: number;
  yEndPct: number;
  xStartPct?: number;
  xEndPct?: number;
  summary?: string;
};

export type RagEvidenceItem = {
  id: string;
  title: string;
  snippet: string;
  sourceUrl?: string;
  page?: number;
  score?: number;
  highlightRange?: EvidenceHighlight;
  chunkType?: string;
  metadata?: Record<string, unknown>;
};

export type GuardrailLevel = 'pass' | 'warn' | 'fail';

export type GuardrailTelemetry = {
  status: 'idle' | 'loading' | 'ready' | 'error';
  level?: GuardrailLevel;
  message?: string;
  errorMessage?: string;
};

export type MetricTrend = 'up' | 'down' | 'flat';

export type MetricSummary = {
  id: string;
  label: string;
  value: string;
  change?: string;
  trend?: MetricTrend;
  description?: string;
};

export type MetricsTelemetry = {
  status: 'idle' | 'loading' | 'ready' | 'error';
  items: MetricSummary[];
  errorMessage?: string;
};

export type SessionTelemetry = {
  guardrail: GuardrailTelemetry;
  metrics: MetricsTelemetry;
};

export type ChatSessionContext =
  | { type: 'filing'; referenceId?: string; summary?: string | null }
  | { type: 'news'; referenceId?: string; summary?: string | null }
  | { type: 'custom'; summary?: string | null };

export type RagEvidenceState =
  | {
      status: 'idle' | 'loading';
      items: RagEvidenceItem[];
      activeId?: string;
      confidence?: number;
      documentTitle?: string;
      documentUrl?: string;
      errorMessage?: string;
    }
  | {
      status: 'ready';
      items: RagEvidenceItem[];
      activeId?: string;
      confidence?: number;
      documentTitle?: string;
      documentUrl?: string;
      errorMessage?: string;
    }
  | {
      status: 'error';
      items: RagEvidenceItem[];
      activeId?: string;
      confidence?: number;
      documentTitle?: string;
      documentUrl?: string;
      errorMessage: string;
    };

export type ChatSession = {
  id: string;
  title: string;
  version?: number;
  updatedAt: string;
  lastMessageAt?: string | null;
  context?: ChatSessionContext;
  messages: ChatMessage[];
  messagesLoaded: boolean;
  evidence: RagEvidenceState;
  telemetry: SessionTelemetry;
};

type ChatStoreState = {
  sessions: ChatSession[];
  activeSessionId: string | null;
  hydrated: boolean;
  loading: boolean;
  error: string | null;
};

type ChatStoreActions = {
  hydrateSessions: () => Promise<void>;
  setActiveSession: (id: string | null) => Promise<void>;
  createSession: (options?: { title?: string | null; context?: ChatSessionContext }) => Promise<string>;
  startFilingConversation: (payload: {
    filingId: string;
    company: string;
    title: string;
    summary: string;
    viewerUrl?: string;
    downloadUrl?: string;
  }) => Promise<string>;
  removeSession: (sessionId: string) => Promise<void>;
  clearSessions: () => Promise<void>;
  renameSession: (sessionId: string, title: string) => Promise<void>;
  loadSessionMessages: (sessionId: string) => Promise<void>;
  addMessage: (sessionId: string, message: ChatMessage) => void;
  updateMessage: (sessionId: string, messageId: string, patch: Partial<ChatMessage>) => void;
  setSessionEvidence: (sessionId: string, evidence: RagEvidenceState) => void;
  setSessionTelemetry: (sessionId: string, telemetry: Partial<SessionTelemetry>) => void;
  focus_evidence_item: (evidenceId?: string) => void;
  resetError: () => void;
};

type Store = ChatStoreState & ChatStoreActions;

const MAX_SESSIONS = 10;

const createGreetingMessage = (sessionId: string): ChatMessage => ({
  id: `greeting-${sessionId}`,
  role: 'assistant',
  content: CHAT_STRINGS.greeting,
  timestamp: new Date().toISOString(),
  meta: {
    status: 'ready'
  }
});

const ensureGreeting = (session: ChatSession): ChatSession => {
  if (session.messages.length > 0) {
    return session;
  }
  return {
    ...session,
    messages: [createGreetingMessage(session.id)],
    messagesLoaded: session.messagesLoaded
  };
};

const enforceSessionLimit = (sessions: ChatSession[]): ChatSession[] => {
  if (sessions.length <= MAX_SESSIONS) {
    return sessions;
  }
  return sessions.slice(0, MAX_SESSIONS);
};

const guardrailDefault: GuardrailTelemetry = { status: 'idle' };
const metricsDefault: MetricsTelemetry = { status: 'idle', items: [] };

const mapContext = (record: ApiChatSession): ChatSessionContext => {
  const type = (record.context_type ?? '').toLowerCase();
  const referenceId = record.context_id ?? undefined;
  const summary = record.summary ?? null;
  if (type === 'filing') {
    return { type: 'filing', referenceId, summary };
  }
  if (type === 'news') {
    return { type: 'news', referenceId, summary };
  }
  return { type: 'custom', summary };
};

const mapStatus = (state: string): ChatMessageStatus => {
  switch (state) {
    case 'pending':
      return 'pending';
    case 'streaming':
      return 'streaming';
    case 'ready':
      return 'ready';
    case 'error':
      return 'error';
    default:
      return 'ready';
  }
};

const mapMeta = (record: ApiChatMessage): ChatMessageMeta => {
  const status = mapStatus(record.state);
  const baseMeta: ChatMessageMeta = {
    status,
  };
  if (record.error_message) {
    baseMeta.errorMessage = record.error_message;
    baseMeta.retryable = true;
  }
  const rawMeta = record.meta ?? {};
  if (typeof rawMeta === 'object') {
    return { ...rawMeta, ...baseMeta };
  }
  return baseMeta;
};

const mapMessage = (record: ApiChatMessage): ChatMessage => ({
  id: record.id,
  role: record.role === 'assistant' ? 'assistant' : 'user',
  content: (record.content ?? '').toString(),
  timestamp: record.created_at,
  meta: mapMeta(record),
});

const mapSession = (record: ApiChatSession): ChatSession => ({
  id: record.id,
  title: record.title || '새 대화',
  version: record.version,
  updatedAt: record.updated_at,
  lastMessageAt: record.last_message_at,
  context: mapContext(record),
  messages: [],
  messagesLoaded: false,
  evidence: {
    status: 'idle',
    items: [],
    activeId: undefined,
    confidence: undefined,
    documentTitle: undefined,
    documentUrl: undefined,
  },
  telemetry: {
    guardrail: { ...guardrailDefault },
    metrics: { ...metricsDefault },
  },
});

const upsertSession = (sessions: ChatSession[], session: ChatSession): ChatSession[] => {
  const index = sessions.findIndex((item) => item.id === session.id);
  if (index === -1) {
    return [session, ...sessions];
  }
  const next = [...sessions];
  next[index] = { ...next[index], ...session };
  return next;
};

export const useChatStore = create<Store>((set, get) => ({
  sessions: [],
  activeSessionId: null,
  hydrated: false,
  loading: false,
  error: null,

  hydrateSessions: async () => {
    if (get().loading) return;
    set({ loading: true, error: null });
    try {
      const response = await fetchSessions();
    const mapped = response.sessions.map(mapSession).map(ensureGreeting);
      set((state) => ({
        sessions: enforceSessionLimit(mapped),
        activeSessionId: state.activeSessionId ?? mapped[0]?.id ?? null,
        hydrated: true,
        loading: false,
      }));
    } catch (error) {
      const message = error instanceof Error ? error.message : '세션을 불러오지 못했습니다.';
      set({ error: message, loading: false, hydrated: true });
    }
  },

  setActiveSession: async (id) => {
    set({ activeSessionId: id ?? null });
    if (!id) {
      return;
    }
    const target = get().sessions.find((session) => session.id === id);
    if (!target) {
      return;
    }
    const hasLocalMessages = Array.isArray(target.messages) && target.messages.length > 0;
    if (target.messagesLoaded || hasLocalMessages) {
      if (!target.messagesLoaded) {
        set((state) => ({
          sessions: state.sessions.map((session) =>
            session.id === id ? { ...session, messagesLoaded: true } : session,
          ),
        }));
      }
      return;
    }
    await get().loadSessionMessages(id);
  },

  createSession: async (options) => {
    const contextType = options?.context?.type ?? 'custom';
    const contextId = options?.context?.type === 'custom' ? null : options?.context?.referenceId ?? null;
    const response = await apiCreateSession({
      title: options?.title ?? null,
      context_type: contextType,
      context_id: contextId,
    });
    const mapped = ensureGreeting(mapSession(response));
    set((state) => ({
      sessions: enforceSessionLimit(upsertSession(state.sessions, mapped)),
      activeSessionId: mapped.id,
    }));
    return mapped.id;
  },

  startFilingConversation: async ({ filingId, company, title, summary, viewerUrl, downloadUrl }) => {
    const sessionId = await get().createSession({
      title: `${company} 공시 분석`,
      context: { type: 'filing', referenceId: filingId, summary },
    });

    const turnId = nanoid();
    const initialMessage = await createMessage({
      session_id: sessionId,
      role: 'assistant',
      content: `${title} 공시에 대해 어떤 점이 궁금한가요?`,
      turn_id: turnId,
      state: 'ready',
      meta: { status: 'ready' },
    });

    const mappedMessage = mapMessage({
      ...initialMessage,
      content: initialMessage.content ?? CHAT_STRINGS.newSessionGreeting(title),
    });
    set((state) => ({
      sessions: enforceSessionLimit(
        state.sessions.map((session) =>
          session.id === sessionId
            ? {
                ...session,
                context: { type: 'filing', referenceId: filingId, summary },
                messages: [mappedMessage, ...session.messages],
                messagesLoaded: false,
                evidence: {
                  status: 'idle',
                  items: [],
                  activeId: undefined,
                  confidence: undefined,
                  documentTitle: title,
                  documentUrl: viewerUrl ?? downloadUrl,
                },
              }
            : session,
        ),
      ),
      activeSessionId: sessionId,
    }));
    return sessionId;
  },

  removeSession: async (sessionId) => {
    await apiDeleteSession(sessionId);
    set((state) => {
      const filtered = state.sessions.filter((session) => session.id !== sessionId);
      const activeSessionId =
        state.activeSessionId === sessionId ? filtered[0]?.id ?? null : state.activeSessionId;
      return { sessions: filtered, activeSessionId };
    });
  },

  clearSessions: async () => {
    await apiClearSessions();
    set({ sessions: [], activeSessionId: null });
  },

  renameSession: async (sessionId, title) => {
    const existing = get().sessions.find((session) => session.id === sessionId);
    const version = existing?.version;
    const response = await apiRenameSession(sessionId, title, version);
    const mapped = mapSession(response);
    set((state) => ({
      sessions: state.sessions.map((session) =>
        session.id === sessionId ? { ...session, title: mapped.title, version: mapped.version } : session,
      ),
    }));
  },

  loadSessionMessages: async (sessionId) => {
    try {
      const response = await fetchSessionMessages(sessionId);
      const mapped = response.messages.map(mapMessage).sort((a, b) => (a.timestamp > b.timestamp ? 1 : -1));
      set((state) => ({
        sessions: state.sessions.map((session) =>
          session.id === sessionId
            ? {
                ...session,
                messages: mapped,
                messagesLoaded: true,
              }
            : session,
        ),
      }));
    } catch (error) {
      const message = error instanceof Error ? error.message : '메시지를 불러오지 못했습니다.';
      set({ error: message });
    }
  },

  addMessage: (sessionId, message) => {
    set((state) => ({
      sessions: state.sessions.map((session) =>
        session.id === sessionId
          ? {
              ...session,
              messages: [...session.messages.filter((item) => item.id !== message.id), message],
              updatedAt: message.timestamp,
            }
          : session,
      ),
    }));
  },

  updateMessage: (sessionId, messageId, patch) => {
    set((state) => ({
      sessions: state.sessions.map((session) => {
        if (session.id !== sessionId) {
          return session;
        }
        return {
          ...session,
          messages: session.messages.map((message) =>
            message.id === messageId
              ? {
                  ...message,
                  ...patch,
                  meta:
                    patch.meta !== undefined
                      ? (() => {
                          const nextMeta = { ...(message.meta ?? {}), ...(patch.meta ?? {}) };
                          return Object.keys(nextMeta).length ? nextMeta : undefined;
                        })()
                      : message.meta,
                }
              : message,
          ),
        };
      }),
    }));
  },

  setSessionEvidence: (sessionId, evidence) => {
    set((state) => ({
      sessions: state.sessions.map((session) =>
        session.id === sessionId
          ? {
              ...session,
              evidence,
            }
          : session,
      ),
    }));
  },

  setSessionTelemetry: (sessionId, telemetry) => {
    set((state) => ({
      sessions: state.sessions.map((session) => {
        if (session.id !== sessionId) {
          return session;
        }
        const currentTelemetry: SessionTelemetry = session.telemetry ?? {
          guardrail: { ...guardrailDefault },
          metrics: { ...metricsDefault },
        };
        return {
          ...session,
          telemetry: {
            guardrail: telemetry.guardrail ?? currentTelemetry.guardrail,
            metrics: telemetry.metrics ?? currentTelemetry.metrics,
          },
        };
      }),
    }));
  },

  focus_evidence_item: (evidenceId) => {
    const activeSessionId = get().activeSessionId;
    if (!activeSessionId) return;
    set((state) => ({
      sessions: state.sessions.map((session) => {
        if (session.id !== activeSessionId || !session.evidence) {
          return session;
        }
        return {
          ...session,
          evidence: {
            ...session.evidence,
            activeId: evidenceId,
          },
        };
      }),
    }));
  },

  resetError: () => set({ error: null }),
}));

export const selectActiveSession = (state: Store) =>
  state.sessions.find((session) => session.id === state.activeSessionId) ?? null;

export const selectIsHydrated = (state: Store) => state.hydrated;

export const selectStoreError = (state: Store) => state.error;
export const selectPersistenceError = selectStoreError;

export const selectActiveEvidence = (state: Store): RagEvidenceState => {
  const evidence = selectActiveSession(state)?.evidence;
  if (!evidence) {
    return {
      status: 'idle',
      items: [],
      activeId: undefined,
      confidence: undefined,
      documentTitle: undefined,
      documentUrl: undefined,
    };
  }
  return evidence;
};

export const selectEvidenceStatus = (state: Store) =>
  selectActiveSession(state)?.evidence?.status ?? 'idle';

export const selectGuardrailTelemetry = (state: Store): GuardrailTelemetry => {
  const guardrail = selectActiveSession(state)?.telemetry?.guardrail;
  if (!guardrail) {
    return { ...guardrailDefault };
  }
  return { ...guardrail };
};

export const selectMetricTelemetry = (state: Store): MetricsTelemetry => {
  const metrics = selectActiveSession(state)?.telemetry?.metrics;
  if (!metrics) {
    return { ...metricsDefault };
  }
  return { ...metrics, items: [...metrics.items] };
};

export const selectContextPanelData = (state: Store) => ({
  evidence: selectActiveEvidence(state),
  guardrail: selectGuardrailTelemetry(state),
  metrics: selectMetricTelemetry(state),
});

export const selectHighlightDisplay = (state: Store) => {
  const session = selectActiveSession(state);
  const evidence = session?.evidence;
  if (!evidence) {
    return {
      status: 'idle' as const,
      ranges: [] as Array<EvidenceHighlight & { evidenceId: string }>,
      activeRangeId: undefined,
      documentTitle: session?.title,
      documentUrl: undefined,
    };
  }

  const ranges = evidence.items
    .filter((item) => Boolean(item.highlightRange))
    .map((item) => ({
      ...item.highlightRange!,
      evidenceId: item.id,
    }));

  return {
    status: evidence.status,
    ranges,
    activeRangeId: evidence.activeId
      ? ranges.find((range) => range.evidenceId === evidence.activeId)?.id ?? evidence.activeId
      : undefined,
    documentTitle: evidence.documentTitle ?? session?.title,
    documentUrl: evidence.documentUrl,
  };
};

export const selectStoreLoading = (state: Store) => state.loading;
