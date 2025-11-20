"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { CalendarClock, ListChecks, PlayCircle, Plus, ShieldCheck, Sparkles, X } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { WatchlistRuleManager } from "@/components/watchlist/WatchlistRuleManager";
import { WatchlistRuleWizard } from "@/components/watchlist/WatchlistRuleWizard";
import { EventMatchList } from "@/components/watchlist/EventMatchList";
import { PlanLock } from "@/components/ui/PlanLock";
import { ErrorState } from "@/components/ui/ErrorState";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { EmptyState } from "@/components/ui/EmptyState";
import { useSimulateAlertRule } from "@/hooks/useAlerts";
import {
  ApiError,
  type AlertEventMatch,
  type AlertPlanInfo,
  type AlertRule,
  type AlertRuleSimulationResponse,
} from "@/lib/alertsApi";
import { formatDateTime, formatRelativeTime } from "@/lib/date";
import { usePlanContext, isTierAtLeast } from "@/store/planStore";
import { useWatchlistAlertsController } from "./useWatchlistAlertsController";

const RECENT_EVENTS_LIMIT = 12;
const SIMULATION_DEFAULT_WINDOW_MINUTES = 7 * 24 * 60;
const SIMULATION_DEFAULT_LIMIT = 12;

// AlertsWatchlistPage enforces plan-tier gating (Pro+) via PlanContext.

function AlertsWatchlistContent({ fallbackPlanTier }: { fallbackPlanTier: string }) {
  const controller = useWatchlistAlertsController({ recentEventsLimit: RECENT_EVENTS_LIMIT });
  const { matches, isLoading: matchesLoading, errorMessage: matchesErrorMessage } = controller.matchesState;
  const { wizardState, simulationRule, mutatingRuleId, actions } = controller;
  const plan = controller.plan;

  if (controller.rulesErrorValue instanceof ApiError) {
    const apiError = controller.rulesErrorValue;
    const isPlanGuard = apiError.status === 402 || (apiError.code && apiError.code.startsWith("plan."));
    return (
      <AppShell>
        {isPlanGuard ? (
          <PlanLock requiredTier="pro" title="알림 · 워치리스트" description={apiError.message} />
        ) : (
          <ErrorState title="알림 · 워치리스트" description={apiError.message} />
        )}
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <AlertsHero
          plan={plan}
          fallbackPlanTier={fallbackPlanTier}
          totalRules={controller.totalRules}
          onCreateRule={actions.openWizard}
          onOpenWizard={actions.openWizard}
        />

        <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
          <div className="space-y-4">
            <WatchlistRuleManager
              plan={plan}
              rules={controller.rules}
              isLoading={controller.rulesLoading}
              isError={controller.rulesError}
              mutatingRuleId={mutatingRuleId}
              onCreate={actions.openWizard}
              onEdit={actions.editRule}
              onToggle={actions.toggleRule}
              onDelete={actions.deleteRule}
              onSimulate={actions.simulateRule}
            />
          </div>
          <div className="space-y-4">
            <EventActivityPanel matches={matches} loading={matchesLoading} errorMessage={matchesErrorMessage} />
            <PlanLimitCard plan={plan} fallbackPlanTier={fallbackPlanTier} />
          </div>
        </div>
      </div>

      <WatchlistRuleWizard
        open={wizardState.open}
        mode={wizardState.mode}
        initialRule={wizardState.initialRule}
        onClose={actions.closeWizard}
        onCompleted={actions.completeWizard}
      />

      {simulationRule ? <SimulationModal rule={simulationRule} onClose={actions.clearSimulation} /> : null}
    </AppShell>
  );
}

type AlertsHeroProps = {
  plan: AlertPlanInfo | null;
  fallbackPlanTier: string;
  totalRules: number;
  onCreateRule: () => void;
  onOpenWizard: () => void;
};

function AlertsHero({ plan, fallbackPlanTier, totalRules, onCreateRule, onOpenWizard }: AlertsHeroProps) {
  const planTierLabel = plan?.planTier?.toUpperCase() ?? fallbackPlanTier ?? "—";
  const remaining = plan?.maxAlerts
    ? `${Math.max(plan.remainingAlerts, 0).toLocaleString("ko-KR")} / ${plan.maxAlerts.toLocaleString("ko-KR")}`
    : "무제한";
  const nextEvaluation = formatDateTime(plan?.nextEvaluationAt, { fallback: "예정 없음" });

  return (
    <section className="rounded-3xl border border-border-light bg-gradient-to-r from-background-cardLight via-white to-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:from-background-cardDark dark:via-background-baseDark dark:to-background-cardDark">
      <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
            Alerts · Watchlist
          </p>
          <h1 className="mt-2 text-2xl font-semibold text-text-primaryLight dark:text-text-primaryDark">
            Evidence-first 워치리스트 알림을 한 화면에서 관리하세요
          </h1>
          <p className="mt-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            룰 생성 · 통계 · 최근 매칭 이벤트를 묶어 워치리스트 기반 알림을 정식 메뉴로 제공합니다. Digest 공유는 AdminOps
            패널에서 계속 사용할 수 있습니다.
          </p>
          <div className="mt-4 flex flex-wrap gap-3 text-sm">
            <MetricPill icon={<ShieldCheck className="h-4 w-4" />} label="플랜" value={planTierLabel} />
            <MetricPill icon={<Sparkles className="h-4 w-4" />} label="남은 룰" value={remaining} />
            <MetricPill icon={<CalendarClock className="h-4 w-4" />} label="다음 평가" value={nextEvaluation} />
          </div>
        </div>
        <div className="flex flex-col gap-3 rounded-2xl border border-border-light bg-background-base p-4 dark:border-border-dark dark:bg-background-baseDark">
          <div className="space-y-3 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">빠른 작업</p>
            <p>Watchlist Rule Wizard 또는 커스텀 룰 빌더로 Slack/이메일 알림을 바로 배포하세요.</p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              type="button"
              onClick={onCreateRule}
              className="flex-1 rounded-full bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary/90"
            >
              <span className="inline-flex items-center justify-center gap-2">
                <Plus className="h-4 w-4" />
                새 알림 룰
              </span>
            </button>
            <button
              type="button"
              onClick={onOpenWizard}
              className="flex-1 rounded-full border border-border-light px-4 py-2 text-sm font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark"
            >
              Watchlist Wizard
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

type EventActivityPanelProps = {
  matches: AlertEventMatch[];
  loading: boolean;
  errorMessage?: string | null;
};

function EventActivityPanel({ matches, loading, errorMessage }: EventActivityPanelProps) {
  return (
    <section className="rounded-2xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <header className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">최근 매칭 이벤트</p>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            워치리스트 룰이 지난 며칠 동안 감지한 매칭 이벤트를 빠르게 훑어볼 수 있어요.
          </p>
        </div>
        <Link
          href="/alerts"
          className="inline-flex items-center gap-2 rounded-full border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark"
        >
          전체 보기
          <ListChecks className="h-4 w-4" aria-hidden />
        </Link>
      </header>
      {errorMessage ? (
        <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100">
          {errorMessage}
        </p>
      ) : null}
      <div className="mt-4">
        <EventMatchList
          matches={matches}
          loading={loading}
          limit={8}
          emptyMessage="최근 24시간 내에 매칭된 이벤트가 아직 없습니다."
        />
      </div>
    </section>
  );
}

type PlanLimitCardProps = {
  plan: AlertPlanInfo | null;
  fallbackPlanTier: string;
};

function PlanLimitCard({ plan, fallbackPlanTier }: PlanLimitCardProps) {
  const channelsLabel = plan?.channels?.length ? plan.channels.join(", ") : "연결된 채널 없음";
  const windowLabel = formatWindowText(plan?.frequencyDefaults?.windowMinutes ?? plan?.defaultWindowMinutes ?? 1440);
  const planTierLabel = plan?.planTier?.toUpperCase() ?? fallbackPlanTier ?? "—";

  if (!plan) {
    return (
      <section className="rounded-2xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
        <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">플랜 제한</p>
        <p className="mt-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          워치리스트 알림 한도 정보를 불러오는 중입니다.
        </p>
        <SkeletonBlock className="mt-4 h-20 rounded-xl" />
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex items-center gap-2 text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
        <ShieldCheck className="h-4 w-4 text-primary" aria-hidden />
        <span>{planTierLabel} 플랜 제한</span>
      </div>
      <p className="mt-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
        남은 룰 {Math.max(plan.remainingAlerts, 0).toLocaleString("ko-KR")}개 / 총 {plan.maxAlerts.toLocaleString("ko-KR")}
        개. Digest 공유는 AdminOpsWatchlistPanel에서 설정하세요.
      </p>
      <ul className="mt-3 space-y-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
        <li>기본 윈도우: {windowLabel}</li>
        <li>지원 채널: {channelsLabel}</li>
        <li>평가 주기: {formatWindowText(plan.frequencyDefaults?.evaluationIntervalMinutes ?? plan.defaultEvaluationIntervalMinutes)}</li>
      </ul>
    </section>
  );
}

type MetricPillProps = {
  icon: ReactNode;
  label: string;
  value: string;
};

function MetricPill({ icon, label, value }: MetricPillProps) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-border-light/70 bg-white px-3 py-1 text-xs font-medium text-text-secondaryLight shadow-sm dark:border-border-dark/70 dark:bg-background-baseDark dark:text-text-secondaryDark">
      {icon}
      <span>
        {label} ·{" "}
        <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{value}</span>
      </span>
    </span>
  );
}

type SimulationModalProps = {
  rule: AlertRule;
  onClose: () => void;
};

function SimulationModal({ rule, onClose }: SimulationModalProps) {
  const [windowMinutes, setWindowMinutes] = useState<number>(
    Math.max(rule.frequency?.windowMinutes ?? SIMULATION_DEFAULT_WINDOW_MINUTES, 60),
  );
  const [limit, setLimit] = useState<number>(SIMULATION_DEFAULT_LIMIT);
  const [result, setResult] = useState<AlertRuleSimulationResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const simulateRule = useSimulateAlertRule();

  const runSimulation = useCallback(
    async (minutes: number, maxItems: number) => {
      setErrorMessage(null);
      try {
        const preview = await simulateRule.mutateAsync({
          id: rule.id,
          payload: { windowMinutes: minutes, limit: maxItems },
        });
        setResult(preview);
      } catch (cause) {
        const message =
          cause instanceof ApiError
            ? cause.message
            : cause instanceof Error
              ? cause.message
              : "시뮬레이션을 실행하지 못했어요.";
        setErrorMessage(message);
        setResult(null);
      }
    },
    [rule.id, simulateRule],
  );

  useEffect(() => {
    const initialWindow = Math.max(rule.frequency?.windowMinutes ?? SIMULATION_DEFAULT_WINDOW_MINUTES, 60);
    setWindowMinutes(initialWindow);
    setLimit(SIMULATION_DEFAULT_LIMIT);
    setResult(null);
    setErrorMessage(null);
    void runSimulation(initialWindow, SIMULATION_DEFAULT_LIMIT);
  }, [rule, runSimulation]);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const safeWindow = Math.max(5, Math.min(windowMinutes, 7 * 24 * 60));
    const safeLimit = Math.max(1, Math.min(limit, 50));
    setWindowMinutes(safeWindow);
    setLimit(safeLimit);
    void runSimulation(safeWindow, safeLimit);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-8">
      <div className="w-full max-w-2xl rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-2xl dark:border-border-dark dark:bg-background-cardDark">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">시뮬레이션</p>
            <h3 className="text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark">{rule.name}</h3>
            <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
              최근 N일 동안 해당 룰이 매칭했을 이벤트를 미리 확인해 노이즈를 조정하세요.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-border-light p-2 text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
            aria-label="시뮬레이션 닫기"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 flex flex-wrap gap-3 text-sm">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-semibold text-text-secondaryLight dark:text-text-secondaryDark">조회 기간(분)</span>
            <input
              type="number"
              min={5}
              max={7 * 24 * 60}
              value={windowMinutes}
              onChange={(event) => setWindowMinutes(Number(event.target.value))}
              className="w-32 rounded-xl border border-border-light bg-background-base px-3 py-2 dark:border-border-dark dark:bg-background-baseDark"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs font-semibold text-text-secondaryLight dark:text-text-secondaryDark">최대 이벤트 수</span>
            <input
              type="number"
              min={1}
              max={50}
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value))}
              className="w-32 rounded-xl border border-border-light bg-background-base px-3 py-2 dark:border-border-dark dark:bg-background-baseDark"
            />
          </label>
          <button
            type="submit"
            className="mt-auto inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary/90"
          >
            <PlayCircle className="h-4 w-4" aria-hidden />
            다시 실행
          </button>
        </form>

        {errorMessage ? (
          <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100">
            {errorMessage}
          </p>
        ) : null}

        {simulateRule.isPending ? (
          <SkeletonBlock className="mt-4 h-32 rounded-2xl" />
        ) : result ? (
          <div className="mt-4 space-y-3">
            <div className="rounded-2xl border border-border-light bg-background-base p-4 text-sm dark:border-border-dark dark:bg-background-baseDark">
              <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                {result.matches ? "매칭 이벤트" : "매칭 없음"} · {result.eventCount}건
              </p>
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                {formatDateTime(result.windowStart, { fallback: "" })} ~ {formatDateTime(result.windowEnd, { fallback: "" })}
              </p>
              <p className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">{result.message}</p>
            </div>
            {result.eventCount > 0 ? (
              <div className="divide-y divide-border-light overflow-hidden rounded-2xl border border-border-light dark:divide-border-dark dark:border-border-dark">
                {result.events.map((event, index) => (
                  <SimulationEventCard key={`${result.ruleId}-${index}`} event={event} eventType={result.eventType} />
                ))}
              </div>
            ) : (
              <EmptyState
                title="표시할 이벤트가 없어요"
                description="필터를 조정하거나 조회 기간을 늘려보세요."
                className="border-none bg-transparent px-0 py-8 text-sm"
              />
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default function AlertsWatchlistPage() {
  const planContext = usePlanContext();
  const planReady = planContext.initialized && !planContext.loading;

  if (!planReady) {
    return (
      <AppShell>
        <div className="space-y-4">
          <SkeletonBlock className="h-32 rounded-3xl" />
        </div>
      </AppShell>
    );
  }

  const hasAccess = isTierAtLeast(planContext.planTier ?? "free", "pro");

  if (!hasAccess) {
    return (
      <AppShell>
        <PlanLock
          requiredTier="pro"
          title="워치리스트 알림은 Pro 이상에서 제공됩니다"
          description="Slack/Email 알림과 Digest 자동화를 실행하려면 플랜을 업그레이드해 주세요."
        />
      </AppShell>
    );
  }

  return <AlertsWatchlistContent fallbackPlanTier={planContext.planTier?.toUpperCase() ?? "—"} />;
}

function SimulationEventCard({
  event,
  eventType,
}: {
  event: Record<string, unknown>;
  eventType: string;
}) {
  const headline =
    (event.headline as string) ??
    (event.report_name as string) ??
    (event.summary as string) ??
    (event.url as string) ??
    "이벤트";
  const company = (event.corp_name as string) ?? (event.company as string) ?? (event.ticker as string) ?? "N/A";
  const timestamp =
    (event.published_at as string) ??
    (event.filed_at as string) ??
    (event.eventTime as string) ??
    (event.created_at as string) ??
    null;
  const relative = timestamp ? formatRelativeTime(timestamp, { fallback: "기록 없음" }) : "기록 없음";
  const absolute = timestamp ? formatDateTime(timestamp, { fallback: "" }) : "";
  const summary =
    (event.summary as string) ??
    (event.message as string) ??
    (event.description as string) ??
    "";

  return (
    <div className="px-4 py-3 text-sm">
      <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{headline}</p>
      <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
        {eventType.toUpperCase()} · {company} · {relative}
      </p>
      {absolute ? (
        <p className="text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">{absolute}</p>
      ) : null}
      {summary ? <p className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark line-clamp-3">{summary}</p> : null}
    </div>
  );
}

const formatWindowText = (minutes?: number | null) => {
  if (!minutes || minutes <= 0) {
    return "—";
  }
  if (minutes % 1440 === 0) {
    const days = minutes / 1440;
    return days === 1 ? "1일" : `${days}일`;
  }
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    return `${hours}시간`;
  }
  return `${minutes}분`;
};
