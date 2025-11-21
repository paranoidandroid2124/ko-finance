"use client";

import { useEffect, useMemo, useState } from "react";
import { FileText } from "lucide-react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ChatMessageBubble } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import type { ChatMessage } from "@/store/chatStore";
import { fetchWithAuth } from "@/lib/fetchWithAuth";
import resolveApiBase from "@/lib/apiBase";

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
  const [profileTags, setProfileTags] = useState<string[]>([]);
  const [profileError, setProfileError] = useState<string | null>(null);
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
        const items = Array.isArray(data?.items) ? data.items : [];
        const mapped =
          items
            .map((item: any) => ({
              question: String(item?.question || "").trim(),
              source: String(item?.source || "default"),
            }))
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

  useEffect(() => {
    let cancelled = false;
    const loadProfile = async () => {
      try {
        const res = await fetchWithAuth(`${resolveApiBase()}/api/v1/profile/interest`);
        if (!res.ok) {
          throw new Error(`profile ${res.status}`);
        }
        const data = await res.json();
        const tags = Array.isArray(data?.tags) ? data.tags : [];
        if (!cancelled) {
          setProfileTags(tags);
          setProfileError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setProfileError("프로필을 불러오지 못했습니다.");
        }
      }
    };
    void loadProfile();
    return () => {
      cancelled = true;
    };
  }, []);

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
        <div className="mx-auto flex w-full max-w-[820px] flex-col space-y-5 px-5 py-6">
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
        {showEmptyState ? (
          <p className="text-[11px] leading-relaxed text-slate-400">{disclaimer}</p>
        ) : null}
      </div>
    </div>

      <div className="relative z-10 flex-1">
        <div className="mx-auto flex w-full max-w-[820px] flex-col space-y-4 overflow-y-auto px-5 pb-16 pt-3">
        {showEmptyState ? (
          <>
            <div className="flex flex-wrap gap-3 rounded-2xl border border-[#30363D] bg-[#0D1117]/70 px-4 py-3 text-xs text-slate-200 shadow-[0_10px_30px_rgba(0,0,0,0.45)] backdrop-blur">
              <p className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-400">추천 질문</p>
              <div className="flex flex-wrap items-center gap-2">
                {loadingStarters ? <span className="text-[11px] text-slate-400">불러오는 중...</span> : null}
                {starterPrompts.map((item) => (
                  <button
                    key={`${item.source}:${item.question}`}
                    type="button"
                    onClick={() => handleStarterSend(item.question)}
                    className="flex items-center gap-2 rounded-full border border-[#30363D] bg-[#161B22] px-3 py-1 text-left text-[12px] font-semibold text-white shadow-[0_8px_24px_rgba(0,0,0,0.45)] transition hover:border-[#58A6FF]/70 hover:scale-[1.01]"
                  >
                    <span className="rounded-full bg-white/10 px-2 py-[2px] text-[10px] font-semibold uppercase tracking-wide text-blue-200">
                      {item.source === "filing" ? "오늘 공시" : item.source === "profile" ? "관심기반" : "추천"}
                    </span>
                    <span className="whitespace-normal">{item.question}</span>
                  </button>
                ))}
              </div>
            </div>
            <div className="flex flex-wrap gap-3 rounded-2xl border border-[#2d333b] bg-[#0d1117]/60 px-4 py-3 text-xs text-slate-200 shadow-[0_8px_24px_rgba(0,0,0,0.45)] backdrop-blur">
              <p className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-400">나의 관심 태그</p>
              <div className="flex flex-wrap items-center gap-2">
                {profileError ? <span className="text-[11px] text-rose-300">{profileError}</span> : null}
                {!profileError && profileTags.length === 0 ? (
                  <span className="text-[11px] text-slate-500">아직 저장된 관심 태그가 없습니다.</span>
                ) : null}
                {profileTags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-[#30363D] bg-[#161b22] px-3 py-1 text-[12px] font-semibold text-white"
                  >
                    {tag}
                  </span>
                ))}
              </div>
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
