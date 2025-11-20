"use client";

import { useEffect } from "react";
import { useSession } from "next-auth/react";
import { usePathname, useRouter } from "next/navigation";
import type { Route } from "next";

import { PlanProvider } from "../plan/PlanProvider";
import { ToastContainer } from "../ui/ToastContainer";
import { StarterPromoBanner } from "../plan/StarterPromoBanner";
import { FEATURE_STARTER_ENABLED } from "@/config/features";
import { OnboardingModal } from "../onboarding/OnboardingModal";
import { useOnboardingStore } from "@/store/onboardingStore";
import { ToolOverlay } from "../tools/ToolOverlay";

type AppShellProps = {
  children: React.ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const { data: session, status } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const setNeedsOnboarding = useOnboardingStore((state) => state.setNeedsOnboarding);

  useEffect(() => {
    if (status === "loading") {
      return;
    }
    const onboardingRequired =
      status === "authenticated" && Boolean(session?.onboardingRequired ?? session?.user?.onboardingRequired);
    setNeedsOnboarding(onboardingRequired);
    if (!onboardingRequired) {
      return;
    }
    const currentPath = pathname ?? "";
    if (currentPath.startsWith("/onboarding") || currentPath.startsWith("/auth")) {
      return;
    }
    router.replace("/onboarding" as Route);
  }, [pathname, router, session, setNeedsOnboarding, status]);

  return (
    <PlanProvider>
      <div className="relative min-h-screen w-full overflow-hidden bg-[#050a1c] text-white font-['Geist','Inter',sans-serif]">
        <div className="pointer-events-none absolute inset-0 opacity-80">
          <div className="absolute -left-20 -top-40 h-96 w-96 rounded-full bg-blue-600/25 blur-[160px]" />
          <div className="absolute -right-32 bottom-[-180px] h-[28rem] w-[28rem] rounded-full bg-cyan-500/20 blur-[180px]" />
        </div>
        <div className="relative z-10 flex min-h-screen flex-col px-5 pb-8 pt-6 md:px-8">
          <ToastContainer />
          <ToolOverlay />
          <OnboardingModal />
          <main className="flex flex-1 min-h-0 flex-col gap-6">
            {FEATURE_STARTER_ENABLED ? <StarterPromoBanner /> : null}
            <div className="flex-1 min-h-0">{children}</div>
          </main>
        </div>
      </div>
    </PlanProvider>
  );
}
