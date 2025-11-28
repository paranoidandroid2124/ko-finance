"use client";

import { useEffect, useMemo, useState } from "react";
import { FileText } from "lucide-react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ChatMessageBubble } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import { Button } from "@/components/ui/Button";
import { Toolbar } from "@/components/ui/Toolbar";
import { ShareButton } from "@/components/share/ShareButton";
import type { ChatMessage } from "@/store/chatStore";
import { fetchWithAuth } from "@/lib/fetchWithAuth";

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
  sessionId?: string;
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
  sessionId,
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
    <section className="relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-[32px] border border-border-hair/70 bg-surface-1/90 shadow-elevation-3 backdrop-blur-glass">
      <div className="pointer-events-none absolute inset-0">
        <div
          className="absolute inset-x-[-12%] -top-40 h-72 bg-[radial-gradient(circle_at_25%_20%,rgba(88,166,255,0.18),transparent_55%)] blur-[110px]"
          aria-hidden
        />
        <div
          className={`absolute inset-x-[-8%] bottom-[-46%] h-[18rem] bg-[radial-gradient(circle_at_50%_20%,rgba(13,17,23,0.9),transparent_62%),radial-gradient(circle_at_40%_70%,rgba(88,166,255,0.12),transparent_55%)] transition-opacity duration-500 ${inputFocused ? "opacity-90" : "opacity-60"
            } blur-[130px]`}
          aria-hidden
        />
      </div>

      <div className="relative z-10 flex items-center justify-between gap-4 border-b border-border-hair/70 px-7 py-6 backdrop-blur">
        <div className="min-w-0">
          <p className="text-[11px] uppercase tracking-[0.35em] text-text-secondary">Session</p>
          <p className="truncate text-lg font-semibold text-text-primary">{sessionTitle}</p>
        </div>
        <div className="flex items-center gap-3">
          {sessionId && !showEmptyState && messages.length > 0 && (
            <ShareButton
              resourceType="chat_session"
              resourceId={sessionId}
              title={sessionTitle}
            />
          )}
          {reportAction ? (
            <Button
              variant="solid"
              tone="brand"
              size="sm"
              icon={<FileText className="h-4 w-4" />}
              onClick={() => {
                if (reportAction.disabled) return;
                reportAction.onOpen();
              }}
              disabled={reportAction.disabled}
              loading={reportAction.loading}
            >
              Generate Report
            </Button>
          ) : null}
          <Toolbar className="text-xs text-text-secondary px-3 py-1.5 gap-2">
            {new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })} | 실시간 스트림
          </Toolbar>
        </div>
      </div>

      <div className="relative z-10 flex-1">
        <div className="mx-auto flex w-full max-w-[820px] flex-col space-y-4 px-5 py-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-sm font-semibold text-text-primary">새 분석을 시작해보세요</p>
              <p className="text-[12px] text-text-secondary">종목이나 이슈를 입력하면 공시·뉴스·시세 기반 분석을 바로 제공합니다.</p>
            </div>
          </div>
          {hasContextBanner && showEmptyState ? (
            <div className="rounded-2xl border border-border-hair/70 bg-surface-2/80 px-4 py-3 text-sm text-text-secondary shadow-subtle backdrop-blur-glass">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-primary">Context Highlights</p>
                  {isFilingContext && filingReferenceId ? (
                    <p className="text-[11px] text-text-secondary">참조 ID: {filingReferenceId}</p>
                  ) : null}
                </div>
                {isFilingContext ? (
                  <Button variant="outline" tone="neutral" size="sm" onClick={onOpenFiling}>
                    원문 열기
                  </Button>
                ) : null}
              </div>
              <p className="mt-3 leading-relaxed text-text-secondary">{contextSummary}</p>
            </div>
          ) : null}
          {showEmptyState ? <p className="text-[11px] leading-relaxed text-text-muted">{disclaimer}</p> : null}
        </div>
      </div>

      <div className="relative z-10 flex-1">
        <div className="mx-auto flex w-full max-w-[820px] flex-col space-y-4 overflow-y-auto px-5 pb-8 pt-2">
          {showEmptyState ? (
            <>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                {(loadingStarters ? fallbackPrompts : starterPrompts).slice(0, 3).map((item, idx) => (
                  <button
                    key={`${item.source}:${item.question}`}
                    type="button"
                    onClick={() => handleStarterSend(item.question)}
                    className="flex h-full flex-col items-start gap-2 rounded-2xl border border-border-hair/70 bg-surface-2/80 px-4 py-3 text-left text-sm font-semibold text-text-primary shadow-subtle transition hover:border-primary/60 hover:-translate-y-[1px] transition-motion-medium"
                    style={{ animation: `fadeUp 0.45s ease ${idx * 70}ms both` } as React.CSSProperties}
                  >
                    <span className="text-lg">📈</span>
                    <span className="text-[12px] font-medium text-text-secondary">{item.question}</span>
                  </button>
                ))}
              </div>
              <EmptyState
                title="메시지가 없습니다"
                description="새 세션을 시작하거나 궁금한 점을 바로 질문해보세요."
                className="rounded-2xl border border-border-hair/70 bg-surface-2/80 px-4 py-6 text-xs text-text-secondary"
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
