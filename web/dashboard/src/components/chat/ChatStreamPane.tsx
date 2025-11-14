"use client";

import { EmptyState } from "@/components/ui/EmptyState";
import { ChatMessageBubble } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import type { ChatMessage } from "@/store/chatStore";

type ChatStreamPaneProps = {
  sessionTitle: string;
  contextSummary: string | null;
  hasContextBanner: boolean;
  isFilingContext: boolean;
  filingReferenceId?: string;
  onOpenFiling: () => void;
  disclaimer: string;
  messages: ChatMessage[];
  showEmptyState: boolean;
  onRetry: (messageId: string) => Promise<void>;
  onSend: (value: string) => Promise<void>;
  inputDisabled: boolean;
};

export function ChatStreamPane({
  sessionTitle,
  contextSummary,
  hasContextBanner,
  isFilingContext,
  filingReferenceId,
  onOpenFiling,
  disclaimer,
  messages,
  showEmptyState,
  onRetry,
  onSend,
  inputDisabled,
}: ChatStreamPaneProps) {
  return (
    <div className="flex min-h-[70vh] flex-1 flex-col gap-4 rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <div className="h-12 rounded-lg border border-border-light px-4 py-2 text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
        세션: {sessionTitle}
      </div>
      {hasContextBanner && (
        <div className="rounded-lg border border-border-light bg-white/70 px-4 py-3 text-sm dark:border-border-dark dark:bg-white/5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase text-primary">컨텍스트 요약</p>
              {isFilingContext && filingReferenceId ? (
                <p className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">참조 ID: {filingReferenceId}</p>
              ) : null}
            </div>
            {isFilingContext ? (
              <button
                type="button"
                onClick={onOpenFiling}
                className="rounded-md border border-border-light px-3 py-1 text-xs font-semibold text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
              >
                공시 화면으로 이동
              </button>
            ) : null}
          </div>
          <p className="mt-3 leading-relaxed text-text-secondaryLight dark:text-text-secondaryDark">{contextSummary}</p>
        </div>
      )}
      <div className="rounded-lg border border-dashed border-border-light bg-white/60 px-4 py-3 text-[11px] leading-relaxed text-text-secondaryLight dark:border-border-dark dark:bg-white/5 dark:text-text-secondaryDark">
        {disclaimer}
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto pr-2">
        {showEmptyState ? (
          <EmptyState
            title="메시지가 없습니다"
            description="새 세션을 시작하거나 궁금한 점을 바로 질문해보세요."
            className="rounded-lg border border-border-light px-4 py-6 text-xs dark:border-border-dark"
          />
        ) : (
          messages.map((message) => (
            <ChatMessageBubble
              key={message.id}
              {...message}
              onRetry={
                message.role === "assistant" && message.meta?.retryable && message.meta.status !== "ready"
                  ? () => onRetry(message.id)
                  : undefined
              }
            />
          ))
        )}
      </div>
      <ChatInput onSubmit={onSend} disabled={inputDisabled} />
    </div>
  );
}

