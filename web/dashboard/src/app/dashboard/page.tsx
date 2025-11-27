'use client';
export const dynamic = "force-dynamic";

import clsx from "clsx";

import { ChatInterface } from "@/components/chat/ChatInterface";
import { DailyBriefingCard } from "@/components/briefing/DailyBriefingCard";
import { ReportEditor } from "@/components/report/ReportEditor";
import { Card } from "@/components/ui/Card";
import { useReportStore } from "@/stores/useReportStore";

export default function DashboardPage() {
  const { isOpen } = useReportStore((state) => ({ isOpen: state.isOpen }));

  return (
    <div className="min-h-screen w-full bg-canvas">
      <div className="mx-auto grid max-w-6xl grid-cols-12 gap-4 px-4 py-4 lg:gap-6 lg:px-6 lg:py-6">
        <div className="col-span-12 space-y-4 lg:col-span-4">
          <DailyBriefingCard />
        </div>
        <div className={clsx("col-span-12 transition-motion-medium", isOpen ? "lg:col-span-8" : "lg:col-span-12")}>
          <ChatInterface />
        </div>
        {isOpen ? (
          <div className="col-span-12 lg:col-span-4">
            <Card variant="raised" padding="lg" className="h-full">
              <ReportEditor />
            </Card>
          </div>
        ) : null}
      </div>
    </div>
  );
}
