import { PlanProvider } from "../plan/PlanProvider";
import { SideNav } from "./SideNav";
import { TopBar } from "./TopBar";
import { ToastContainer } from "../ui/ToastContainer";
import { StarterPromoBanner } from "../plan/StarterPromoBanner";
import { FEATURE_STARTER_ENABLED } from "@/config/features";

type AppShellProps = {
  children: React.ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  return (
    <PlanProvider>
      <div className="flex min-h-screen bg-background-light text-text-primaryLight transition-colors dark:bg-background-dark dark:text-text-primaryDark">
        <ToastContainer />
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
