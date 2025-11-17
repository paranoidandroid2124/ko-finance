"use client";

import Link from "next/link";
import { CreditCard } from "lucide-react";

import { PlanSummaryCard } from "@/components/plan/PlanSummaryCard";
import { usePlanStore } from "@/store/planStore";
import { planTierLabel } from "@/constants/planPricing";

type AdminBillingPanelProps = {
  compact?: boolean;
};

export function AdminBillingPanel({ compact = false }: AdminBillingPanelProps) {
  const planTier = usePlanStore((state) => state.planTier);
  const expiresAt = usePlanStore((state) => state.expiresAt);
  const entitlements = usePlanStore((state) => state.entitlements);
  const checkoutRequested = usePlanStore((state) => state.checkoutRequested);

  const renewalLabel = expiresAt ? new Date(expiresAt).toLocaleDateString("ko-KR") : "제한 없음";
  const statusLabel = checkoutRequested ? "결제 진행 중" : "정상";
  const headlineFeatures = entitlements.slice(0, 3);

  return (
    <div className="rounded-xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
            Billing &amp; Plan
          </p>
          <h3 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">
            {planTierLabel(planTier)}
          </h3>
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            만료일: {renewalLabel} · 상태: {statusLabel}
          </p>
        </div>
        <CreditCard className="h-8 w-8 text-primary" aria-hidden />
      </div>
      {!compact ? (
        <div className="mt-4">
          <PlanSummaryCard />
        </div>
      ) : null}
      <div className="mt-4 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
        <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">주요 포함 기능</p>
        <ul className="mt-1 list-disc space-y-0.5 pl-4">
          {headlineFeatures.map((entitlement) => (
            <li key={entitlement}>{entitlement}</li>
          ))}
          {headlineFeatures.length === 0 ? <li>설정된 권한 정보가 없습니다.</li> : null}
        </ul>
      </div>
      <div className="mt-4 flex flex-wrap gap-2 text-sm">
        <Link
          href="/pricing"
          className="inline-flex items-center rounded-lg border border-border-light px-3 py-1.5 font-semibold text-text-primaryLight transition hover:bg-border-light/40 dark:border-border-dark dark:text-text-primaryDark"
        >
          가격표 보기
        </Link>
        <Link
          href="/onboarding"
          className="inline-flex items-center rounded-lg border border-border-light px-3 py-1.5 font-semibold text-text-primaryLight transition hover:bg-border-light/40 dark:border-border-dark dark:text-text-primaryDark"
        >
          플랜 변경
        </Link>
      </div>
    </div>
  );
}
