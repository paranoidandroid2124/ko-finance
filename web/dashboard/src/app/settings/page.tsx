"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTheme } from "next-themes";
import { useSearchParams } from "next/navigation";
import clsx from "classnames";

import { PlanSummaryCard } from "@/components/plan/PlanSummaryCard";
import { PlanAlertOverview } from "@/components/plan/PlanAlertOverview";
import { PlanTierPreview } from "@/components/plan/PlanTierPreview";
import { PlanSettingsForm } from "@/components/plan/PlanSettingsForm";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { useAlertRules } from "@/hooks/useAlerts";
import { usePlanStore, type PlanTier } from "@/store/planStore";
import { UserLightMemSettingsCard } from "@/components/settings/UserLightMemSettingsCard";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const searchParams = useSearchParams();
  const planPanelRef = useRef<HTMLDivElement>(null);
  const [planHighlighted, setPlanHighlighted] = useState(false);

  const { error: planError } = usePlanStore((state) => ({
    error: state.error,
  }));

  const {
    data: alertRulesData,
    isLoading: isAlertPlanLoading,
    isError: isAlertPlanError,
  } = useAlertRules();

  useEffect(() => setMounted(true), []);

  const focusTier = useMemo<PlanTier | null>(() => {
    const value = searchParams.get("tier");
    if (value === "free" || value === "pro" || value === "enterprise") {
      return value;
    }
    return null;
  }, [searchParams]);

  useEffect(() => {
    const panel = searchParams.get("panel");
    if (panel !== "plan" && !focusTier) {
      return;
    }
    const target = planPanelRef.current;
    if (!target) {
      return;
    }
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    setPlanHighlighted(true);
    const timer = setTimeout(() => setPlanHighlighted(false), 2200);
    return () => clearTimeout(timer);
  }, [focusTier, searchParams]);

  const isDark = mounted ? theme === "dark" : false;
  const alertPlan = alertRulesData?.plan ?? null;
  const alertPlanErrorMessage = isAlertPlanError ? "알림 플랜 정보를 불러오는 중 작은 hiccup이 있었어요." : undefined;
  const planStoreErrorMessage = planError ? `플랜 컨텍스트 로딩이 살짝 미끄러졌어요. (${planError})` : undefined;

  const handleThemeToggle = () => {
    setTheme(isDark ? "light" : "dark");
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <PlanSummaryCard />

        <PlanAlertOverview
          plan={alertPlan}
          loading={isAlertPlanLoading}
          error={alertPlanErrorMessage ?? planStoreErrorMessage}
        />

        <div
          ref={planPanelRef}
          className={clsx(
            "space-y-4 rounded-xl border border-transparent p-1 transition-all duration-500",
            planHighlighted && "border-primary/60 bg-primary/5 shadow-lg dark:bg-primary.dark/10",
          )}
        >
          <PlanTierPreview focusTier={focusTier} />
          <PlanSettingsForm />
        </div>
        <UserLightMemSettingsCard />

        <section className="rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
          <header className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">화면 분위기</h2>
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                지금 기분에 맞게 라이트/다크 테마를 골라주세요. 언제든 다시 바꿀 수 있어요.
              </p>
            </div>
            <button
              type="button"
              onClick={handleThemeToggle}
              className="rounded-md border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
            >
              {isDark ? "라이트 테마로 살짝 밝히기" : "다크 테마로 눈을 쉬게 하기"}
            </button>
          </header>
        </section>

        <section className="rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
          <h2 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">다가오는 연동</h2>
          <EmptyState
            title="Settings & Admin 연동이 곧 준비됩니다"
            description="Plan 기본값을 직접 수정하고, Admin 콘솔에서 큐 모니터링·재처리 도구를 다룰 수 있도록 API 연결을 마무리하는 중이에요. 곧 더 많은 버튼이 이곳에 등장할 거예요!"
            className="border-none bg-transparent px-0 py-6 text-xs text-text-secondaryLight dark:text-text-secondaryDark"
          />
        </section>
      </div>
    </AppShell>
  );
}
