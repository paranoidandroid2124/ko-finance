import { SideNav } from "./SideNav";
import { TopBar } from "./TopBar";
import { RightRail } from "./RightRail";

type AppShellProps = {
  children: React.ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="flex min-h-screen bg-background-light text-text-primaryLight transition-colors dark:bg-background-dark dark:text-text-primaryDark">
      <SideNav />
      <div className="flex min-h-screen flex-1 flex-col">
        <TopBar />
        <main className="flex flex-1 flex-row gap-6 px-6 pb-8 pt-6">
          <div className="flex-1 space-y-6">{children}</div>
          <RightRail />
        </main>
      </div>
    </div>
  );
}

