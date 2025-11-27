"use client";

import { useState } from "react";

import { ChatHistoryList } from "@/components/chat/ChatHistoryList";
import { ChatStreamPane } from "@/components/chat/ChatStreamPane";
import { PlanTrialBanner } from "@/components/plan/PlanTrialBanner";
import type { ChatController } from "@/hooks/useChatController";

type ChatPageShellProps = {
  controller: ChatController;
  reportAction?: {
    onOpen: () => void;
    disabled?: boolean;
    loading?: boolean;
  };
  guestBadge?: React.ReactNode;
};

export function ChatPageShell({ controller, reportAction, guestBadge }: ChatPageShellProps) {
  const {
    plan,
    quotaNotice,
    history,
    stream,
    actions: { openPlanSettings },
  } = controller;
  const [focusMode, setFocusMode] = useState(false);

  if (plan.initialized && !plan.ragEnabled) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center px-6">
        <PlanTrialBanner
          currentTier={plan.tier}
          title="AI 애널리스트는 Pro 플랜에서 열립니다."
          description="근거 기반 Q&A, 증거 Diff, LightMem 문맥 유지는 Pro 업그레이드 후 이용할 수 있어요."
          errorMessage={plan.error}
          onUpgrade={openPlanSettings}
        />
      </div>
    );
  }

  return (
    <>
      {quotaNotice.notice ? (
        <QuotaNotice
          message={quotaNotice.notice.message}
          planLabel={quotaNotice.planLabel}
          limit={quotaNotice.limit}
          resetText={quotaNotice.resetText}
          onRedirect={openPlanSettings}
          onDismiss={quotaNotice.onDismiss}
          dimmed={focusMode}
        />
      ) : null}
      <div className="mx-auto w-full max-w-6xl px-2 pb-6 sm:px-4 md:px-6">
        <div className="grid gap-4 xl:grid-cols-12">
          <div className="xl:col-span-4">
            <ChatHistoryList
              sessions={history.sessions}
              selectedId={history.selectedId ?? undefined}
              onSelect={history.onSelect}
              onNewSession={history.onCreate}
              onDeleteSession={history.onDelete}
              onClearAll={history.onClear}
              persistenceError={history.persistenceError ?? undefined}
              disabled={history.disabled}
              dimmed={focusMode}
              footer={guestBadge}
            />
          </div>
          <div className="xl:col-span-8">
            <ChatStreamPane
              sessionTitle={stream.title}
              contextSummary={stream.contextSummary ?? null}
              hasContextBanner={stream.hasContextBanner}
              isFilingContext={stream.isFilingContext}
              filingReferenceId={stream.filingReferenceId ?? undefined}
              onOpenFiling={stream.onOpenFiling}
              disclaimer={stream.disclaimer}
              messages={stream.messages}
              showEmptyState={stream.showEmptyState}
              onRetry={stream.onRetry}
              onSend={stream.onSend}
              inputDisabled={stream.inputDisabled}
              reportAction={reportAction}
              onFocusChange={setFocusMode}
            />
          </div>
        </div>
      </div>
    </>
  );
}

type QuotaNoticeProps = {
  message: string;
  planLabel: string;
  limit: number | null;
  resetText: string;
  onRedirect: () => void;
  onDismiss: () => void;
  dimmed?: boolean;
};

function QuotaNotice({ message, planLabel, limit, resetText, onRedirect, onDismiss, dimmed }: QuotaNoticeProps) {
  return (
    <div
      className={`mb-8 rounded-2xl border border-amber-400/30 bg-amber-500/10 p-4 text-sm text-amber-50 shadow-[0_20px_80px_rgba(12,8,0,0.35)]${dimmed ? " focused-mode" : ""}`}
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="font-semibold text-white">{message}</p>
          <p className="mt-1 text-xs text-amber-100/80">
            {limit
              ? `${planLabel} 플랜 하루 ${limit.toLocaleString("ko-KR")}회 한도가 모두 사용되었어요.`
              : `${planLabel} 플랜 하루 한도가 모두 사용되었어요.`}{" "}
            {resetText}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-full border border-white/30 bg-white/10 px-4 py-2 text-xs font-semibold text-white transition hover:bg-white/20"
            onClick={onRedirect}
          >
            플랜 카드로 이동
          </button>
          <button
            type="button"
            className="rounded-full border border-white/10 px-4 py-2 text-xs font-semibold text-white/80 transition hover:border-white/30 hover:text-white"
            onClick={onDismiss}
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}
