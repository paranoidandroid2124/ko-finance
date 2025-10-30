"use client";

import clsx from "classnames";
import { Crown, Lock, Sparkles } from "lucide-react";
import { useEffect, useMemo, type ComponentType } from "react";
import { logEvent } from "@/lib/telemetry";
import { isTierAtLeast, nextTier, planTierRank, type PlanTier, usePlanTier } from "@/store/planStore";

type PlanLockProps = {
  requiredTier: PlanTier;
  currentTier?: PlanTier;
  title?: string;
  description?: string;
  onUpgrade?: (tier: PlanTier) => void;
  className?: string;
  children?: React.ReactNode;
  showBadge?: boolean;
};

const PLAN_LABEL: Record<PlanTier, string> = {
  free: "Free",
  pro: "Pro",
  enterprise: "Enterprise",
};

const PLAN_TONE: Record<PlanTier, string> = {
  free: "bg-slate-100 text-slate-600 dark:bg-white/10 dark:text-slate-200",
  pro: "bg-primary/10 text-primary dark:bg-primary/20",
  enterprise: "bg-emerald-500/10 text-emerald-600 dark:bg-emerald-400/10 dark:text-emerald-200",
};

const PLAN_ICON: Record<PlanTier, ComponentType<{ className?: string }>> = {
  free: Sparkles,
  pro: Lock,
  enterprise: Crown,
};

const PLAN_ICON_TONE: Record<PlanTier, string> = {
  free: "text-slate-500 dark:text-slate-300",
  pro: "text-primary",
  enterprise: "text-emerald-500 dark:text-emerald-300",
};

export function PlanLock({
  requiredTier,
  currentTier,
  title,
  description,
  onUpgrade,
  className,
  children,
  showBadge = true,
}: PlanLockProps) {
  const tierFromStore = usePlanTier();
  const tier = currentTier ?? tierFromStore;
  const isUnlocked = isTierAtLeast(tier, requiredTier);

  const Icon = PLAN_ICON[requiredTier] ?? Lock;
  const iconTone = PLAN_ICON_TONE[requiredTier] ?? PLAN_ICON_TONE.pro;

  const heading = title ?? `${PLAN_LABEL[requiredTier]} 플랜에서 열리는 기능이에요.`;
  const detail =
    description ??
    (requiredTier === "pro"
      ? "조금 더 풍성한 자동화를 돕고 싶어요. Pro 플랜으로 업그레이드하면 이메일·웹훅 채널과 고급 하이라이트를 바로 누릴 수 있어요."
      : "전용 파트너 플랜에서만 제공되는 기능이에요. 다음 단계에서 토스페이먼츠로 간편 결제하고 바로 사용을 시작할 수 있어요.");

  const next = useMemo(() => nextTier(tier), [tier]);

  useEffect(() => {
    if (!isUnlocked) {
      logEvent("plan.lock.view", { requiredTier, currentTier: tier });
    }
  }, [isUnlocked, requiredTier, tier]);

  if (isUnlocked) {
    return children ? <>{children}</> : null;
  }

  return (
    <div
      className={clsx(
        "motion-shimmer animate-motion-shimmer animate-pulse rounded-xl border border-dashed border-border-light/80 bg-background-cardLight/70 p-4 text-sm text-text-secondaryLight shadow-card dark:border-border-dark/80 dark:bg-background-cardDark/40 dark:text-text-secondaryDark",
        className,
      )}
      data-testid="plan-lock"
    >
      <div className="flex items-center gap-2 text-text-primaryLight dark:text-text-primaryDark">
        <Icon aria-hidden className={clsx("h-5 w-5", iconTone)} />
        <p className="font-semibold">{heading}</p>
        {showBadge ? (
          <span className={clsx("rounded-full px-2 py-0.5 text-[11px] uppercase", PLAN_TONE[requiredTier])}>
            {PLAN_LABEL[requiredTier]}
          </span>
        ) : null}
      </div>
      <p className="mt-2 text-xs leading-5">{detail}</p>
      {onUpgrade ? (
        <button
          type="button"
          className="mt-3 inline-flex items-center gap-2 rounded-lg border border-primary bg-primary px-3 py-2 text-xs font-semibold text-white transition-motion-fast hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          onClick={() => {
            logEvent("plan.lock.upgrade_click", { requiredTier, currentTier: tier, nextTier: next });
            onUpgrade(requiredTier);
          }}
        >
          {next === "enterprise" ? "전용 플랜 결제하기" : "플랜 업그레이드 안내 받기"}
        </button>
      ) : null}
      {children ? <div className="mt-3">{children}</div> : null}
      <p className="mt-3 text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
        지금은{" "}
        <strong className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">{PLAN_LABEL[tier]}</strong> 플랜을 이용 중이에요.{" "}
        <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{PLAN_LABEL[requiredTier]}</span>로 한 단계 올라가면 바라던 기능을 바로 사용하실 수 있어요.
      </p>
    </div>
  );
}
