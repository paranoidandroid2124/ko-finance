'use client';

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { nanoid } from 'nanoid';

const MAX_SESSION_HISTORY = 10;
const STORAGE_KEY = 'chat-store-v1';

const noopStorage: Storage = {
  length: 0,
  clear: () => {},
  getItem: () => null,
  key: () => null,
  removeItem: () => {},
  setItem: () => {}
};

let notifyPersistenceError: (message: string | null) => void = () => {};

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

type RagEvidenceStateBase = {
  items: RagEvidenceItem[];
  activeId?: string;
  confidence?: number;
  documentTitle?: string;
  documentUrl?: string;
};

export type RagEvidenceState =
  | (RagEvidenceStateBase & {
      status: 'idle' | 'loading';
    })
  | (RagEvidenceStateBase & {
      status: 'ready';
    })
  | (RagEvidenceStateBase & {
      status: 'error';
      errorMessage: string;
    });

export type ChatSession = {
  id: string;
  title: string;
  updatedAt: string;
  context?: {
    type: 'filing' | 'news' | 'custom';
    referenceId?: string;
    summary?: string;
  };
  messages: ChatMessage[];
  evidence?: RagEvidenceState;
  telemetry?: SessionTelemetry;
};

type ChatStoreState = {
  sessions: ChatSession[];
  activeSessionId: string | null;
  persistenceError: string | null;
  hydrated: boolean;
};

type ChatStoreActions = {
  setActiveSession: (id: string | null) => void;
  addMessage: (sessionId: string, message: ChatMessage) => void;
  updateMessage: (sessionId: string, messageId: string, patch: Partial<ChatMessage>) => void;
  createSession: (title?: string) => string;
  startFilingConversation: (payload: {
    filingId: string;
    company: string;
    title: string;
    summary: string;
    viewerUrl?: string;
    downloadUrl?: string;
  }) => string;
  removeSession: (sessionId: string) => void;
  clearSessions: () => void;
  renameSession: (sessionId: string, title: string) => void;
  setSessionEvidence: (sessionId: string, evidence: RagEvidenceState) => void;
  setSessionTelemetry: (sessionId: string, telemetry: Partial<SessionTelemetry>) => void;
  focus_evidence_item: (evidenceId?: string) => void;
};

type StoreState = ChatStoreState & ChatStoreActions;

type StoreSetter = (
  partial: StoreState | Partial<StoreState> | ((state: StoreState) => StoreState | Partial<StoreState>),
  replace?: boolean
) => void;

type StoreGetter = () => StoreState;

let setRef: StoreSetter | null = null;
let getRef: StoreGetter | null = null;

const formatNow = () =>
  new Date().toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit'
  });

const initialSessions: ChatSession[] = [];

const guardrailDefault: GuardrailTelemetry = { status: 'idle' };
const metricsDefault: MetricsTelemetry = { status: 'idle', items: [] };

export const useChatStore = create<StoreState>()(
  persist(
    (set, get) => {
      setRef = set as StoreSetter;
      getRef = get as StoreGetter;
      notifyPersistenceError = (message) => set({ persistenceError: message });

      return {
        sessions: initialSessions,
        activeSessionId: null,
        persistenceError: null,
        hydrated: false,
        setActiveSession: (id) => set({ activeSessionId: id }),
        addMessage: (sessionId, message) =>
          set((state) => ({
            sessions: state.sessions.map((session) =>
              session.id === sessionId
                ? {
                    ...session,
                    messages: [...session.messages, message],
                    updatedAt: message.timestamp
                  }
                : session
            )
          })),
        updateMessage: (sessionId, messageId, patch) =>
          set((state) => ({
            sessions: state.sessions.map((session) => {
              if (session.id !== sessionId) {
                return session;
              }
              const now = formatNow();
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
                            : message.meta
                      }
                    : message
                ),
                updatedAt: patch.timestamp ?? (patch.meta ? now : session.updatedAt)
              };
            })
          })),
        createSession: (title = '새 대화') => {
          const sessionId = nanoid();
          const now = formatNow();
          const newSession: ChatSession = {
            id: sessionId,
            title,
            updatedAt: now,
            context: { type: 'custom' },
            messages: [
              {
                id: nanoid(),
                role: 'assistant',
                content: '새 대화를 시작했어요. 공시나 뉴스에 대해 궁금한 점을 물어보면 근거와 함께 답변해 드릴게요.',
                timestamp: now,
                meta: { status: 'ready' }
              }
            ],
            evidence: {
              status: 'idle',
              items: [],
              activeId: undefined,
              confidence: undefined
            },
            telemetry: {
              guardrail: { ...guardrailDefault },
              metrics: { ...metricsDefault }
            }
          };
          set((state) => ({
            sessions: [newSession, ...state.sessions].slice(0, MAX_SESSION_HISTORY),
            activeSessionId: sessionId
          }));
          return sessionId;
        },
        startFilingConversation: ({ filingId, company, title, summary, viewerUrl, downloadUrl }) => {
          const sessionId = nanoid();
          const now = formatNow();
          const newSession: ChatSession = {
            id: sessionId,
            title: `${company} 공시 분석`,
            updatedAt: now,
            context: {
              type: 'filing',
              referenceId: filingId,
              summary
            },
            messages: [
              {
                id: nanoid(),
                role: 'assistant',
                content: `${title} 공시에 대해 어떤 점이 궁금한가요?`,
                timestamp: now,
                meta: { status: 'ready' }
              }
            ],
            evidence: {
              status: 'idle',
              items: [],
              activeId: undefined,
              confidence: undefined,
              documentTitle: title,
              documentUrl: viewerUrl ?? downloadUrl
            },
            telemetry: {
              guardrail: { ...guardrailDefault },
              metrics: { ...metricsDefault }
            }
          };
          set((state) => ({
            sessions: [newSession, ...state.sessions].slice(0, MAX_SESSION_HISTORY),
            activeSessionId: sessionId
          }));
          return sessionId;
        },
        removeSession: (sessionId) =>
          set((state) => {
            const filtered = state.sessions.filter((session) => session.id !== sessionId);
            const nextActive = state.activeSessionId === sessionId ? filtered[0]?.id ?? null : state.activeSessionId;
            return {
              sessions: filtered,
              activeSessionId: nextActive
            };
          }),
        clearSessions: () =>
          set(() => ({
            sessions: [],
            activeSessionId: null
          })),
        renameSession: (sessionId, title) =>
          set((state) => ({
            sessions: state.sessions.map((session) =>
              session.id === sessionId
                ? {
                    ...session,
                    title
                  }
                : session
            )
          })),
        setSessionEvidence: (sessionId, evidence) =>
          set((state) => ({
            sessions: state.sessions.map((session) =>
              session.id === sessionId
                ? {
                    ...session,
                    evidence
                  }
                : session
            )
          })),
        setSessionTelemetry: (sessionId, telemetry) =>
          set((state) => ({
            sessions: state.sessions.map((session) => {
              if (session.id !== sessionId) {
                return session;
              }
              const currentTelemetry: SessionTelemetry = session.telemetry ?? {
                guardrail: { ...guardrailDefault },
                metrics: { ...metricsDefault }
              };
              return {
                ...session,
                telemetry: {
                  guardrail: telemetry.guardrail ?? currentTelemetry.guardrail,
                  metrics: telemetry.metrics ?? currentTelemetry.metrics
                }
              };
            })
          })),
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
                  activeId: evidenceId
                }
              };
            })
          }));
        }
      };
    },
    {
      name: STORAGE_KEY,
      version: 1,
      storage: createJSONStorage(() => {
        if (typeof window === 'undefined') {
          return noopStorage;
        }
        const base = window.localStorage;
        return {
          getItem: base.getItem.bind(base),
          setItem: (name: string, value: string) => {
            try {
              base.setItem(name, value);
              notifyPersistenceError(null);
            } catch (error) {
              const message =
                error instanceof Error
                  ? error.message
                  : '대화 내용을 로컬 저장소에 기록하지 못했습니다.';
              notifyPersistenceError(message);
              throw error;
            }
          },
          removeItem: base.removeItem.bind(base)
        } as Storage;
      }),
      partialize: (state) => ({
        sessions: state.sessions.slice(0, MAX_SESSION_HISTORY),
        activeSessionId: state.activeSessionId
      }),
      onRehydrateStorage: () => (_state, error) => {
        if (error) {
          const message =
            error instanceof Error
              ? error.message
              : '저장된 대화를 불러오지 못했습니다.';
          notifyPersistenceError(message);
          setRef?.((state) => ({ ...state, hydrated: true }));
        } else {
          notifyPersistenceError(null);
          const sessions = getRef?.().sessions ?? [];
          setRef?.((state) => ({
            ...state,
            hydrated: true,
            sessions: sessions.slice(0, MAX_SESSION_HISTORY)
          }));
        }
      }
    }
  )
);

export const selectActiveSession = (state: ChatStoreState & ChatStoreActions) =>
  state.sessions.find((session) => session.id === state.activeSessionId) ?? null;

export const selectPersistenceError = (state: ChatStoreState & ChatStoreActions) =>
  state.persistenceError;

export const selectIsHydrated = (state: ChatStoreState & ChatStoreActions) => state.hydrated;

export const selectActiveEvidence = (state: ChatStoreState & ChatStoreActions): RagEvidenceState => {
  const evidence = selectActiveSession(state)?.evidence;
  if (!evidence) {
    return {
      status: 'idle',
      items: [],
      activeId: undefined,
      confidence: undefined,
      documentTitle: undefined,
      documentUrl: undefined
    };
  }
  return evidence;
};

export const selectEvidenceStatus = (state: ChatStoreState & ChatStoreActions) =>
  selectActiveSession(state)?.evidence?.status ?? 'idle';

export const selectGuardrailTelemetry = (state: ChatStoreState & ChatStoreActions): GuardrailTelemetry => {
  const guardrail = selectActiveSession(state)?.telemetry?.guardrail;
  if (!guardrail) {
    return { ...guardrailDefault };
  }
  return { ...guardrail };
};

export const selectMetricTelemetry = (state: ChatStoreState & ChatStoreActions): MetricsTelemetry => {
  const metrics = selectActiveSession(state)?.telemetry?.metrics;
  if (!metrics) {
    return { ...metricsDefault };
  }
  return { ...metrics, items: [...metrics.items] };
};

export const selectContextPanelData = (state: ChatStoreState & ChatStoreActions) => ({
  evidence: selectActiveEvidence(state),
  guardrail: selectGuardrailTelemetry(state),
  metrics: selectMetricTelemetry(state)
});

export const selectHighlightDisplay = (state: ChatStoreState & ChatStoreActions) => {
  const session = selectActiveSession(state);
  const evidence = session?.evidence;
  if (!evidence) {
    return {
      status: 'idle' as const,
      ranges: [] as Array<EvidenceHighlight & { evidenceId: string }>,
      activeRangeId: undefined,
      documentTitle: session?.title,
      documentUrl: undefined
    };
  }

  const ranges = evidence.items
    .filter((item) => Boolean(item.highlightRange))
    .map((item) => ({
      ...item.highlightRange!,
      evidenceId: item.id
    }));

  return {
    status: evidence.status,
    ranges,
    activeRangeId: evidence.activeId
      ? ranges.find((range) => range.evidenceId === evidence.activeId)?.id ?? evidence.activeId
      : undefined,
    documentTitle: evidence.documentTitle ?? session?.title,
    documentUrl: evidence.documentUrl
  };
};

export type HighlightDisplayState = ReturnType<typeof selectHighlightDisplay>;

