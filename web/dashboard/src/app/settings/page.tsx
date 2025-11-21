"use client";

import { useEffect, useMemo, useState } from "react";
import { useTheme } from "next-themes";
import Link from "next/link";

import { PlanSummaryCard } from "@/components/plan/PlanSummaryCard";
import { PlanAlertOverview } from "@/components/plan/PlanAlertOverview";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { useAlertRules } from "@/hooks/useAlerts";
import { UserLightMemSettingsCard } from "@/components/settings/UserLightMemSettingsCard";
import { LegalDataCard } from "@/components/settings/LegalDataCard";
import { SettingsSectionNav } from "@/components/settings/SettingsSectionNav";
import { useAuth } from "@/lib/authContext";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
   const { session, loading: authLoading } = useAuth();

  const {
    data: alertRulesData,
    isLoading: isAlertPlanLoading,
    isError: isAlertPlanError,
  } = useAlertRules();

  useEffect(() => setMounted(true), []);

  const isDark = mounted ? theme === "dark" : false;
  const alertPlan = alertRulesData?.plan ?? null;
  const alertPlanErrorMessage = isAlertPlanError ? "알림 플랜 정보를 불러오는 중 작은 hiccup이 있었어요." : undefined;
  const userEmail = useMemo(() => session?.user?.email ?? null, [session?.user?.email]);
  const userId = useMemo(() => session?.user?.id ?? session?.user?.aud ?? null, [session?.user?.aud, session?.user?.id]);

  const handleThemeToggle = () => {
    setTheme(isDark ? "light" : "dark");
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <SettingsSectionNav />

        <section className="rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
          <header className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-text-tertiaryLight dark:text-text-tertiaryDark">
                Account & Workspace
              </p>
              <h1 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">
                프로필 · 워크스페이스 정보
              </h1>
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                로그인 상태를 확인하고, 알림·플랜 설정 전에 계정을 점검하세요.
              </p>
            </div>
            {userEmail ? (
              <div className="rounded-lg border border-border-light bg-white/60 px-4 py-3 text-sm text-text-primaryLight shadow-sm dark:border-border-dark dark:bg-background-base dark:text-text-primaryDark">
                <div className="font-semibold">{userEmail}</div>
                {userId ? <div className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">User ID: {userId}</div> : null}
              </div>
            ) : (
              <Link
                href="/auth/login"
                className="inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow hover:bg-primary/90"
              >
                로그인하고 설정 계속하기
              </Link>
            )}
          </header>
          {authLoading ? (
            <p className="mt-3 text-xs text-text-secondaryLight dark:text-text-secondaryDark">로그인 상태를 확인하는 중입니다…</p>
          ) : null}
        </section>

        <PlanSummaryCard />

        <PlanAlertOverview plan={alertPlan} loading={isAlertPlanLoading} error={alertPlanErrorMessage} />

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

        <LegalDataCard />
      </div>
    </AppShell>
  );
}
