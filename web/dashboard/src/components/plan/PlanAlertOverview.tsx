"use client";

import clsx from "classnames";
import type { AlertPlanInfo } from "@/lib/alertsApi";

const CHANNEL_LABELS: Record<string, string> = {
  email: "이메일",
  telegram: "텔레그램",
  slack: "슬랙",
  webhook: "Webhook",
  pagerduty: "PagerDuty",
};

type PlanAlertOverviewProps = {
  plan: AlertPlanInfo | null | undefined;
  loading?: boolean;
  error?: string;
  className?: string;
};

const friendlyChannel = (channel: string) => CHANNEL_LABELS[channel] ?? channel;

const friendlyNumber = (value: number | null | undefined, suffix = "") => {
  if (value === null || value === undefined) {
    return "무제한";
  }
  return `${value.toLocaleString("ko-KR")}${suffix}`;
};

export function PlanAlertOverview({ plan, loading, error, className }: PlanAlertOverviewProps) {
  if (loading) {
    return (
      <section
        className={clsx(
          "space-y-4 rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark",
          className,
        )}
      >
        <div className="h-5 w-32 animate-pulse rounded bg-border-light/70 dark:bg-border-dark/60" />
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <div
              key={`alert-overview-skeleton-${index}`}
              className="h-16 animate-pulse rounded-lg bg-border-light/40 dark:bg-border-dark/40"
            />
          ))}
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section
        className={clsx(
          "rounded-xl border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive shadow-card dark:border-destructive/60 dark:bg-destructive/20",
          className,
        )}
      >
        <p>알림 플랜 정보를 불러오는 데 잠깐 차질이 생겼어요. 잠시 후 다시 확인하거나 관리자에게 알려주세요.</p>
        <p className="mt-1 text-xs opacity-80">{error}</p>
      </section>
    );
  }

  if (!plan) {
    return (
      <section
        className={clsx(
          "rounded-xl border border-border-light bg-background-cardLight p-6 text-sm text-text-secondaryLight shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark dark:text-text-secondaryDark",
          className,
        )}
      >
        아직 알림 플랜 정보가 도착하지 않았어요. 잠시 뒤 새로고침하면 함께 살펴볼 수 있어요.
      </section>
    );
  }

  const channelList = plan.channels.length ? plan.channels.map(friendlyChannel) : ["허용된 채널이 없어요."];

  return (
    <section
      className={clsx(
        "space-y-5 rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark",
        className,
      )}
    >
      <header className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
            알림 기본값
          </p>
          <h2 className="mt-1 text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">
            플랜에 맞춘 자동화 한도
          </h2>
          <p className="mt-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            지금 남은 슬롯과 채널 허용 범위를 한눈에 살펴볼 수 있도록 정리했어요.
          </p>
        </div>
        <div className="rounded-lg bg-background-cardDark/5 px-3 py-2 text-xs text-text-secondaryLight dark:bg-white/10 dark:text-text-secondaryDark">
          남은 슬롯&nbsp;
          <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
            {friendlyNumber(plan.remainingAlerts, "개")}
          </span>
        </div>
      </header>

      <div className="grid gap-3 sm:grid-cols-2">
        <CardItem label="최대 알림 수" value={friendlyNumber(plan.maxAlerts, "개")} />
        <CardItem label="하루 발송 제한" value={friendlyNumber(plan.maxDailyTriggers ?? null, "회")} />
        <CardItem label="평가 주기 기본값" value={`${plan.defaultEvaluationIntervalMinutes}분`} />
        <CardItem label="탐색 윈도우" value={`${plan.defaultWindowMinutes}분`} />
        <CardItem label="쿨다운" value={`${plan.defaultCooldownMinutes}분`} />
        <CardItem label="평가 최소 간격" value={`${plan.minEvaluationIntervalMinutes}분`} />
      </div>

      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
          사용할 수 있는 채널
        </h3>
        <div className="mt-2 flex flex-wrap gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          {channelList.map((channel) => (
            <span
              key={channel}
              className="rounded-full border border-border-light px-2 py-0.5 dark:border-border-dark"
            >
              {channel}
            </span>
          ))}
        </div>
      </section>
    </section>
  );
}

function CardItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border-light/70 bg-white/70 px-3 py-3 text-sm text-text-secondaryLight shadow-sm transition dark:border-border-dark/70 dark:bg-white/5 dark:text-text-secondaryDark">
      <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
        {label}
      </p>
      <p className="mt-1 text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">{value}</p>
    </div>
  );
}
