"use client";

import clsx from "clsx";
import { useMemo, useState } from "react";
import { AlertTriangle, BarChart3, Edit3, PauseCircle, PlayCircle, Send, Trash2, X } from "lucide-react";

import type { AlertPlanInfo, AlertRule, AlertRuleStats } from "@/lib/alertsApi";
import { useAlertRuleStats } from "@/hooks/useAlerts";

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

type RuleFilter = "all" | "issues";

const CHANNEL_LABELS: Record<string, string> = {
  email: "이메일",
  slack: "Slack",
  telegram: "텔레그램",
  webhook: "웹훅",
  pagerduty: "PagerDuty",
};

const formatRuleSubtitle = (rule: AlertRule) => {
  const tickers = rule.trigger?.tickers?.length ? rule.trigger.tickers.join(", ") : "전체";
  const label = rule.trigger?.type === "news" ? "뉴스" : "공시";
  return `${label} · ${tickers}`;
};

const formatChannelsLabel = (rule: AlertRule) => {
  if (!rule.channels?.length) {
    return "채널 없음";
  }
  return rule.channels
    .map((channel) => {
      const totalTargets = channel.targets?.length ?? (channel.target ? 1 : 0);
      const label = CHANNEL_LABELS[channel.type] ?? channel.type;
      return totalTargets > 1 ? `${label}×${totalTargets}` : label;
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

const formatRetryLabel = (retryAfter?: string | null) => {
  if (!retryAfter) {
    return null;
  }
  const date = new Date(retryAfter);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  const diffMs = date.getTime() - Date.now();
  if (diffMs <= 0) {
    return "곧 재시도";
  }
  const minutes = Math.round(diffMs / 60000);
  if (minutes >= 60) {
    const hours = Math.round(minutes / 60);
    return `${hours}시간 뒤 재시도`;
  }
  return `${minutes}분 뒤 재시도`;
};

const resolveFailureEntries = (rule: AlertRule) => {
  return Object.entries(rule.channelFailures ?? {})
    .map(([channel, meta]) => ({
      channel,
      status: meta?.status ?? "failed",
      error: meta?.error ?? "전송 실패",
      retryAfter: meta?.retryAfter,
    }))
    .sort((a, b) => {
      const aTime = a.retryAfter ? new Date(a.retryAfter).getTime() : 0;
      const bTime = b.retryAfter ? new Date(b.retryAfter).getTime() : 0;
      return aTime - bTime;
    });
};

const hasChannelIssues = (rule: AlertRule) => Object.keys(rule.channelFailures ?? {}).length > 0;

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
  const [filter, setFilter] = useState<RuleFilter>("all");
  const [statsRuleId, setStatsRuleId] = useState<string | null>(null);
  const [statsRuleName, setStatsRuleName] = useState<string>("");
  const statsWindowMinutes = 1440;
  const { data: statsData, isLoading: isStatsLoading } = useAlertRuleStats(statsRuleId, statsWindowMinutes);

  const rulesWithIssues = useMemo(() => rules.filter(hasChannelIssues), [rules]);
  const filteredRules = useMemo(() => {
    if (filter === "issues") {
      return rulesWithIssues;
    }
    return rules;
  }, [filter, rules, rulesWithIssues]);

  const remainingLabel =
    plan && plan.maxAlerts > 0
      ? `남은 슬롯 ${Math.max(plan.remainingAlerts, 0).toLocaleString("ko-KR")}개 / 총 ${plan.maxAlerts.toLocaleString("ko-KR")}개`
      : null;
  const channelSummary = plan?.channels?.length ? `채널: ${plan.channels.join(", ")}` : null;
  const issueCount = rulesWithIssues.length;

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
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-full border border-border-light/70 bg-background-base p-1 text-xs dark:border-border-dark/70 dark:bg-background-baseDark">
            <button
              type="button"
              onClick={() => setFilter("all")}
              className={clsx(
                "rounded-full px-3 py-1 font-semibold transition",
                filter === "all"
                  ? "bg-primary text-white dark:bg-primary.dark"
                  : "text-text-secondaryLight dark:text-text-secondaryDark",
              )}
            >
              전체
            </button>
            <button
              type="button"
              onClick={() => setFilter("issues")}
              className={clsx(
                "rounded-full px-3 py-1 font-semibold transition",
                filter === "issues"
                  ? "bg-amber-500 text-white dark:bg-amber-400"
                  : "text-text-secondaryLight dark:text-text-secondaryDark",
              )}
            >
              채널 이슈 {issueCount > 0 ? `(${issueCount})` : ""}
            </button>
          </div>
          <button
            type="button"
            onClick={onCreate}
            className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow transition hover:-translate-y-0.5 hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 dark:bg-primary.dark dark:hover:bg-primary.dark/90"
          >
            새 알림 만들기
          </button>
        </div>
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
        ) : filteredRules.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border-light/70 bg-background-light/40 px-4 py-8 text-center text-sm text-text-secondaryLight dark:border-border-dark/70 dark:bg-background-dark/40 dark:text-text-secondaryDark">
            {filter === "issues"
              ? "채널 이슈가 감지된 알림이 없습니다. 전체 보기에서 다른 룰을 확인하세요."
              : "아직 만든 알림 룰이 없어요. 워치리스트 룰을 만들어 처음 알림을 받아보세요."}
          </div>
        ) : (
          filteredRules.map((rule) => {
            const isMutating = mutatingRuleId === rule.id;
            const statusBadge =
              rule.status === "active"
                ? "bg-success/10 text-success ring-success/40"
                : "bg-border-light text-text-secondaryLight ring-border-light dark:bg-border-dark/70 dark:text-text-secondaryDark";
            const failureEntries = resolveFailureEntries(rule);

            return (
              <div
                key={rule.id}
                className="flex flex-col gap-3 rounded-xl border border-border-light/70 bg-background-base p-4 shadow-sm transition hover:border-primary/50 dark:border-border-dark/70 dark:bg-background-cardDark"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <p className="truncate font-semibold text-text-primaryLight dark:text-text-primaryDark">{rule.name}</p>
                      <span
                        className={clsx(
                          "inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset",
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
                    <p className="text-[11px] text-text-ter티aryLight dark:text-text-tertiaryDark">
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
                      {rule.status === "active" ? <PauseCircle className="h-4 w-4" aria-hidden /> : <PlayCircle className="h-4 w-4" aria-hidden />}
                      <span className="sr-only">{rule.status === "active" ? "알림 일시 중지" : "알림 다시 시작"}</span>
                    </button>
                    <button
                      type="button"
                      disabled={isMutating}
                      onClick={() => {
                        setStatsRuleId(rule.id);
                        setStatsRuleName(rule.name);
                      }}
                      className="rounded-full border border-border-light/70 bg-white/70 p-2 text-text-secondaryLight transition hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
                    >
                      <BarChart3 className="h-4 w-4" aria-hidden />
                      <span className="sr-only">전송 통계</span>
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

                {failureEntries.length > 0 ? (
                  <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50/80 px-3 py-2 text-xs text-amber-900 dark:border-amber-400/50 dark:bg-amber-400/10 dark:text-amber-100">
                    <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden />
                    <div className="space-y-1">
                      <p className="font-semibold">
                        채널 이슈 감지 · {Object.keys(rule.channelFailures ?? {}).length}개 채널
                      </p>
                      <ul className="space-y-1 text-[11px]">
                        {failureEntries.slice(0, 3).map((entry) => (
                          <li key={entry.channel}>
                            <span className="font-semibold">{CHANNEL_LABELS[entry.channel] ?? entry.channel.toUpperCase()}</span>{" "}
                            {entry.error}
                            {formatRetryLabel(entry.retryAfter) ? ` · ${formatRetryLabel(entry.retryAfter)}` : ""}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ) : null}
              </div>
            );
          })
        )}
      </div>

      {statsRuleId ? (
        <RuleStatsDialog
          ruleName={statsRuleName}
          loading={isStatsLoading}
          data={statsData}
          windowMinutes={statsWindowMinutes}
          onClose={() => setStatsRuleId(null)}
        />
      ) : null}
    </section>
  );
}

type RuleStatsDialogProps = {
  ruleName: string;
  loading: boolean;
  data: AlertRuleStats | undefined;
  windowMinutes: number;
  onClose: () => void;
};

function RuleStatsDialog({ ruleName, loading, data, windowMinutes, onClose }: RuleStatsDialogProps) {
  const formatter = useMemo(() => new Intl.NumberFormat("ko-KR"), []);
  const windowLabel =
    windowMinutes >= 1440 ? `${Math.round(windowMinutes / 1440)}일` : `${Math.round(windowMinutes / 60)}시간`;

  const StatCard = ({ label, value }: { label: string; value: number | undefined }) => (
    <div className="rounded-xl border border-border-light bg-background-base p-3 text-center text-sm dark:border-border-dark dark:bg-background-baseDark">
      <p className="text-xs uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-text-primaryLight dark:text-text-primaryDark">
        {loading ? "…" : formatter.format(value ?? 0)}
      </p>
    </div>
  );

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 px-4 py-8">
      <div className="w-full max-w-md rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-2xl dark:border-border-dark dark:bg-background-cardDark">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">전송 통계</p>
            <h3 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">{ruleName}</h3>
            <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">최근 {windowLabel} 기준</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-border-light p-1 text-text-secondaryLight transition hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
          >
            <X className="h-4 w-4" aria-hidden />
            <span className="sr-only">닫기</span>
          </button>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3">
          <StatCard label="총 전송" value={data?.total} />
          <StatCard label="성공" value={data?.delivered} />
          <StatCard label="실패" value={data?.failed} />
          <StatCard label="스로틀" value={data?.throttled} />
        </div>

        <div className="mt-4 rounded-xl border border-border-light bg-background-base p-4 text-sm dark:border-border-dark dark:bg-background-baseDark">
          {loading ? (
            <p className="text-text-secondaryLight dark:text-text-secondaryDark">통계를 불러오는 중입니다…</p>
          ) : data?.lastDelivery ? (
            <div className="space-y-1 text-text-secondaryLight dark:text-text-secondaryDark">
              <p className="text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
                마지막 전송
              </p>
              <p>
                상태:{" "}
                <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                  {data.lastDelivery.status}
                </span>
              </p>
              <p>채널: {CHANNEL_LABELS[data.lastDelivery.channel ?? ""] ?? data.lastDelivery.channel ?? "—"}</p>
              <p>전송 시각: {formatTimestamp(data.lastDelivery.createdAt ?? null)}</p>
              {data.lastDelivery.error ? <p>오류: {data.lastDelivery.error}</p> : null}
            </div>
          ) : (
            <p className="text-text-secondaryLight dark:text-text-secondaryDark">
              아직 통계가 없습니다. 알림이 전송되면 집계가 표시됩니다.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
