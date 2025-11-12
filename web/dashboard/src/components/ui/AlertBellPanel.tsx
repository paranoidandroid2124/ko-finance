"use client";

import clsx from "classnames";
import { motion } from "framer-motion";
import { Copy, Edit3, PauseCircle, Pin, PinOff, PlayCircle, Trash2, X } from "lucide-react";
import { AlertBuilder } from "@/components/alerts/AlertBuilder";
import { UNKNOWN_PLAN_COPY } from "@/components/alerts/planMessaging";
import type { AlertBellPanelProps } from "./useAlertBellController";
import type { DashboardAlert } from "@/hooks/useDashboardOverview";
import type { AlertRule } from "@/lib/alertsApi";

const toneStyles: Record<DashboardAlert["tone"], string> = {
  positive: "bg-accent-positive/15 text-accent-positive",
  negative: "bg-accent-negative/15 text-accent-negative",
  warning: "bg-accent-warning/20 text-accent-warning",
  neutral: "bg-border-light/60 text-text-secondaryLight dark:bg-border-dark/60 dark:text-text-secondaryDark",
};

const toneLabelMap: Record<DashboardAlert["tone"], string> = {
  positive: "긍정",
  negative: "부정",
  warning: "주의",
  neutral: "중립",
};

export function AlertBellPanel({
  containerId,
  isPinned,
  onTogglePin,
  onClose,
  builder,
  planSummary,
  alerts,
  rules,
  chat,
}: AlertBellPanelProps) {
  return (
    <motion.div
      key="alert-panel"
      id={containerId}
      role="dialog"
      aria-label="실시간 소식 알림"
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ type: "spring", stiffness: 320, damping: 26 }}
      className="absolute right-0 top-[calc(100%+12px)] z-50 w-[384px] max-w-[90vw] rounded-2xl border border-border-light bg-background-cardLight p-4 shadow-xl ring-1 ring-black/5 dark:border-border-dark dark:bg-background-cardDark"
    >
      <AlertBellHeader isPinned={isPinned} onTogglePin={onTogglePin} onClose={onClose} />
      <div className="mt-4 space-y-3">
        <AlertsSection {...alerts} />
        <RulesSection builder={builder} planSummary={planSummary} rules={rules} />
        <ChatSection {...chat} />
      </div>
    </motion.div>
  );
}

type AlertBellHeaderProps = {
  isPinned: boolean;
  onTogglePin: () => void;
  onClose: () => void;
};

function AlertBellHeader({ isPinned, onTogglePin, onClose }: AlertBellHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">방금 들어온 소식</p>
        <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">최신 공시와 뉴스 소식을 한자리에서 모아드려요.</p>
      </div>
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={onTogglePin}
          className="rounded-full p-1 text-text-secondaryLight transition hover:bg-border-light/40 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:text-text-secondaryDark dark:hover:bg-border-dark/50"
        >
          {isPinned ? <Pin className="h-4 w-4" aria-hidden /> : <PinOff className="h-4 w-4" aria-hidden />}
          <span className="sr-only">{isPinned ? "핀 해제" : "핀 고정"}</span>
        </button>
        <button
          type="button"
          onClick={onClose}
          className="rounded-full p-1 text-text-secondaryLight transition hover:bg-border-light/40 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:text-text-secondaryDark dark:hover:bg-border-dark/50"
        >
          <X className="h-4 w-4" aria-hidden />
          <span className="sr-only">패널 닫기</span>
        </button>
      </div>
    </div>
  );
}

type AlertsSectionProps = AlertBellPanelProps["alerts"];

function AlertsSection({ visibleAlerts, readAlertIds, isLoading, isError, onNavigate }: AlertsSectionProps) {
  return (
    <section className="rounded-xl border border-border-light/70 bg-white/70 px-3 py-3 dark:border-border-dark/70 dark:bg-white/5">
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={`alert-skeleton-${index}`} className="space-y-2">
              <div className="h-3 w-24 rounded bg-border-light/70 dark:bg-border-dark/60" />
              <div className="h-3 w-full rounded bg-border-light/60 dark:bg-border-dark/50" />
              <div className="h-2 w-20 rounded bg-border-light/50 dark:bg-border-dark/40" />
            </div>
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-4 text-xs text-destructive dark:border-destructive/60 dark:bg-destructive/10">
          대시보드 알림을 잠깐 불러오지 못했어요. 잠시 후 다시 불러오거나 우리에게 알려주세요.
        </div>
      ) : visibleAlerts.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border-light px-3 py-4 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
          아직 도착한 알림이 없어요. 데이터가 들어오면 가장 먼저 알려드릴게요.
        </div>
      ) : (
        <div className="max-h-64 space-y-2 overflow-y-auto pr-1">
          {visibleAlerts.map((alert) => {
            const isRead = readAlertIds.has(alert.id);
            return (
              <button
                key={alert.id}
                type="button"
                className={clsx(
                  "w-full rounded-lg border border-border-light/60 px-3 py-2 text-left text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-border-dark/60",
                  "hover:border-primary hover:text-primary dark:hover:border-primary.dark dark:hover:text-primary.dark",
                  isRead ? "bg-white/40 text-text-secondaryLight dark:bg-white/5 dark:text-text-secondaryDark" : "bg-white/80 dark:bg-white/10",
                )}
                onClick={() => onNavigate(alert)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium leading-tight">{alert.title}</p>
                    <p className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">{alert.body}</p>
                  </div>
                  {alert.tone ? (
                    <span
                      className={clsx(
                        "inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold",
                        toneStyles[alert.tone],
                      )}
                    >
                      {toneLabelMap[alert.tone] ?? alert.tone}
                    </span>
                  ) : null}
                </div>
                <p className="mt-2 text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">{alert.timestamp}</p>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}

type RulesSectionProps = {
  builder: AlertBellPanelProps["builder"];
  planSummary: AlertBellPanelProps["planSummary"];
  rules: AlertBellPanelProps["rules"];
};

function RulesSection({ builder, planSummary, rules }: RulesSectionProps) {
  return (
    <section className="rounded-xl border border-border-light/70 bg-white/70 px-4 py-4 dark:border-border-dark/70 dark:bg-background-cardDark/60">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">내가 만든 알림</p>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            {planSummary.alertPlan
              ? builder.mode === "create" && planSummary.builderQuotaReached
                ? planSummary.bellCopy.quotaToast.description(planSummary.quotaInfo)
                : planSummary.maxRules > 0
                ? `남은 슬롯 ${Math.max(planSummary.remainingSlots, 0).toLocaleString(
                    "ko-KR",
                  )}개 / 총 ${planSummary.maxRules.toLocaleString("ko-KR")}개 · 채널: ${planSummary.alertChannelSummary}`
                : `채널: ${planSummary.alertChannelSummary}`
              : UNKNOWN_PLAN_COPY.bell.disabledHint}
          </p>
        </div>
        <button
          type="button"
          disabled={builder.isDisabled}
          data-focus-return="alerts-builder-create"
          onClick={(event) => builder.onOpenCreate(event.currentTarget)}
          title={builder.isDisabled ? builder.disabledReason : undefined}
          aria-label={builder.isDisabled ? builder.disabledReason : builder.ctaLabel}
          aria-expanded={!builder.isDisabled ? builder.isOpen && builder.mode === "create" : undefined}
          aria-pressed={!builder.isDisabled ? builder.isOpen && builder.mode === "create" : undefined}
          className={clsx(
            "rounded-lg border border-border-light/70 bg-white/70 px-3 py-1.5 text-xs font-semibold text-text-primaryLight transition hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-primaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark",
            builder.isOpen && builder.mode === "create" && !builder.isDisabled
              ? "border-primary text-primary dark:border-primary.dark dark:text-primary.dark"
              : null,
            builder.isDisabled &&
              "cursor-not-allowed opacity-60 hover:border-border-light hover:text-text-primaryLight dark:hover:text-text-primaryDark",
          )}
        >
          {builder.ctaLabel}
        </button>
      </div>
      {builder.isDisabled ? (
        <p className="mt-2 text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
          {builder.disabledReason} {builder.disabledHint}
        </p>
      ) : null}

      <div className="mt-3 space-y-3">
        {rules.isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 2 }).map((_, index) => (
              <div
                key={`alert-rule-skeleton-${index}`}
                className="h-14 animate-pulse rounded-lg bg-border-light/30 dark:bg-border-dark/30"
              />
            ))}
          </div>
        ) : rules.isError ? (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-3 text-xs text-destructive dark:border-destructive/60 dark:bg-destructive/20">
            사용자 알림을 잠깐 불러오지 못했어요. 새로고침 후 다시 시도하거나 우리에게 알려주세요.
          </div>
        ) : null}

        {builder.isOpen && builder.plan ? (
        <AlertBuilder
          plan={builder.plan}
          existingCount={builder.existingCount}
          editingRule={builder.mode === "create" ? null : builder.editingRule}
          mode={builder.mode}
          onSuccess={builder.onSuccess}
          onCancel={builder.onCancel}
          onRequestUpgrade={builder.onRequestUpgrade}
        />
        ) : null}

        {!builder.isOpen && !rules.isLoading && !rules.isError ? (
          rules.rules.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border-light/70 px-3 py-4 text-xs text-text-secondaryLight dark:border-border-dark/70 dark:text-text-secondaryDark">
              아직 만든 알림이 없어요. “새 알림 만들기” 버튼으로 관심 기업 소식을 자동으로 받아보세요.
            </div>
          ) : (
            <div className="space-y-3">
              {rules.rules.map((rule) => {
                const isRuleMutating = rules.mutatingRuleId === rule.id;
                const statusBadge =
                  rule.status === "active"
                    ? "bg-emerald-500/15 text-emerald-600 dark:bg-emerald-400/15 dark:text-emerald-200"
                    : "bg-border-light/60 text-text-secondaryLight dark:bg-border-dark/60 dark:text-text-secondaryDark";
                const isEditingThisRule = builder.isOpen && builder.editingRule?.id === rule.id;
                const focusBase = encodeURIComponent(rule.id);
                return (
                  <motion.div
                    key={rule.id}
                    layout
                    className={clsx(
                      "rounded-lg border border-border-light/70 bg-white/80 p-3 text-sm shadow-sm transition dark:border-border-dark/70 dark:bg-background-cardDark",
                      isEditingThisRule && "border-primary/60 ring-1 ring-primary/40 dark:border-primary.dark/60",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <p className="truncate font-semibold text-text-primaryLight dark:text-text-primaryDark">
                            {rule.name}
                          </p>
                          <span
                            className={clsx(
                              "inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold",
                              statusBadge,
                            )}
                          >
                            {rule.status === "active" ? "활성" : "일시중지"}
                          </span>
                        </div>
                        <p className="mt-1 truncate text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                          {formatRuleSubtitle(rule)}
                        </p>
                        <p className="text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                          채널: {formatChannelsLabel(rule)}
                        </p>
                        <p className="text-[11px] text-text-ter티aryLight dark:text-text-tertiaryDark">
                          최근 발송: {formatTimestamp(rule.lastTriggeredAt)}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          disabled={isRuleMutating}
                          data-focus-return={`alerts-rule-${focusBase}-edit`}
                          onClick={(event) => rules.onEdit(rule, event.currentTarget)}
                          title="알림 수정"
                          aria-label="알림 수정"
                          className="rounded-full border border-border-light/70 bg-white/70 p-2 text-text-secondaryLight transition hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
                        >
                          <Edit3 className="h-4 w-4" aria-hidden />
                          <span className="sr-only">알림 수정</span>
                        </button>
                        <button
                          type="button"
                          disabled={isRuleMutating}
                          data-focus-return={`alerts-rule-${focusBase}-duplicate`}
                          onClick={(event) => rules.onDuplicate(rule, event.currentTarget)}
                          title="알림 복제"
                          aria-label="알림 복제"
                          className="rounded-full border border-border-light/70 bg-white/70 p-2 text-text-secondaryLight transition hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
                        >
                          <Copy className="h-4 w-4" aria-hidden />
                          <span className="sr-only">알림 복제</span>
                        </button>
                        <button
                          type="button"
                          disabled={isRuleMutating}
                          onClick={() => rules.onToggle(rule)}
                          title={rule.status === "active" ? "알림 일시 중지" : "알림 다시 시작"}
                          aria-label={rule.status === "active" ? "알림 일시 중지" : "알림 다시 시작"}
                          className="rounded-full border border-border-light/70 bg-white/70 p-2 text-text-secondaryLight transition hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
                        >
                          {rule.status === "active" ? (
                            <PauseCircle className="h-4 w-4" aria-hidden />
                          ) : (
                            <PlayCircle className="h-4 w-4" aria-hidden />
                          )}
                          <span className="sr-only">
                            {rule.status === "active" ? "알림 일시 중지" : "알림 다시 시작"}
                          </span>
                        </button>
                        <button
                          type="button"
                          disabled={isRuleMutating}
                          onClick={() => rules.onDelete(rule)}
                          title="알림 삭제"
                          aria-label="알림 삭제"
                          className="rounded-full border border-border-light/70 bg-white/70 p-2 text-text-secondaryLight transition hover:border-destructive hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-secondaryDark dark:hover:border-destructive dark:hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" aria-hidden />
                          <span className="sr-only">알림 삭제</span>
                        </button>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          )
        ) : null}
      </div>
    </section>
  );
}

type ChatSectionProps = AlertBellPanelProps["chat"];

function ChatSection({ activeSession, otherSessions, onSelect, onStartNew }: ChatSectionProps) {
  return (
    <section className="rounded-xl border border-border-light/70 bg-gradient-to-br from-primary/12 via-background-cardLight to-white px-4 py-4 shadow-sm dark:border-border-dark/70 dark:from-primary.dark/15 dark:via-background-cardDark dark:to-background-cardDark">
      <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">대화 메모</p>
      <p className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
        채팅으로 공시와 뉴스를 빠르게 정리하고 필요한 인사이트를 함께 찾아보세요.
      </p>
      <button
        type="button"
        onClick={onStartNew}
        className="mt-3 inline-flex w-full items-center justify-center rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white shadow transition hover:scale-[1.02] hover:bg-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-background-cardDark"
      >
        새 대화 열기
      </button>
      <div className="mt-3 space-y-2 text-sm">
        <div className="rounded-lg border border-border-light/70 bg-white/70 px-3 py-3 dark:border-border-dark/70 dark:bg-white/10">
          <p className="text-xs uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
            현재 세션
          </p>
          <p className="mt-1 font-medium text-text-primaryLight dark:text-text-primaryDark">
            {activeSession ? activeSession.title : "열어둔 대화가 아직 없어요"}
          </p>
          <p className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
            {activeSession?.updatedAt ?? "최근 대화 기록이 아직 없어요"}
          </p>
        </div>
        {otherSessions.length > 0 ? (
          <div>
            <p className="text-xs font-semibold text-text-secondaryLight dark:text-text-secondaryDark">최근 세션</p>
            <div className="mt-2 space-y-2">
              {otherSessions.map((session) => (
                <button
                  key={session.id}
                  type="button"
                  onClick={() => onSelect(session.id)}
                  className="w-full rounded-lg border border-border-light/70 bg-background-cardLight px-3 py-2 text-left text-[13px] font-medium text-text-primaryLight transition hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-primaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
                >
                  <span className="block truncate">{session.title}</span>
                  <span className="text-[11px] font-normal text-text-secondaryLight dark:text-text-secondaryDark">
                    {session.updatedAt}
                  </span>
                </button>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

const formatRuleSubtitle = (rule: AlertRule) => {
  const tickers = rule.condition?.tickers?.length ? rule.condition.tickers.join(", ") : "전체";
  const label = rule.condition?.type === "news" ? "뉴스" : "공시";
  return `${label} · ${tickers}`;
};

const formatChannelsLabel = (rule: AlertRule) => {
  if (!rule.channels?.length) {
    return "채널 없음";
  }
  return rule.channels
    .map((channel) => {
      const totalTargets = channel.targets?.length ?? (channel.target ? 1 : 0);
      return totalTargets > 1 ? `${channel.type}×${totalTargets}` : channel.type;
    })
    .join(", ");
};

const formatTimestamp = (value: string | null) => {
  if (!value) {
    return "발송 이력 없음";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "발송 이력 없음";
  }
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
};
