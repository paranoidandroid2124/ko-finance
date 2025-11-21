"use client";

import { useEffect, useMemo, useState } from "react";
import { FileText } from "lucide-react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ChatMessageBubble } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import type { ChatMessage } from "@/store/chatStore";
import { fetchWithAuth } from "@/lib/fetchWithAuth";
import { ProactiveFeedWidget } from "@/components/feed/ProactiveFeedWidget";
import { ProactiveBriefingsWidget } from "@/components/feed/ProactiveBriefingsWidget";

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
  reportAction?: {
    onOpen: () => void;
    disabled?: boolean;
    loading?: boolean;
  };
  onFocusChange?: (focused: boolean) => void;
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
  reportAction,
  onFocusChange,
}: ChatStreamPaneProps) {
  const fallbackPrompts = useMemo(
    () => [
      { question: "하이브 주가 분석 (주요 리스크와 CAR 영향까지 정리해줘)", source: "default" },
      { question: "삼성전자 최근 분기 실적 요약해줘 (매출/영업이익/YoY)", source: "default" },
      { question: "2차전지 섹터 리스크 재점검 (IRA 변수 포함)", source: "default" },
    ],
    []
  );
  const [starterPrompts, setStarterPrompts] = useState(fallbackPrompts);
  const [loadingStarters, setLoadingStarters] = useState(false);
  const [inputFocused, setInputFocused] = useState(false);
  const handleFocusChange = (focused: boolean) => {
    setInputFocused(focused);
    onFocusChange?.(focused);
  };

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        setLoadingStarters(true);
        const res = await fetchWithAuth("/api/v1/recommendations/chat?limit=3");
        if (!res.ok) {
          throw new Error(`failed ${res.status}`);
        }
        const data = await res.json();
        type RecoItem = { question?: string; source?: string };
        const items: RecoItem[] = Array.isArray(data?.items) ? data.items : [];
        const mapped =
          items
            .map((item) => {
              const question = typeof item?.question === "string" ? item.question.trim() : "";
              const source = typeof item?.source === "string" ? item.source : "default";
              return { question, source };
            })
            .filter((item) => item.question) || [];
        if (!cancelled && mapped.length) {
          setStarterPrompts(mapped);
        }
      } catch {
        // fallback to default silently
      } finally {
        if (!cancelled) {
          setLoadingStarters(false);
        }
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [fallbackPrompts]);

  const handleStarterSend = async (prompt: string) => {
    if (!prompt || inputDisabled) return;
    await onSend(prompt);
  };

  return (
    <section className="relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-[32px] border border-[#30363D] bg-[#161B22]/90 shadow-[0_35px_120px_rgba(0,0,0,0.55)] backdrop-blur-2xl">
      <div className="pointer-events-none absolute inset-0">
        <div
          className="absolute inset-x-[-12%] -top-40 h-72 bg-[radial-gradient(circle_at_25%_20%,rgba(88,166,255,0.18),transparent_55%)] blur-[110px]"
          aria-hidden
        />
        <div
          className={`absolute inset-x-[-8%] bottom-[-46%] h-[18rem] bg-[radial-gradient(circle_at_50%_20%,rgba(13,17,23,0.9),transparent_62%),radial-gradient(circle_at_40%_70%,rgba(88,166,255,0.12),transparent_55%)] transition-opacity duration-500 ${
            inputFocused ? "opacity-90" : "opacity-60"
          } blur-[130px]`}
          aria-hidden
        />
      </div>

      <div className="relative z-10 flex items-center justify-between gap-4 border-b border-[#30363D] px-7 py-6 backdrop-blur">
        <div className="min-w-0">
          <p className="text-[11px] uppercase tracking-[0.35em] text-slate-500">Session</p>
          <p className="truncate text-lg font-semibold text-white">{sessionTitle}</p>
        </div>
        <div className="flex items-center gap-3">
          {reportAction ? (
            <button
              type="button"
              onClick={() => {
                if (reportAction.disabled) return;
                reportAction.onOpen();
              }}
              disabled={reportAction.disabled}
              aria-disabled={reportAction.disabled}
              className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-[#58A6FF] to-[#58A6FF] px-4 py-2 text-xs font-semibold text-white shadow-[0_12px_36px_rgba(88,166,255,0.4)] transition hover:-translate-y-[1px] hover:shadow-[0_15px_46px_rgba(88,166,255,0.55)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <FileText className="h-4 w-4" />
              {reportAction.loading ? "Generating..." : "Generate Report"}
            </button>
          ) : null}
          <div className="rounded-full border border-[#30363D] bg-[#0D1117]/70 px-4 py-1 text-xs text-slate-200/90 shadow-[0_8px_28px_rgba(0,0,0,0.5)] backdrop-blur">
            {new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })} | 실시간 스트림
          </div>
        </div>
      </div>

      <div className="relative z-10 flex-1">
        <div className="mx-auto flex w-full max-w-[820px] flex-col space-y-4 px-5 py-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-sm font-semibold text-white">새 분석을 시작해보세요</p>
              <p className="text-[12px] text-slate-400">종목이나 이슈를 입력하면 공시·뉴스·시세 기반 분석을 바로 제공합니다.</p>
            </div>
          </div>
          <ProactiveBriefingsWidget />
          <ProactiveFeedWidget />
          {hasContextBanner && showEmptyState ? (
            <div className="rounded-2xl border border-[#30363D] bg-[#0D1117]/60 px-4 py-3 text-sm text-slate-200 shadow-[0_10px_30px_rgba(0,0,0,0.35)] backdrop-blur-xl">
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
          {showEmptyState ? <p className="text-[11px] leading-relaxed text-slate-500">{disclaimer}</p> : null}
        </div>
      </div>

      <div className="relative z-10 flex-1">
        <div className="mx-auto flex w-full max-w-[820px] flex-col space-y-4 overflow-y-auto px-5 pb-8 pt-2">
          {showEmptyState ? (
            <>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                {(loadingStarters ? fallbackPrompts : starterPrompts).slice(0, 3).map((item) => (
                  <button
                    key={`${item.source}:${item.question}`}
                    type="button"
                    onClick={() => handleStarterSend(item.question)}
                    className="flex h-full flex-col items-start gap-2 rounded-2xl border border-[#30363D] bg-[#0D1117]/70 px-4 py-3 text-left text-sm font-semibold text-white shadow-[0_10px_30px_rgba(0,0,0,0.35)] transition hover:border-[#58A6FF]/70 hover:translate-y-[-1px]"
                  >
                    <span className="text-lg">📈</span>
                    <span className="text-[12px] font-medium text-slate-200">{item.question}</span>
                  </button>
                ))}
              </div>
              <EmptyState
                title="메시지가 없습니다"
                description="새 세션을 시작하거나 궁금한 점을 바로 질문해보세요."
                className="rounded-2xl border border-[#30363D] bg-[#0D1117]/70 px-4 py-6 text-xs text-slate-300"
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
      </div>

      <div
        className="pointer-events-none absolute inset-x-6 bottom-[80px] h-24 rounded-full bg-[radial-gradient(circle_at_50%_50%,rgba(88,166,255,0.22),transparent_55%)] opacity-70 blur-2xl"
        aria-hidden
      />
      <div className="relative z-20">
        <div className="mx-auto w-full max-w-[820px] px-5 pb-8">
          <ChatInput onSubmit={onSend} disabled={inputDisabled} onFocusChange={handleFocusChange} />
        </div>
      </div>
    </section>
  );
}
