"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useState } from "react";
import { CircleUserRound, LogOut, Settings, Sparkles } from "lucide-react";
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
import supabase from "@/lib/supabase";
import { toast } from "@/store/toastStore";

type AppShellProps = {
  children: React.ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const { loading, user } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);
  const setNeedsOnboarding = useOnboardingStore((state) => state.setNeedsOnboarding);
  const openSettings = useSettingsModalStore((state) => state.openModal);
  const displayName =
    user?.email ??
    (typeof user?.user_metadata?.full_name === "string" ? user.user_metadata.full_name : undefined) ??
    "Guest";

  const handleLogout = useCallback(async () => {
    if (loggingOut) return;
    setLoggingOut(true);
    const { error } = await supabase.auth.signOut();
    if (error) {
      console.error("[Supabase] Logout failed", error);
      toast.show({ intent: "error", message: "로그아웃에 실패했습니다. 잠시 후 다시 시도해 주세요." });
      setLoggingOut(false);
      return;
    }
    router.replace("/auth/login" as Route);
  }, [loggingOut, router]);

  useEffect(() => {
    if (loading) {
      return;
    }
    const onboardingRequired =
      typeof user === "object" &&
        user !== null &&
        "onboardingRequired" in user &&
        typeof (user as { onboardingRequired?: unknown }).onboardingRequired === "boolean"
        ? Boolean((user as { onboardingRequired?: boolean }).onboardingRequired)
        : false;
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
      <div className="relative min-h-screen w-full overflow-hidden text-text-primary font-['Geist','Inter',sans-serif]">
        <div className="pointer-events-none absolute inset-0 z-30 flex items-end justify-start pb-6 pl-6">
          <div className="pointer-events-auto flex items-center gap-2 rounded-full border border-border-hair/70 bg-surface-2/85 px-3 py-2 text-xs font-semibold text-text-secondary shadow-elevation-1 backdrop-blur-glass">
            <Link href="/dashboard" className="flex items-center gap-2 rounded-full px-2 py-1 transition hover:text-text-primary">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl border border-border-hair/70 bg-surface-1/90 text-sm font-semibold text-text-primary shadow-subtle">
                N
              </div>
              <span className="hidden text-[11px] uppercase tracking-[0.3em] text-text-secondary sm:inline">Dashboard</span>
            </Link>
            <Link
              href="/insights"
              className="inline-flex items-center gap-1.5 rounded-full border border-border-hair/70 bg-surface-1/90 px-3 py-1 text-[12px] font-semibold text-text-secondary shadow-subtle transition hover:border-primary/60 hover:text-text-primary"
            >
              <Sparkles className="h-4 w-4 text-accent-emerald" />
              Insights
            </Link>
            <Link
              href="#"
              onClick={(event) => {
                event.preventDefault();
                openSettings();
              }}
              className="inline-flex items-center gap-1.5 rounded-full border border-border-hair/70 bg-surface-1/90 px-3 py-1 text-[12px] font-semibold text-text-secondary shadow-subtle transition hover:border-primary/60 hover:text-text-primary"
            >
              <Settings className="h-4 w-4 text-primary" />
              설정
            </Link>
            <button
              type="button"
              onClick={handleLogout}
              disabled={loggingOut}
              className="inline-flex items-center gap-1.5 rounded-full border border-border-hair/70 bg-surface-1/90 px-3 py-1 text-[12px] font-semibold text-text-secondary shadow-subtle transition hover:border-accent-rose/70 hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-60"
            >
              <LogOut className="h-4 w-4 text-accent-rose" />
              {loggingOut ? "로그아웃 중" : "로그아웃"}
            </button>
            <div className="flex items-center gap-2 rounded-full border border-border-hair/70 bg-surface-1/90 px-2.5 py-1 text-[12px] font-semibold text-text-secondary shadow-subtle">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/15 text-primary">
                <CircleUserRound className="h-4 w-4" aria-hidden />
              </span>
              <span className="max-w-[140px] truncate">{loading ? "불러오는 중..." : displayName}</span>
            </div>
          </div>
        </div>
        <div className="relative z-10 flex min-h-screen flex-col px-4 pb-6 pt-2 md:px-6 lg:px-8">
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
