'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FileText, Loader2 } from "lucide-react";

import { ChatPageShell } from "@/components/chat/ChatPageShell";
import OnboardingGuide from "@/components/onboarding/OnboardingGuide";
import { useGenerateReport } from "@/hooks/useGenerateReport";
import { useChatController } from "@/hooks/useChatController";
import { extractEventStudyKeyStats } from "@/lib/reportExport";
import { useReportStore } from "@/stores/useReportStore";

export function ChatInterface() {
  const controller = useChatController();
  const generateReport = useGenerateReport();
  const messages = controller.stream.messages;
  const setKeyStats = useReportStore((state) => state.setKeyStats);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [tickerInput, setTickerInput] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const lastStatsRef = useRef<string | null>(null);

  useEffect(() => {
    const stats = extractEventStudyKeyStats(messages);
    if (!stats) {
      return;
    }
    const serialized = JSON.stringify(stats);
    if (serialized === lastStatsRef.current) {
      return;
    }
    lastStatsRef.current = serialized;
    setKeyStats(stats);
  }, [messages, setKeyStats]);

  const normalizedTicker = useMemo(() => tickerInput.trim().toUpperCase(), [tickerInput]);

  const handleReportClick = useCallback(() => {
    setDialogOpen(true);
  }, []);

  const handleDialogClose = useCallback(() => {
    setDialogOpen(false);
    setInputError(null);
  }, []);

  const handleSubmit = useCallback(
    (event?: React.FormEvent<HTMLFormElement>) => {
      event?.preventDefault();
      const normalized = normalizedTicker;
      if (!normalized) {
        setInputError("Enter a ticker symbol");
        return;
      }
      generateReport.mutate({ ticker: normalized });
      setDialogOpen(false);
      setTickerInput("");
      setInputError(null);
    },
    [generateReport, normalizedTicker]
  );

  return (
    <div className="relative h-full">
      <ChatPageShell controller={controller} />
      <OnboardingGuide />
      <button
        type="button"
        className="fixed bottom-8 right-8 flex items-center gap-2 rounded-full bg-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-2xl transition hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
        onClick={handleReportClick}
        disabled={generateReport.isPending}
      >
        <FileText className="h-4 w-4" />
        {generateReport.isPending ? "Generating…" : "Generate Report"}
      </button>

      {dialogOpen && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4">
          <form
            className="w-full max-w-md rounded-3xl border border-border-dark bg-surface p-6 text-slate-100 shadow-2xl"
            onSubmit={handleSubmit}
          >
            <div className="flex items-center gap-3 text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">
              <FileText className="h-4 w-4 text-primary" />
              New Report
            </div>
            <h2 className="mt-3 text-2xl font-semibold text-white">Which ticker do you want to analyze?</h2>
            <p className="mt-2 text-sm text-slate-400">
              Examples: <span className="font-semibold text-slate-200">AAPL</span>,{" "}
              <span className="font-semibold text-slate-200">005930</span>,{" "}
              <span className="font-semibold text-slate-200">TSLA</span>
            </p>
            <div className="mt-6 space-y-2">
              <label htmlFor="report-ticker" className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Ticker
              </label>
              <input
                id="report-ticker"
                name="ticker"
                autoFocus
                value={tickerInput}
                onChange={(event) => setTickerInput(event.target.value)}
                className="w-full rounded-2xl border border-border-dark bg-background-dark px-4 py-3 text-base font-semibold uppercase tracking-wide text-white placeholder:text-slate-500 focus:border-primary focus:outline-none"
                placeholder="e.g. AAPL"
              />
              {inputError && <p className="text-xs text-rose-400">{inputError}</p>}
            </div>
            <div className="mt-6 flex items-center justify-end gap-3">
              <button
                type="button"
                className="rounded-full px-4 py-2 text-sm font-semibold text-slate-400 hover:text-slate-200"
                onClick={handleDialogClose}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-primary/40 disabled:cursor-not-allowed disabled:bg-primary/40"
                disabled={generateReport.isPending}
              >
                {generateReport.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Create report
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

export default ChatInterface;
