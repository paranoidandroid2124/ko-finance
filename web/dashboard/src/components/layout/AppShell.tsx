"use client";

import Link from "next/link";
import { Suspense, useEffect } from "react";
import { CircleUserRound, Settings } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import type { Route } from "next";

import { PlanProvider } from "../plan/PlanProvider";
import { ToastContainer } from "../ui/ToastContainer";
import { OnboardingModal } from "../onboarding/OnboardingModal";
import { useOnboardingStore } from "@/store/onboardingStore";
import { ToolOverlay } from "../tools/ToolOverlay";
import { AppFooter } from "./AppFooter";
import { useAuth } from "@/lib/authContext";
import { useSettingsModalStore } from "@/store/settingsModalStore";
import { SettingsModal } from "@/components/settings/SettingsModal";

type AppShellProps = {
  children: React.ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const { loading, user } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const setNeedsOnboarding = useOnboardingStore((state) => state.setNeedsOnboarding);
  const openSettings = useSettingsModalStore((state) => state.openModal);
  const displayName =
    user?.email ??
    (typeof user?.user_metadata?.full_name === "string" ? user.user_metadata.full_name : undefined) ??
    "Guest";

  useEffect(() => {
    if (loading) {
      return;
    }
    const onboardingRequired = Boolean(user?.onboardingRequired);
    setNeedsOnboarding(onboardingRequired);
    if (!onboardingRequired) {
      return;
    }
    const currentPath = pathname ?? "";
    if (currentPath.startsWith("/onboarding") || currentPath.startsWith("/auth")) {
      return;
    }
    router.replace("/onboarding" as Route);
  }, [loading, pathname, router, setNeedsOnboarding, user]);

  return (
    <PlanProvider>
      <div className="relative min-h-screen w-full overflow-hidden bg-[#0D1117] text-white font-['Geist','Inter',sans-serif]">
        <div className="pointer-events-none absolute inset-0 opacity-80">
          <div className="absolute -left-28 -top-48 h-[26rem] w-[26rem] rounded-full bg-[#58A6FF]/12 blur-[180px]" />
          <div className="absolute -right-32 bottom-[-200px] h-[30rem] w-[30rem] rounded-full bg-[#58A6FF]/10 blur-[200px]" />
        </div>
        <div className="pointer-events-none absolute inset-0 z-30 flex items-end justify-start pb-6 pl-6">
          <div className="pointer-events-auto flex items-center gap-2 rounded-full border border-[#30363D] bg-[#0f1624]/90 px-3 py-2 text-xs font-semibold text-slate-200 shadow-[0_12px_40px_rgba(0,0,0,0.45)] backdrop-blur-xl">
            <Link href="/dashboard" className="flex items-center gap-2 rounded-full px-2 py-1 hover:text-white transition">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl border border-[#30363D] bg-[#161B22] text-sm font-semibold text-white shadow-[0_8px_24px_rgba(0,0,0,0.35)]">
                N
              </div>
              <span className="hidden text-[11px] uppercase tracking-[0.3em] text-slate-400 sm:inline">Dashboard</span>
            </Link>
            <Link
              href="#"
              onClick={(event) => {
                event.preventDefault();
                openSettings();
              }}
              className="inline-flex items-center gap-1.5 rounded-full border border-[#30363D] bg-[#161B22] px-3 py-1 text-[12px] font-semibold text-slate-200 shadow-[0_8px_24px_rgba(0,0,0,0.35)] transition hover:border-[#58A6FF]/70 hover:text-white"
            >
              <Settings className="h-4 w-4 text-[#58A6FF]" />
              설정
            </Link>
            <div className="flex items-center gap-2 rounded-full border border-[#30363D] bg-[#161B22] px-2.5 py-1 text-[12px] font-semibold text-slate-200 shadow-[0_8px_24px_rgba(0,0,0,0.35)]">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#58A6FF]/15 text-[#58A6FF]">
                <CircleUserRound className="h-4 w-4" aria-hidden />
              </span>
              <span className="max-w-[140px] truncate">{loading ? "불러오는 중..." : displayName}</span>
            </div>
          </div>
        </div>
        <div className="relative z-10 flex min-h-screen flex-col px-5 pb-6 pt-2 md:px-8">
          <ToastContainer />
          <ToolOverlay />
          <Suspense fallback={null}>
            <OnboardingModal />
          </Suspense>
          <SettingsModal />
          <main className="flex flex-1 min-h-0 flex-col gap-4">
            <div className="flex-1 min-h-0">{children}</div>
            <AppFooter />
          </main>
        </div>
      </div>
    </PlanProvider>
  );
}
