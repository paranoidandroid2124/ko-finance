'use client';
export const dynamic = "force-dynamic";

import clsx from "clsx";

import { ChatInterface } from "@/components/chat/ChatInterface";
import { DailyBriefingCard } from "@/components/briefing/DailyBriefingCard";
import { ReportEditor } from "@/components/report/ReportEditor";
import { useReportStore } from "@/stores/useReportStore";

export default function DashboardPage() {
  const { isOpen } = useReportStore((state) => ({ isOpen: state.isOpen }));

  return (
    <div className="relative flex h-screen w-full overflow-hidden">
      <div className="pointer-events-auto absolute left-4 top-4 z-30 max-w-xl">
        <DailyBriefingCard />
      </div>
      <main className={clsx("flex-1 transition-all duration-300", isOpen ? "mr-[420px]" : "")}>
        <ChatInterface />
      </main>
      <aside
        className={clsx(
          "fixed right-4 top-4 z-40 h-[calc(100vh-2rem)] w-[360px] rounded-3xl border border-white/10 bg-[#050a1c]/70 p-4 shadow-[0_25px_120px_rgba(15,23,42,0.45)] backdrop-blur-2xl transition-transform duration-300",
          isOpen ? "translate-x-0 opacity-100" : "translate-x-[420px] opacity-0"
        )}
      >
        <ReportEditor />
      </aside>
    </div>
  );
}
