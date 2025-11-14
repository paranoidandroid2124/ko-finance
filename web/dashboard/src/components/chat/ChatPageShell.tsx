"use client";

import { AppShell } from "@/components/layout/AppShell";
import { ChatHistoryList } from "@/components/chat/ChatHistoryList";
import { ChatContextPane } from "@/components/chat/ChatContextPane";
import { ChatStreamPane } from "@/components/chat/ChatStreamPane";
import { PlanInfoCard } from "@/components/plan/PlanInfoCard";
import { PlanTrialBanner } from "@/components/plan/PlanTrialBanner";
import type { ChatController } from "@/hooks/useChatController";

type ChatPageShellProps = {
  controller: ChatController;
};

export function ChatPageShell({ controller }: ChatPageShellProps) {
  const {
    plan,
    quotaNotice,
    history,
    stream,
    actions: { openPlanSettings },
  } = controller;

  if (!plan.initialized) {
    return (
      <AppShell>
        <div className="flex min-h-[60vh] items-center justify-center px-6">
          <PlanInfoCard
            title="플랜 정보를 초기화하는 중입니다."
            description={plan.loading ? "플랜 정보를 불러오는 중입니다…" : "플랜 정보를 초기화하는 중입니다."}
            loading={plan.loading}
            planTier={plan.tier}
          />
        </div>
      </AppShell>
    );
  }

  if (!plan.ragEnabled) {
    return (
      <AppShell>
        <div className="flex min-h-[60vh] items-center justify-center px-6">
          <PlanTrialBanner
            currentTier={plan.tier}
            title="AI 애널리스트는 Pro 플랜에서 열립니다."
            description="근거 기반 Q&A, 증거 Diff, LightMem 문맥 유지는 Pro 업그레이드 후 이용할 수 있어요."
            errorMessage={plan.error}
            onUpgrade={openPlanSettings}
          />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      {quotaNotice.notice ? (
        <QuotaNotice
          message={quotaNotice.notice.message}
          planLabel={quotaNotice.planLabel}
          limit={quotaNotice.limit}
          resetText={quotaNotice.resetText}
          onRedirect={openPlanSettings}
          onDismiss={quotaNotice.onDismiss}
        />
      ) : null}
      <div className="flex flex-col gap-6 lg:flex-row">
        <ChatHistoryList
          sessions={history.sessions}
          selectedId={history.selectedId ?? undefined}
          onSelect={history.onSelect}
          onNewSession={history.onCreate}
          onDeleteSession={history.onDelete}
          onClearAll={history.onClear}
          persistenceError={history.persistenceError ?? undefined}
          disabled={history.disabled}
        />
        <ChatStreamPane
          sessionTitle={stream.title}
          contextSummary={stream.contextSummary}
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
        />
        <ChatContextPane />
      </div>
    </AppShell>
  );
}

type QuotaNoticeProps = {
  message: string;
  planLabel: string;
  limit: number | null;
  resetText: string;
  onRedirect: () => void;
  onDismiss: () => void;
};

function QuotaNotice({ message, planLabel, limit, resetText, onRedirect, onDismiss }: QuotaNoticeProps) {
  return (
    <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 shadow-card dark:border-amber-400/60 dark:bg-amber-950/40 dark:text-amber-100">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="font-semibold text-amber-900 dark:text-amber-50">{message}</p>
          <p className="mt-1 text-xs text-amber-800 dark:text-amber-200">
            {limit
              ? `${planLabel} 플랜 하루 ${limit.toLocaleString("ko-KR")}회 한도가 모두 사용되었어요.`
              : `${planLabel} 플랜 하루 한도가 모두 사용되었어요.`}{" "}
            {resetText}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-lg border border-primary bg-primary px-4 py-2 text-xs font-semibold text-white transition hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            onClick={onRedirect}
          >
            플랜 카드로 이동
          </button>
          <button
            type="button"
            className="rounded-lg border border-amber-300 px-4 py-2 text-xs font-semibold text-amber-900 transition hover:bg-amber-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-400 dark:border-amber-500 dark:text-amber-100 dark:hover:bg-amber-500/10"
            onClick={onDismiss}
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}

