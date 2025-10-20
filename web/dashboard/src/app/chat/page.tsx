"use client";

import { useCallback, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { nanoid } from "nanoid";
import { AppShell } from "@/components/layout/AppShell";
import { ChatHistoryList } from "@/components/chat/ChatHistoryList";
import { ChatMessageBubble } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import { ChatContextPanel } from "@/components/chat/ChatContextPanel";
import { useChatStore, selectActiveSession } from "@/store/chatStore";

const ASSISTANT_FALLBACK_RESPONSE =
  "í˜„ìž¬ëŠ” ëª©ì—… ì‘ë‹µìž…ë‹ˆë‹¤. ì‹¤ì œ RAG ê²°ê³¼ì™€ self-check ê²½ê³ ê°€ ì—¬ê¸°ì— í‘œì‹œë  ì˜ˆì •ìž…ë‹ˆë‹¤. ê³µì‹œ ìš”ì•½, ê´€ë ¨ ë‰´ìŠ¤, guardrail ê²½ê³  ë“±ì„ ì´ì–´ì„œ ì œê³µí•  ìˆ˜ ìžˆìŠµë‹ˆë‹¤.";

const formatTimestamp = () =>
  new Date().toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit"
  });

export default function ChatPage() {
  const searchParams = useSearchParams();
  const querySessionId = searchParams?.get("session");

  const sessions = useChatStore((state) => state.sessions);
  const activeSessionId = useChatStore((state) => state.activeSessionId);
  const setActiveSession = useChatStore((state) => state.setActiveSession);
  const addMessage = useChatStore((state) => state.addMessage);
  const createSession = useChatStore((state) => state.createSession);
  const activeSession = useChatStore(selectActiveSession);

  useEffect(() => {
    if (!querySessionId) return;
    if (querySessionId === activeSessionId) return;

    const exists = sessions.some((session) => session.id === querySessionId);
    if (exists) {
      setActiveSession(querySessionId);
    }
  }, [querySessionId, sessions, activeSessionId, setActiveSession]);

  const handleSelectSession = useCallback(
    (sessionId: string) => {
      setActiveSession(sessionId);
    },
    [setActiveSession]
  );

  const handleCreateSession = useCallback(() => {
    createSession();
  }, [createSession]);

  const handleSend = useCallback(
    (rawInput: string) => {
      const trimmed = rawInput.trim();
      if (!trimmed) return;

      let targetSessionId = activeSessionId;
      if (!targetSessionId) {
        targetSessionId = createSession();
      }

      const timestamp = formatTimestamp();

      addMessage(targetSessionId, {
        id: nanoid(),
        role: "user",
        content: trimmed,
        timestamp
      });

      addMessage(targetSessionId, {
        id: nanoid(),
        role: "assistant",
        content: ASSISTANT_FALLBACK_RESPONSE,
        timestamp
      });
    },
    [activeSessionId, addMessage, createSession]
  );

  const messages = activeSession?.messages ?? [];
  const sessionTitle = activeSession?.title ?? "ìƒˆ ì„¸ì…˜";
  const showEmptyState = messages.length === 0;

  return (
    <AppShell>
      <div className="flex flex-col gap-6 lg:flex-row">
        <ChatHistoryList
          sessions={sessions}
          selectedId={activeSessionId ?? undefined}
          onSelect={handleSelectSession}
          onNewSession={handleCreateSession}
        />
        <div className="flex min-h-[70vh] flex-1 flex-col gap-4 rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
          <div className="h-12 rounded-lg border border-border-light px-4 py-2 text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
            ì„¸ì…˜: {sessionTitle}
          </div>
          <div className="flex-1 space-y-4 overflow-y-auto pr-2">
            {showEmptyState ? (
              <p className="rounded-lg border border-dashed border-border-light px-4 py-6 text-center text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
                ì•„ì§ ë©”ì‹œì§€ê°€ ì—†ìŠµë‹ˆë‹¤. ìƒˆ ì„¸ì…˜ì„ ì‹œìž‘í•˜ê±°ë‚˜ ê³µì‹œ ìƒì„¸ì—ì„œ ì§ˆë¬¸í•´ë³´ì„¸ìš”.
              </p>
            ) : (
              messages.map((message) => <ChatMessageBubble key={message.id} {...message} />)
            )}
          </div>
          <ChatInput onSubmit={handleSend} />
        </div>
        <ChatContextPanel />
      </div>
    </AppShell>
  );
}
