"use client";

import { useEffect } from "react";
import { useSession } from "next-auth/react";
import { usePathname, useRouter } from "next/navigation";

import { PlanProvider } from "../plan/PlanProvider";
import { SideNav } from "./SideNav";
import { TopBar } from "./TopBar";
import { ToastContainer } from "../ui/ToastContainer";
import { StarterPromoBanner } from "../plan/StarterPromoBanner";
import { FEATURE_STARTER_ENABLED } from "@/config/features";
import { OnboardingModal } from "../onboarding/OnboardingModal";
import { useOnboardingStore } from "@/store/onboardingStore";

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
    router.replace("/onboarding");
  }, [pathname, router, session, setNeedsOnboarding, status]);

  return (
    <PlanProvider>
      <div className="flex min-h-screen bg-background-light text-text-primaryLight transition-colors dark:bg-background-dark dark:text-text-primaryDark">
        <ToastContainer />
        <OnboardingModal />
        <SideNav />
        <div className="flex min-h-screen flex-1 flex-col">
          <TopBar />
          <main className="flex flex-1 flex-col px-6 pb-8 pt-6">
            {FEATURE_STARTER_ENABLED ? <StarterPromoBanner /> : null}
            <div className="flex-1 space-y-6">{children}</div>
          </main>
        </div>
      </div>
    </PlanProvider>
  );
}
