"use client";

import { useMemo } from "react";
import { ArrowUpRight, BadgeCheck, Building2, Sparkles, TrendingUp } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { ErrorState } from "@/components/ui/ErrorState";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { usePlanCatalog } from "@/hooks/usePlanCatalog";
import type { PlanCatalogTier } from "@/lib/planCatalogApi";
import { FEATURE_STARTER_ENABLED } from "@/config/features";
import { resolvePlanMarketingCopy } from "@/lib/planContext";
import type { PlanTier } from "@/store/planStore/types";
import type { PlanTierCopy } from "@/config/planConfig";
import { PlanTierCTA } from "@/components/plan/PlanTierCTA";
import { usePlanContext } from "@/store/planStore";

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  free: Sparkles,
  starter: Sparkles,
  pro: TrendingUp,
  enterprise: Building2,
};

const formatCurrency = (amount: number, currency: string): string => {
  const simpleCurrency = currency.toUpperCase();
  if (amount === 0) {
    return "무료";
  }
  try {
    return new Intl.NumberFormat("ko-KR", {
      style: "currency",
      currency: simpleCurrency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${amount.toLocaleString()} ${simpleCurrency}`;
  }
};

type PlanCardProps = {
  tier: PlanCatalogTier;
  isFeatured?: boolean;
  copy: PlanTierCopy;
  isCurrent?: boolean;
};

const PlanCard = ({ tier, isFeatured, copy, isCurrent = false }: PlanCardProps) => {
  const Icon = ICON_MAP[tier.tier] ?? Sparkles;
  const priceText = formatCurrency(tier.price.amount, tier.price.currency);
  const priceNote = tier.price.note;
  const description = copy.description ?? tier.description ?? null;
  const featureEntries: Array<{ text: string; highlight?: boolean | null }> =
    tier.features?.length && tier.features.every((feature) => typeof feature?.text === "string")
      ? (tier.features as Array<{ text: string; highlight?: boolean | null }>)
      : copy.features.map((text) => ({ text }));

  return (
    <div
      className={`flex h-full flex-col rounded-3xl border border-border-subtle bg-surface-light/80 p-6 shadow-sm transition duration-300 dark:border-border-subtleDark dark:bg-surface-dark/70 ${
        isFeatured
          ? "border-accent-primary shadow-lg dark:border-accent-primary"
          : "hover:border-accent-primary/40 hover:shadow-md"
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-2 text-sm font-semibold text-accent-primary">
          <Icon className="h-5 w-5" />
          {tier.badge ?? tier.tier.toUpperCase()}
        </span>
        <div className="flex items-center gap-2">
          {isCurrent ? (
            <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary dark:bg-primary.dark/20 dark:text-primary.dark">
              현재 이용 중
            </span>
          ) : null}
          {isFeatured && (
            <span className="inline-flex items-center gap-1 rounded-full bg-accent-primary px-3 py-1 text-xs font-semibold text-white">
              <BadgeCheck className="h-3.5 w-3.5" />
              추천 플랜
            </span>
          )}
        </div>
      </div>

      <div className="mt-5">
        <h2 className="text-2xl font-semibold text-text-primaryLight dark:text-text-primaryDark">{tier.title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-text-secondaryLight dark:text-text-secondaryDark">
          {tier.tagline}
        </p>
        {description ? (
          <p className="mt-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">{description}</p>
        ) : null}
      </div>

      <div className="mt-6 flex items-baseline gap-2">
        <span className="text-4xl font-bold text-text-primaryLight dark:text-text-primaryDark">{priceText}</span>
        {tier.price.amount !== 0 && (
          <span className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">/ {tier.price.interval}</span>
        )}
      </div>
      {priceNote && (
        <p className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">{priceNote}</p>
      )}

      <ul className="mt-6 space-y-3 text-sm leading-relaxed text-text-secondaryLight dark:text-text-secondaryDark">
        {featureEntries.map((feature) => (
          <li
            key={feature.text}
            className={`flex items-start gap-2 rounded-lg border border-transparent px-2 py-1 ${
              feature.highlight ? "bg-accent-primary/10 text-accent-primary" : ""
            }`}
          >
            <ArrowUpRight className={`mt-1 h-4 w-4 ${feature.highlight ? "text-accent-primary" : "text-border-subtle"}`} />
            <span>{feature.text}</span>
          </li>
        ))}
      </ul>

      <div className="mt-6 flex flex-col gap-2">
        <PlanTierCTA
          tier={tier.tier}
          action={copy.primaryAction}
          variant={isFeatured ? "primary" : "secondary"}
          fullWidth
        />
        {copy.secondaryAction ? (
          <PlanTierCTA tier={tier.tier} action={copy.secondaryAction} variant="secondary" fullWidth />
        ) : null}
        {(copy.supportNote ?? tier.supportNote) && (
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            {copy.supportNote ?? tier.supportNote}
          </p>
        )}
      </div>
    </div>
  );
};

export default function PricingPage() {
  const { catalog, loading, error, refetch } = usePlanCatalog();
  const planContext = usePlanContext();

  const tiers: PlanCatalogTier[] = useMemo(() => {
    const all = catalog?.tiers ?? [];
    if (FEATURE_STARTER_ENABLED) {
      return all;
    }
    return all.filter((tier) => tier.tier !== "starter");
  }, [catalog]);

  const tierCopyMap = useMemo(() => {
    const map: Partial<Record<PlanTier, PlanTierCopy>> = {};
    (["free", "starter", "pro", "enterprise"] as PlanTier[]).forEach((tier) => {
      map[tier] = resolvePlanMarketingCopy(tier, catalog);
    });
    return map;
  }, [catalog]);

  const currentPlanTier = planContext.planTier ?? "free";
  const planInitialized = planContext.initialized && !planContext.loading;

  return (
    <AppShell>
      <section className="space-y-4">
        <h1 className="text-3xl font-semibold text-text-primaryLight dark:text-text-primaryDark">플랜 & 가격 안내</h1>
        <p className="max-w-3xl text-sm leading-relaxed text-text-secondaryLight dark:text-text-secondaryDark">
          팀의 성장 단계에 맞춰 사용할 수 있는 3가지 플랜을 준비했어요. 따뜻한 금융 데이터를 기반으로 한 RAG 분석,
          알림, 워크플로 자동화를 손쉽게 도입해 보세요.
        </p>
      </section>

      {loading && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <SkeletonBlock key={index} className="h-96 rounded-3xl" />
          ))}
        </div>
      )}

      {!loading && error && (
        <ErrorState
          title="플랜 정보를 불러오지 못했어요."
          description="네트워크 상태를 확인한 뒤 다시 시도해 주세요."
          action={
            <button
              onClick={() => refetch()}
              className="rounded-full border border-accent-primary px-4 py-2 text-sm font-semibold text-accent-primary hover:bg-accent-primary/10"
            >
              다시 시도하기
            </button>
          }
        />
      )}

      {!loading && !error && (
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {tiers.map((tier) => (
            <PlanCard
              key={tier.tier}
              tier={tier}
              isFeatured={tier.tier === "pro"}
              copy={tierCopyMap[tier.tier]!}
              isCurrent={planInitialized && tier.tier === currentPlanTier}
            />
          ))}
        </section>
      )}
    </AppShell>
  );
}
