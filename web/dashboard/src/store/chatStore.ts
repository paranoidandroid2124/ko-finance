"use client";

import { create } from "zustand";
import { nanoid } from "nanoid";

export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: string;
  meta?: Record<string, unknown>;
};

export type EvidenceHighlight = {
  id: string;
  page: number;
  yStartPct: number;
  yEndPct: number;
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
      status: "idle" | "loading";
    })
  | (RagEvidenceStateBase & {
      status: "ready";
    })
  | (RagEvidenceStateBase & {
      status: "error";
      errorMessage: string;
    });

export type ChatSession = {
  id: string;
  title: string;
  updatedAt: string;
  context?: {
    type: "filing" | "news" | "custom";
    referenceId?: string;
    summary?: string;
  };
  messages: ChatMessage[];
  evidence?: RagEvidenceState;
};

type ChatStoreState = {
  sessions: ChatSession[];
  activeSessionId: string | null;
};

type ChatStoreActions = {
  setActiveSession: (id: string) => void;
  addMessage: (sessionId: string, message: ChatMessage) => void;
  createSession: (title?: string) => string;
  startFilingConversation: (payload: {
    filingId: string;
    company: string;
    title: string;
    summary: string;
  }) => string;
  focus_evidence_item: (evidenceId?: string) => void;
};

const formatNow = () =>
  new Date().toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit"
  });

const initialSessions: ChatSession[] = [
  {
    id: "chat-1",
    title: "“삼성전자 실적 요약”",
    updatedAt: "5분 전",
    context: {
      type: "filing",
      referenceId: "F-001",
      summary: "반도체 부문 재고 조정으로 영업이익이 감소했지만, 시스템 LSI와 파운드리는 견조한 성장 기조입니다."
    },
    messages: [
      {
        id: nanoid(),
        role: "assistant",
        content: "안녕하세요! 공시와 뉴스 기반으로 질문에 답변드릴 수 있습니다. 공시 제목이나 상황을 설명해 주세요.",
        timestamp: "방금"
      }
    ],
    evidence: {
      status: "ready",
      items: [
        {
          id: "ev-1",
          title: "자사 재무 목록 해석",
          snippet: "재무 정리 문단에서 의로 필요한 세부 사항이 안내되며, 공시 무재수에서 간략 개설 필요.",
          page: 12,
          score: 0.82,
          highlightRange: {
            id: "hl-ev-1",
            page: 12,
            yStartPct: 22,
            yEndPct: 38,
            summary: "현금흐름 추이를 설명하는 문단"
          }
        },
        {
          id: "ev-2",
          title: "LSI 블록커 요약",
          snippet: "공시에서 마련 비우 된 LSI 파운드리 확장 계획에 대한 배경시 기초.",
          page: 34,
          score: 0.76,
          highlightRange: {
            id: "hl-ev-2",
            page: 34,
            yStartPct: 45,
            yEndPct: 60,
            summary: "LSI 투자 계획의 핵심 수치"
          }
        }
      ],
      activeId: "ev-1",
      confidence: 0.71,
      documentTitle: "삼성전자 반기보고서",
      documentUrl: "/mock/filings/F-001.pdf"
    }
  },
  {
    id: "chat-2",
    title: "LG화학 투자 포인트",
    updatedAt: "1시간 전",
    context: {
      type: "filing",
      referenceId: "F-002",
      summary: "전지 사업부 수요 회복과 전기차 소재 CAPEX 확대 계획이 공시에서 강조되었습니다."
    },
    messages: [
      {
        id: nanoid(),
        role: "assistant",
        content: "LG화학 반기보고서 관련 질문이 있으시면 말씀해주세요.",
        timestamp: "1시간 전"
      }
    ],
    evidence: {
      status: "loading",
      items: [],
      activeId: undefined,
      confidence: undefined,
      documentTitle: "LG화학 반기보고서",
      documentUrl: "/mock/filings/F-002.pdf"
    }
  }
];

export const useChatStore = create<ChatStoreState & ChatStoreActions>((set, get) => ({
  sessions: initialSessions,
  activeSessionId: initialSessions[0]?.id ?? null,
  setActiveSession: (id) => set({ activeSessionId: id }),
  addMessage: (sessionId, message) =>
    set((state) => {
      const sessions = state.sessions.map((session) =>
        session.id === sessionId
          ? {
              ...session,
              messages: [...session.messages, message],
              updatedAt: message.timestamp
            }
          : session
      );
      return { sessions };
    }),
  createSession: (title = "새 대화") => {
    const sessionId = nanoid();
    const newSession: ChatSession = {
      id: sessionId,
      title,
      updatedAt: "방금",
      context: { type: "custom" },
      messages: [
        {
          id: nanoid(),
          role: "assistant",
          content:
            "새로운 대화를 시작했습니다. 공시나 뉴스에 대한 질문을 입력하면 근거와 함께 답변을 드릴게요.",
          timestamp: formatNow()
        }
      ],
      evidence: {
        status: "idle",
        items: [],
        activeId: undefined,
        confidence: undefined
      }
    };
    set((state) => ({
      sessions: [newSession, ...state.sessions],
      activeSessionId: sessionId
    }));
    return sessionId;
  },
  startFilingConversation: ({ filingId, company, title, summary }) => {
    const sessionId = nanoid();
    const now = formatNow();
    const newSession: ChatSession = {
      id: sessionId,
      title: `“${company} 공시 분석”`,
      updatedAt: now,
      context: {
        type: "filing",
        referenceId: filingId,
        summary
      },
      messages: [
        {
          id: nanoid(),
          role: "assistant",
          content: `“${title}” 공시 내용을 기반으로 질문을 도와드릴게요. 궁금한 점을 입력해주세요.`,
          timestamp: now
        }
      ],
      evidence: {
        status: "loading",
        items: [],
        activeId: undefined,
        confidence: undefined,
        documentTitle: title,
        documentUrl: `/mock/filings/${filingId}.pdf`
      }
    };
    set((state) => ({
      sessions: [newSession, ...state.sessions],
      activeSessionId: sessionId
    }));
    return sessionId;
  },
  focus_evidence_item: (evidenceId) => {
    const activeSessionId = get().activeSessionId;
    if (!activeSessionId) return;
    set((state) => {
      const sessions = state.sessions.map((session) => {
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
      });
      return { sessions };
    });
  }
}));

export const selectActiveSession = (state: ChatStoreState & ChatStoreActions) =>
  state.sessions.find((session) => session.id === state.activeSessionId) ?? null;

export const selectActiveEvidence = (state: ChatStoreState & ChatStoreActions): RagEvidenceState => {
  const evidence = selectActiveSession(state)?.evidence;
  if (!evidence) {
    return {
      status: "idle",
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
  selectActiveSession(state)?.evidence?.status ?? "idle";

export const selectHighlightDisplay = (state: ChatStoreState & ChatStoreActions) => {
  const session = selectActiveSession(state);
  const evidence = session?.evidence;
  if (!evidence) {
    return {
      status: "idle" as const,
      ranges: [] as Array<EvidenceHighlight & { evidenceId: string }>,
      activeRangeId: undefined,
      documentTitle: session?.title,
      documentUrl: session?.context?.referenceId ? `/mock/filings/${session.context.referenceId}.pdf` : undefined
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
