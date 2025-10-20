"use client";

import { useCallback, useEffect, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { nanoid } from "nanoid";
import { AppShell } from "@/components/layout/AppShell";
import { ChatHistoryList } from "@/components/chat/ChatHistoryList";
import { ChatMessageBubble } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import { ChatContextPanel } from "@/components/chat/ChatContextPanel";
import { EmptyState } from "@/components/ui/EmptyState";
import { useChatStore, selectActiveSession } from "@/store/chatStore";

const ASSISTANT_FALLBACK_RESPONSE =
  "현재는 목업 응답입니다. 실제 RAG 결과와 self-check 경고가 여기에 표시될 예정입니다. 공시 요약, 관련 뉴스, guardrail 경고 등을 이어서 제공할 수 있습니다.";

const formatTimestamp = () =>
  new Date().toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit"
  });

export default function ChatPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const querySessionId = searchParams?.get("session");

  const sessions = useChatStore((state) => state.sessions);
  const activeSessionId = useChatStore((state) => state.activeSessionId);
  const setActiveSession = useChatStore((state) => state.setActiveSession);
  const addMessage = useChatStore((state) => state.addMessage);
  const createSession = useChatStore((state) => state.createSession);
  const activeSession = useChatStore(selectActiveSession);

  const contextSummary = activeSession?.context?.summary;
  const isFilingContext = activeSession?.context?.type === "filing";
  const filingReferenceId = activeSession?.context?.referenceId;

  // [FIX] URL을 단일 진실 공급원(Single Source of Truth)으로 삼아 상태 동기화 루프를 해결합니다.
  // 기존의 양방향 동기화(URL <=> Store) 로직을 단방향(URL => Store)으로 변경합니다.

  // 1. URL 변경 감지 및 스토어 업데이트
  // URL의 'session' 쿼리 파라미터가 변경되면, 이를 감지하여 Zustand 스토어의 상태를 업데이트합니다.
  useEffect(() => {
    if (querySessionId) {
      const exists = sessions.some((s) => s.id === querySessionId);
      if (exists) {
        // 유효한 세션 ID가 URL에 있으면, 스토어의 활성 세션으로 설정합니다.
        if (activeSessionId !== querySessionId) {
          setActiveSession(querySessionId);
        }
      } else {
        // 유효하지 않은 세션 ID가 URL에 있으면, URL에서 해당 파라미터를 제거합니다.
        router.replace(pathname);
      }
    } else {
      // URL에 세션 ID가 없으면, 스토어의 활성 세션도 비웁니다.
      // (setActiveSession이 null을 처리할 수 있도록 스토어 로직 수정이 필요할 수 있습니다)
      if (activeSessionId) {
        setActiveSession(null);
      }
    }
  }, [querySessionId, sessions, activeSessionId, setActiveSession, router, pathname]);

  // 2. 사용자 인터랙션 처리
  // 사용자가 세션을 선택하거나 새로 생성하면, URL을 직접 변경하여 상태 변경 플로우를 시작시킵니다.

  const handleSelectSession = useCallback(
    (sessionId: string) => {
      const nextQuery = new URLSearchParams(searchParams.toString());
      nextQuery.set("session", sessionId);
      // router.push를 사용해 사용자가 뒤로 가기를 통해 이전 세션으로 돌아갈 수 있게 합니다.
      router.push(`${pathname}?${nextQuery.toString()}`);
    },
    [pathname, router, searchParams]
  );

  const handleCreateSession = useCallback(() => {
    const newSessionId = createSession();
    const nextQuery = new URLSearchParams(searchParams.toString());
    nextQuery.set("session", newSessionId);
    router.push(`${pathname}?${nextQuery.toString()}`);
  }, [createSession, pathname, router, searchParams]);

  const handleOpenFiling = useCallback(() => {
    if (!isFilingContext) return;

    if (filingReferenceId) {
      router.push(`/filings?filingId=${filingReferenceId}`);
    } else {
      router.push("/filings");
    }
  }, [filingReferenceId, isFilingContext, router]);

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
  const sessionTitle = activeSession?.title ?? "새 세션";
  const showEmptyState = messages.length === 0;

  const hasContextBanner = useMemo(() => Boolean(contextSummary), [contextSummary]);

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
            세션: {sessionTitle}
          </div>
          {hasContextBanner && (
            <div className="rounded-lg border border-border-light bg-white/70 px-4 py-3 text-sm dark:border-border-dark dark:bg-white/5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase text-primary">컨텍스트 요약</p>
                  {isFilingContext && filingReferenceId && (
                    <p className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">참조 ID: {filingReferenceId}</p>
                  )}
                </div>
                {isFilingContext && (
                  <button
                    type="button"
                    onClick={handleOpenFiling}
                    className="rounded-md border border-border-light px-3 py-1 text-xs font-semibold text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
                  >
                    공시 화면으로 이동
                  </button>
                )}
              </div>
              <p className="mt-3 leading-relaxed text-text-secondaryLight dark:text-text-secondaryDark">{contextSummary}</p>
            </div>
          )}
          <div className="flex-1 space-y-4 overflow-y-auto pr-2">
            {showEmptyState ? (
              <EmptyState
                title="메시지가 없습니다"
                description="새 세션을 시작하거나 공시 상세에서 '질문하기' 버튼을 눌러 대화를 생성해보세요."
                className="rounded-lg border border-border-light px-4 py-6 text-xs dark:border-border-dark"
              />
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
