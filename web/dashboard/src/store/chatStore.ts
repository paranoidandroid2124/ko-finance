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
    context: { type: "filing", referenceId: "F-001" },
    messages: [
      {
        id: nanoid(),
        role: "assistant",
        content: "안녕하세요! 공시와 뉴스 기반으로 질문에 답변드릴 수 있습니다. 공시 제목이나 상황을 설명해 주세요.",
        timestamp: "방금"
      }
    ]
  },
  {
    id: "chat-2",
    title: "LG화학 투자 포인트",
    updatedAt: "1시간 전",
    context: { type: "filing", referenceId: "F-002" },
    messages: [
      {
        id: nanoid(),
        role: "assistant",
        content: "LG화학 반기보고서 관련 질문이 있으시면 말씀해주세요.",
        timestamp: "1시간 전"
      }
    ]
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
      ]
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
      ]
    };
    set((state) => ({
      sessions: [newSession, ...state.sessions],
      activeSessionId: sessionId
    }));
    return sessionId;
  }
}));

export const selectActiveSession = (state: ChatStoreState & ChatStoreActions) =>
  state.sessions.find((session) => session.id === state.activeSessionId) ?? null;

