'use client';
export const dynamic = "force-dynamic";

import clsx from "clsx";
import { useEffect, useState } from "react";

import { ChatInterface } from "@/components/chat/ChatInterface";
import { DailyBriefingCard } from "@/components/briefing/DailyBriefingCard";
import { ReportEditor } from "@/components/report/ReportEditor";
import { Card } from "@/components/ui/Card";
import fetchWithAuth from "@/lib/fetchWithAuth";
import { toast } from "@/store/toastStore";
import { useReportStore } from "@/stores/useReportStore";

const PROACTIVE_LAST_SEEN_KEY = "__proactive_last_seen_id__";

export default function DashboardPage() {
  const { isOpen } = useReportStore((state) => ({ isOpen: state.isOpen }));
  const [proactiveChecked, setProactiveChecked] = useState(false);

  useEffect(() => {
    if (proactiveChecked) {
      return;
    }
    let cancelled = false;
    const run = async () => {
      try {
        const res = await fetchWithAuth("/api/v1/feed/proactive/briefings?limit=1");
        if (!res.ok) {
          return;
        }
        const data = await res.json();
        const first = Array.isArray(data?.items) && data.items.length > 0 ? data.items[0] : null;
        if (!first?.id) {
          return;
        }
        const lastSeen = typeof window !== "undefined" ? window.localStorage.getItem(PROACTIVE_LAST_SEEN_KEY) : null;
        if (lastSeen === first.id) {
          return;
        }
        if (typeof window !== "undefined") {
          window.localStorage.setItem(PROACTIVE_LAST_SEEN_KEY, first.id);
        }
        toast.show({
          title: "새 프로액티브 인사이트",
          message: first.title || "새 인사이트가 도착했습니다.",
          intent: "info",
          actionLabel: "Insight Hub 열기",
          onAction: () => {
            window.location.href = "/insights";
          }
        });
      } catch {
        // silent best-effort
      } finally {
        if (!cancelled) {
          setProactiveChecked(true);
        }
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [proactiveChecked]);

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
