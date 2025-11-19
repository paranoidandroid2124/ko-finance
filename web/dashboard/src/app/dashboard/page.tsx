'use client';

import clsx from "clsx";

import { ChatInterface } from "@/components/chat/ChatInterface";
import { ReportEditor } from "@/components/report/ReportEditor";
import { useReportStore } from "@/stores/useReportStore";

export default function DashboardPage() {
  const { isOpen } = useReportStore((state) => ({ isOpen: state.isOpen }));

  return (
    <div className="flex h-screen w-full overflow-hidden bg-slate-50">
      <main className={clsx("flex-1 transition-all duration-300", isOpen ? "mr-[480px]" : "")}>
        <ChatInterface />
      </main>
      <aside
        className={clsx(
          "fixed right-0 top-0 z-50 h-full w-[480px] border-l border-slate-100 bg-white shadow-2xl transition-transform duration-300",
          isOpen ? "translate-x-0" : "translate-x-full"
        )}
      >
        <ReportEditor />
      </aside>
    </div>
  );
}
