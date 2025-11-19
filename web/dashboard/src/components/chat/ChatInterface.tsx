'use client';

import { useCallback } from "react";
import { FileText } from "lucide-react";

import { ChatPageShell } from "@/components/chat/ChatPageShell";
import { useGenerateReport } from "@/hooks/useGenerateReport";
import { useChatController } from "@/hooks/useChatController";

export function ChatInterface() {
  const controller = useChatController();
  const generateReport = useGenerateReport();

  const handleReportClick = useCallback(() => {
    if (typeof window === "undefined") {
      return;
    }
    const ticker = window.prompt("어떤 종목으로 투자 메모를 생성할까요? (예: 005930, AAPL)");
    const normalized = ticker?.trim();
    if (!normalized) {
      return;
    }
    generateReport.mutate({ ticker: normalized });
  }, [generateReport]);

  return (
    <div className="relative h-full">
      <ChatPageShell controller={controller} />
      <button
        type="button"
        className="fixed bottom-8 right-8 flex items-center gap-2 rounded-full bg-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-2xl transition hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
        onClick={handleReportClick}
        disabled={generateReport.isPending}
      >
        <FileText className="h-4 w-4" />
        {generateReport.isPending ? "Generating…" : "Generate Report"}
      </button>
    </div>
  );
}

export default ChatInterface;
