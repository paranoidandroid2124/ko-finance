"use client";

import clsx from "clsx";
import { Edit3, PauseCircle, PlayCircle, Send, Trash2 } from "lucide-react";

import type { AlertPlanInfo, AlertRule } from "@/lib/alertsApi";

type WatchlistRuleManagerProps = {
  plan: AlertPlanInfo | null;
  rules: AlertRule[];
  isLoading: boolean;
  isError: boolean;
  mutatingRuleId: string | null;
  onCreate: () => void;
  onEdit: (rule: AlertRule) => void;
  onToggle: (rule: AlertRule) => void;
  onDelete: (rule: AlertRule) => void;
  onShareToDigest?: (rule: AlertRule) => void;
};

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

export function WatchlistRuleManager({
  plan,
  rules,
  isLoading,
  isError,
  mutatingRuleId,
  onCreate,
  onEdit,
  onToggle,
  onDelete,
  onShareToDigest,
}: WatchlistRuleManagerProps) {
  const remainingLabel =
    plan && plan.maxAlerts > 0
      ? `남은 슬롯 ${Math.max(plan.remainingAlerts, 0).toLocaleString("ko-KR")}개 / 총 ${plan.maxAlerts.toLocaleString(
          "ko-KR",
        )}개`
      : null;
  const channelSummary = plan?.channels?.length ? `채널: ${plan.channels.join(", ")}` : null;

  return (
    <section className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card transition dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="space-y-1">
          <p className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">내가 만든 알림</p>
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            워치리스트 마법사로 생성한 알림 룰을 한곳에서 관리하세요.
          </p>
          <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
            {[remainingLabel, channelSummary].filter(Boolean).join(" · ")}
          </p>
        </div>
        <button
          type="button"
          onClick={onCreate}
          className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow transition hover:-translate-y-0.5 hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 dark:bg-primary.dark dark:hover:bg-primary.dark/90"
        >
          새 알림 만들기
        </button>
      </div>

      <div className="mt-4 space-y-3">
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, index) => (
              <div
                key={`watchlist-rule-skeleton-${index}`}
                className="h-16 animate-pulse rounded-xl border border-border-light/70 bg-border-light/30 dark:border-border-dark/70 dark:bg-border-dark/30"
              />
            ))}
          </div>
        ) : isError ? (
          <div className="rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive dark:border-destructive/60 dark:bg-destructive/15">
            알림 룰 정보를 불러오지 못했어요. 새로고침 후 다시 시도해 주세요.
          </div>
        ) : rules.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border-light/70 bg-background-light/40 px-4 py-8 text-center text-sm text-text-secondaryLight dark:border-border-dark/70 dark:bg-background-dark/40 dark:text-text-secondaryDark">
            아직 생성한 알림 룰이 없습니다. 오른쪽 버튼을 눌러 첫 알림을 만들어 보세요.
          </div>
        ) : (
          rules.map((rule) => {
            const statusBadge =
              rule.status === "active"
                ? "bg-emerald-500/15 text-emerald-600 dark:bg-emerald-400/15 dark:text-emerald-200"
                : "bg-border-light/60 text-text-secondaryLight dark:bg-border-dark/60 dark:text-text-secondaryDark";
            const isMutating = mutatingRuleId === rule.id;
            return (
              <div
                key={rule.id}
                className="flex flex-col gap-3 rounded-xl border border-border-light/70 bg-background-base p-4 shadow-sm transition hover:border-primary/50 dark:border-border-dark/70 dark:bg-background-cardDark"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1 space-y-1">
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
                    <p className="truncate text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                      {formatRuleSubtitle(rule)}
                    </p>
                    <p className="text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                      채널: {formatChannelsLabel(rule)}
                    </p>
                    <p className="text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                      최근 발송: {formatTimestamp(rule.lastTriggeredAt)}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {onShareToDigest ? (
                      <button
                        type="button"
                        disabled={isMutating}
                        onClick={() => onShareToDigest(rule)}
                        className="rounded-full border border-border-light/70 bg-white/70 p-2 text-text-secondaryLight transition hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
                      >
                        <Send className="h-4 w-4" aria-hidden />
                        <span className="sr-only">다이제스트로 공유</span>
                      </button>
                    ) : null}
                    <button
                      type="button"
                      disabled={isMutating}
                      onClick={() => onEdit(rule)}
                      className="rounded-full border border-border-light/70 bg-white/70 p-2 text-text-secondaryLight transition hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
                    >
                      <Edit3 className="h-4 w-4" aria-hidden />
                      <span className="sr-only">알림 수정</span>
                    </button>
                    <button
                      type="button"
                      disabled={isMutating}
                      onClick={() => onToggle(rule)}
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
                      disabled={isMutating}
                      onClick={() => onDelete(rule)}
                      className="rounded-full border border-border-light/70 bg-white/70 p-2 text-text-secondaryLight transition hover:border-destructive hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-secondaryDark dark:hover:border-destructive dark:hover:text-destructive"
                    >
                      <Trash2 className="h-4 w-4" aria-hidden />
                      <span className="sr-only">알림 삭제</span>
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
