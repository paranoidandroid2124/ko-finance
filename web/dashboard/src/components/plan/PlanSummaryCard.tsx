"use client";

import clsx from "classnames";
import { useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";

import { usePlanStore } from "@/store/planStore";
import { getTrialCountdownLabel } from "@/lib/trialUtils";
import { usePlanUpgrade } from "@/hooks/usePlanUpgrade";
import { logEvent } from "@/lib/telemetry";
import { recordKpiEvent } from "@/lib/kpi";
import { FEATURE_STARTER_ENABLED } from "@/config/features";
import { getPlanBadgeTone, getPlanLabel } from "@/lib/planTier";
import { usePlanCatalog } from "@/hooks/usePlanCatalog";
import { resolvePlanMarketingCopy } from "@/lib/planContext";
import { usePlanTrialCta } from "@/hooks/usePlanTrialCta";
import { PLAN_ENTITLEMENT_LABELS } from "@/constants/planMetadata";

const friendlyEntitlement = (entitlement: string) => PLAN_ENTITLEMENT_LABELS[entitlement] ?? entitlement;

const friendlyQuotaValue = (value: number | null, unit: string) => {
  if (value === null || value === undefined) {
    return "무제한";
  }
  return `${value.toLocaleString("ko-KR")}${unit}`;
};

const friendlyDate = (iso: string | null | undefined) => {
  if (!iso) {
    return "만료일 정보를 아직 받지 못했어요.";
  }
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return "만료일을 확인 중이에요.";
  }
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(parsed);
};

type PlanSummaryCardProps = {
  className?: string;
};

export function PlanSummaryCard({ className }: PlanSummaryCardProps) {
  const router = useRouter();
  const { planTier, expiresAt, entitlements, quota, loading, initialized, error } = usePlanStore((state) => ({
    planTier: state.planTier,
    expiresAt: state.expiresAt,
    entitlements: state.entitlements,
    quota: state.quota,
    loading: state.loading,
    initialized: state.initialized,
    error: state.error,
  }));
  const { catalog } = usePlanCatalog();
  const { requestUpgrade, isPreparing } = usePlanUpgrade();
  const { trial, trialActive, trialAvailable, trialDurationDays, trialStarting, startTrialCta } = usePlanTrialCta();
  const trialEndsLabel = trialActive ? getTrialCountdownLabel(trial?.endsAt) : null;
  const marketingCopy = useMemo(() => resolvePlanMarketingCopy(planTier, catalog), [planTier, catalog]);

  const handleStartTrial = useCallback(() => {
    startTrialCta({ source: "plan-summary-card" }).catch(() => undefined);
  }, [startTrialCta]);

  const handleStarterUpgrade = useCallback(async () => {
    if (!FEATURE_STARTER_ENABLED) {
      return;
    }
    const redirectPath =
      typeof window !== "undefined" ? `${window.location.pathname}${window.location.search}` : "/settings";
    logEvent("plan.starter_upgrade.cta", { currentPlan: planTier });
    void recordKpiEvent("campaign.starter.settings_cta_click", { currentPlan: planTier }).catch(() => undefined);
    try {
      await requestUpgrade("starter", { redirectPath });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Starter 업그레이드를 준비하지 못했어요.";
      pushToast({
        id: "plan-starter-upgrade-error",
        title: "Starter 업그레이드를 진행하지 못했어요",
        message,
        intent: "error",
      });
    }
  }, [planTier, pushToast, requestUpgrade]);

  const content = useMemo(() => {
    if (!initialized || loading) {
      return (
        <div className="space-y-4">
          <div className="h-5 w-24 animate-pulse rounded bg-border-light/70 dark:bg-border-dark/60" />
          <div className="space-y-2 text-sm">
            <div className="h-4 w-3/4 animate-pulse rounded bg-border-light/60 dark:bg-border-dark/50" />
            <div className="h-4 w-1/2 animate-pulse rounded bg-border-light/60 dark:bg-border-dark/50" />
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={`quota-skeleton-${index}`} className="h-14 animate-pulse rounded-lg bg-border-light/40 dark:bg-border-dark/40" />
            ))}
          </div>
        </div>
      );
    }

    if (error) {
      return (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-4 text-sm text-destructive dark:border-destructive/60 dark:bg-destructive/20">
          플랜 정보를 불러오는 데 잠깐 지연이 있어요. 새로고침 후에도 이어지면 관리자에게 살짝 알려주세요.
        </div>
      );
    }

    const entitlementList = entitlements.length
      ? entitlements.map((item) => friendlyEntitlement(item))
      : ["아직 추가된 권한이 없어요."];

    const quotaItems = [
      {
        label: "하루 채팅 요청",
        value: friendlyQuotaValue(quota.chatRequestsPerDay ?? null, "회"),
      },
      {
        label: "RAG Top-K",
        value: friendlyQuotaValue(quota.ragTopK ?? null, "개"),
      },
      {
        label: "LLM 셀프체크",
        value: quota.selfCheckEnabled ? "켜짐" : "꺼짐",
      },
      {
        label: "동료 비교 내보내기",
        value: friendlyQuotaValue(quota.peerExportRowLimit ?? null, "행"),
      },
    ];

    return (
      <>
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">내 플랜</p>
            <div className="mt-2 flex items-center gap-2 text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">
              <span>{getPlanLabel(planTier, catalog)}</span>
              <span
                className={clsx(
                  "rounded-full px-2 py-0.5 text-[11px] uppercase tracking-wide",
                getPlanBadgeTone(planTier),
                )}
              >
                {planTier}
              </span>
            </div>
            <p className="mt-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">{marketingCopy.tagline}</p>
          </div>
          <div className="rounded-lg bg-border-light/40 px-3 py-2 text-xs text-text-secondaryLight dark:bg-border-dark/40 dark:text-text-secondaryDark">
            만료일&nbsp;
            <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{friendlyDate(expiresAt)}</span>
          </div>
        </header>

        <section className="space-y-3">
          {FEATURE_STARTER_ENABLED && planTier === "free" ? (
            <div className="rounded-lg border border-dashed border-sky-400/60 bg-white/80 p-4 text-sm text-text-secondaryLight shadow-sm dark:border-sky-300/60 dark:bg-white/5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                    Starter 플랜으로 알림 자동화를 바로 시작하세요
                  </p>
                  <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                    워치리스트 50개 · 알림 룰 10개 · 하루 80회 RAG가 포함돼요.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleStarterUpgrade}
                  disabled={isPreparing}
                  className="rounded-lg bg-sky-600 px-4 py-2 text-xs font-semibold text-white shadow transition hover:bg-sky-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isPreparing ? "연결 중..." : "Starter 업그레이드"}
                </button>
              </div>
            </div>
          ) : null}
          {trialActive ? (
            <div className="rounded-lg border border-primary/40 bg-primary/10 p-4 text-sm text-text-primaryLight dark:border-primary.dark/40 dark:bg-primary.dark/15 dark:text-white">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-semibold">Pro 플랜 체험을 이용 중이에요</p>
                  <p className="text-xs text-text-secondaryLight dark:text-white/70">
                    {trialEndsLabel ? `${trialEndsLabel} 후 만료됩니다.` : "종료일 정보가 곧 업데이트됩니다."}
                  </p>
                </div>
                <button
                  type="button"
                  className="rounded-lg border border-white/60 bg-white/10 px-3 py-2 text-xs font-semibold text-white transition hover:bg-white/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/70"
                  onClick={() => router.push("/settings?panel=plan&tier=pro")}
                >
                  플랜 관리
                </button>
              </div>
            </div>
          ) : trialAvailable ? (
            <div className="rounded-lg border border-dashed border-primary/40 bg-primary/5 p-4 text-sm text-text-secondaryLight dark:border-primary.dark/40 dark:bg-primary.dark/10">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                    Pro {trialDurationDays}일 무료 체험이 준비돼 있어요
                  </p>
                  <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                    검색·알림·PDF 열람 등 상위 권한을 결제 없이 바로 체험해볼 수 있어요.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleStartTrial}
                  disabled={trialStarting}
                  className="rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-white shadow transition hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {trialStarting ? "체험 시작 중..." : "무료 체험 시작"}
                </button>
              </div>
            </div>
          ) : null}

          <h3 className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
            포함된 권한
          </h3>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            {entitlementList.map((item) => (
              <span
                key={item}
                className="rounded-full border border-border-light px-2 py-0.5 dark:border-border-dark"
              >
                {item}
              </span>
            ))}
          </div>
        </section>

        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
            주요 한도
          </h3>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {quotaItems.map((item) => (
              <div
                key={item.label}
                className="rounded-lg border border-border-light/70 bg-white/70 px-3 py-3 text-sm text-text-secondaryLight shadow-sm transition dark:border-border-dark/70 dark:bg-white/5 dark:text-text-secondaryDark"
              >
                <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
                  {item.label}
                </p>
                <p className="mt-1 text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">{item.value}</p>
              </div>
            ))}
          </div>
        </section>
      </>
    );
  }, [
    initialized,
    loading,
    error,
    planTier,
    expiresAt,
    entitlements,
    quota,
    trialActive,
    trialAvailable,
    trialDurationDays,
    trialEndsLabel,
    handleStartTrial,
    handleStarterUpgrade,
    isPreparing,
    trialStarting,
    router,
  ]);

  return (
    <section
      className={clsx(
        "space-y-5 rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark",
        className,
      )}
    >
      {content}
    </section>
  );
}
