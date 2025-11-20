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
  const starterPrompts = [
    "하이브 주가 분석 (주요 리스크와 CAR 영향까지 정리해줘)",
    "삼성전자 최근 분기 실적 요약해줘 (매출/영업이익/YoY)",
    "2차전지 섹터 리스크 재점검 (IRA 변수 포함)",
  ];

  const handleStarterSend = async (prompt: string) => {
    if (!prompt || inputDisabled) return;
    await onSend(prompt);
  };

  return (
    <section className="relative flex min-h-[75vh] flex-1 flex-col overflow-hidden rounded-3xl border border-white/10 bg-white/5 shadow-[0_35px_120px_rgba(3,7,18,0.55)] backdrop-blur-xl">
      <div className="flex items-center justify-between border-b border-white/10 px-6 py-5">
        <div>
          <p className="text-[11px] uppercase tracking-[0.35em] text-slate-500">Session</p>
          <p className="text-lg font-semibold text-white">{sessionTitle}</p>
        </div>
        <div className="rounded-full border border-white/10 px-4 py-1 text-xs text-slate-300">
          {new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })} · 실시간 스트림
        </div>
      </div>
      <div className="space-y-3 px-6 py-4">
        {hasContextBanner ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-4 text-sm text-slate-200">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-300">Context Highlights</p>
                {isFilingContext && filingReferenceId ? (
                  <p className="text-[11px] text-slate-400">참조 ID: {filingReferenceId}</p>
                ) : null}
              </div>
              {isFilingContext ? (
                <button
                  type="button"
                  onClick={onOpenFiling}
                  className="rounded-full border border-white/20 bg-white/5 px-4 py-1 text-xs font-semibold text-slate-200 transition hover:border-white/40 hover:text-white"
                >
                  원문 열기
                </button>
              ) : null}
            </div>
            <p className="mt-3 leading-relaxed text-slate-300">{contextSummary}</p>
          </div>
        ) : null}
        <div className="rounded-2xl border border-dashed border-white/10 bg-black/20 px-4 py-3 text-[11px] leading-relaxed text-slate-400">
          {disclaimer}
        </div>
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto px-6 pb-28 pt-2">
        {showEmptyState ? (
          <>
            <div className="flex flex-wrap gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-xs text-slate-200">
              <p className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-400">추천 질문</p>
              <div className="flex flex-wrap gap-2">
                {starterPrompts.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => handleStarterSend(prompt)}
                    className="rounded-full border border-white/15 bg-[#0f1c2f]/80 px-3 py-1 text-left text-[12px] font-semibold text-white shadow-[0_10px_30px_rgba(3,7,18,0.45)] transition hover:border-white/40 hover:scale-[1.01]"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
            <EmptyState
              title="메시지가 없습니다"
              description="새 세션을 시작하거나 궁금한 점을 바로 질문해보세요."
              className="rounded-2xl border border-white/10 bg-white/5 px-4 py-6 text-xs text-slate-300"
            />
          </>
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
      <div className="pointer-events-none absolute inset-x-0 bottom-24 h-24 bg-gradient-to-t from-[#050a1c] via-[#050a1c]/70 to-transparent" />
      <div className="relative z-10 px-6 pb-6">
        <ChatInput onSubmit={onSend} disabled={inputDisabled} />
      </div>
    </section>
  );
}
