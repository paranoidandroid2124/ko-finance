"use client";

import { useEffect, useState } from "react";
import { X, HelpCircle } from "lucide-react";
import { useTheme } from "next-themes";
import Link from "next/link";

import { PlanSummaryCard } from "@/components/plan/PlanSummaryCard";
import { PlanAlertOverview } from "@/components/plan/PlanAlertOverview";
import { UserLightMemSettingsCard } from "@/components/settings/UserLightMemSettingsCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { useAlertRules } from "@/hooks/useAlerts";

type SettingsOverlayProps = {
  onClose: () => void;
};

export function SettingsOverlay({ onClose }: SettingsOverlayProps) {
  const { data: alertRulesData, isLoading: isAlertPlanLoading, isError: isAlertPlanError } = useAlertRules();
  const alertPlan = alertRulesData?.plan ?? null;
  const alertPlanErrorMessage = isAlertPlanError ? "알림 플랜 정보를 불러오지 못했어요." : undefined;

  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, []);

  const [isClosing, setIsClosing] = useState(false);
  const handleClose = () => {
    setIsClosing(true);
    setTimeout(onClose, 120);
  };

  const isDark = mounted ? theme === "dark" : false;

  const handleThemeToggle = () => {
    setTheme(isDark ? "light" : "dark");
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 px-4 py-8">
      <div
        className={`relative flex w-full max-w-4xl flex-col overflow-hidden rounded-3xl border border-border-light bg-background-cardLight shadow-2xl transition-all dark:border-border-dark dark:bg-background-cardDark ${
          isClosing ? "scale-95 opacity-0" : "scale-100 opacity-100"
        }`}
      >
        <header className="flex items-center justify-between border-b border-border-light px-6 py-4 dark:border-border-dark">
          <div>
            <p className="text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">설정</p>
            <p className="text-sm font-medium text-text-primaryLight dark:text-text-primaryDark">
              플랜 정보와 개인화 옵션을 한 곳에서 관리하세요.
            </p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="rounded-full border border-border-light p-2 text-text-secondaryLight transition hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
          >
            <X className="h-5 w-5" aria-hidden />
            <span className="sr-only">설정 닫기</span>
          </button>
        </header>

        <div className="max-h-[75vh] overflow-y-auto px-6 py-6">
          <div className="space-y-5">
            <PlanSummaryCard />
            <PlanAlertOverview plan={alertPlan} loading={isAlertPlanLoading} error={alertPlanErrorMessage} />
            <UserLightMemSettingsCard />

            <section className="rounded-xl border border-border-light bg-background-base p-5 shadow-sm dark:border-border-dark dark:bg-background-baseDark">
              <header className="flex items-center justify-between gap-4">
                <div>
                  <h3 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">화면 모드</h3>
                  <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                    라이트·다크 테마를 전환해 눈을 편하게 해보세요.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleThemeToggle}
                  className="rounded-md border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
                >
                  {isDark ? "라이트 테마로 전환" : "다크 테마로 전환"}
                </button>
              </header>
            </section>

            <section className="rounded-xl border border-border-light bg-background-base p-5 shadow-sm dark:border-border-dark dark:bg-background-baseDark">
              <div className="flex items-start gap-3">
                <div className="rounded-full bg-primary/10 p-2 text-primary dark:bg-primary.dark/20">
                  <HelpCircle className="h-5 w-5" aria-hidden />
                </div>
                <div className="flex-1">
                  <h3 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                    도움말 센터
                  </h3>
                  <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                    연동 가이드와 운영 체크리스트는 도움말 문서를 통해 빠르게 찾아볼 수 있어요.
                  </p>
                </div>
                <Link
                  href="https://docs.kfinance.co/help"
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-md border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
                >
                  문서 열기
                </Link>
              </div>
            </section>

            <section className="rounded-xl border border-dashed border-border-light bg-background-base p-5 text-xs text-text-secondaryLight dark:border-border-dark dark:bg-background-baseDark dark:text-text-secondaryDark">
              <EmptyState
                title="추가 설정 연동 준비 중"
                description="플랜 기본값, Admin 콘솔 연계 등 더 많은 조정 도구가 여기로 통합될 예정입니다. 피드백이 있다면 Slack에서 알려주세요."
                className="border-none bg-transparent px-0 py-0"
              />
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
