"use client";

import clsx from "clsx";
import { Clock, FileText, FolderOpen, RefreshCw } from "lucide-react";
import useSWR from "swr";

import { ReportEditor } from "@/components/report/ReportEditor";
import fetchWithAuth from "@/lib/fetchWithAuth";
import { formatDateTime } from "@/lib/date";
import { useReportStore, type ReportSource } from "@/stores/useReportStore";

type ReportHistoryItem = {
  id: string;
  ticker: string;
  title?: string | null;
  content: string;
  sources: ReportSource[];
  createdAt: string;
};

type ReportHistoryResponse = {
  items: ReportHistoryItem[];
};

const fetcher = async (url: string) => {
  const res = await fetchWithAuth(url);
  if (!res.ok) {
    let detail = "Failed to load report history.";
    try {
      const payload = await res.json();
      if (typeof payload?.detail === "string") {
        detail = payload.detail;
      }
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return res.json();
};

export default function ReportHistoryPage() {
  const { data, isLoading, error, mutate } = useSWR<ReportHistoryResponse>("/api/v1/report/history", fetcher);
  const {
    isOpen,
    openPanel,
    setContent,
    setSources,
    setTicker,
    setReportId,
    setGenerating,
    setCharts,
    setKeyStats,
  } = useReportStore((state) => ({
    isOpen: state.isOpen,
    openPanel: state.openPanel,
    setContent: state.setContent,
    setSources: state.setSources,
    setTicker: state.setTicker,
    setReportId: state.setReportId,
    setGenerating: state.setGenerating,
    setCharts: state.setCharts,
    setKeyStats: state.setKeyStats,
  }));

  const openReport = (item: ReportHistoryItem) => {
    setGenerating(false);
    setContent(item.content);
    setSources(item.sources ?? []);
    setTicker(item.ticker);
    setReportId(item.id);
    setCharts(null);
    setKeyStats(null);
    openPanel();
  };

  const handleRefresh = () => mutate();

  const reports = data?.items ?? [];

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background-dark text-slate-100">
      <main className={clsx("flex-1 overflow-y-auto p-8", isOpen ? "mr-[480px]" : "")}>
        <header className="mb-10 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.4em] text-slate-500">My Reports</p>
            <h1 className="text-3xl font-semibold text-white">Saved investment memos</h1>
            <p className="mt-2 text-sm text-slate-400">Reopen and export any report you generated previously.</p>
          </div>
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-full border border-border-dark px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-primary hover:text-white"
            onClick={handleRefresh}
            disabled={isLoading}
          >
            <RefreshCw className={clsx("h-4 w-4", isLoading && "animate-spin")} />
            Refresh
          </button>
        </header>

        {error && (
          <div className="mb-8 rounded-2xl border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-200">
            {error.message}
          </div>
        )}

        <section className="space-y-4">
          {isLoading && (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, index) => (
                <div key={`skeleton-${index}`} className="h-24 animate-pulse rounded-2xl bg-slate-900/60" />
              ))}
            </div>
          )}

          {!isLoading && reports.length === 0 && (
            <div className="flex flex-col items-center justify-center rounded-3xl border border-dashed border-border-dark/70 bg-slate-900/40 px-8 py-16 text-center">
              <FolderOpen className="mb-4 h-8 w-8 text-slate-500" />
              <h3 className="text-xl font-semibold text-white">No reports yet</h3>
              <p className="mt-2 text-sm text-slate-400">Ask the AI analyst for a ticker in chat to create your first report.</p>
            </div>
          )}

          {reports.map((item) => (
            <article
              key={item.id}
              className="flex flex-col gap-4 rounded-3xl border border-border-dark bg-surface/80 p-6 shadow-lg shadow-black/20 sm:flex-row sm:items-center sm:justify-between"
            >
              <div>
                <div className="flex items-center gap-3">
                  <div className="rounded-full border border-primary/40 px-3 py-1 text-xs font-semibold tracking-wide text-primary">
                    {item.ticker.toUpperCase()}
                  </div>
                  <span className="flex items-center gap-1 text-xs text-slate-400">
                    <Clock className="h-3.5 w-3.5" />
                    {formatDateTime(item.createdAt, { fallback: "-" })}
                  </span>
                </div>
                <h3 className="mt-3 text-xl font-semibold text-white">{item.title || "Untitled memo"}</h3>
                <p className="mt-1 line-clamp-2 text-sm text-slate-400">
                  {item.content.replace(/<[^>]+>/g, "").slice(0, 160) || "Report content available in the viewer."}
                </p>
              </div>
              <div className="flex flex-col gap-3 sm:items-end">
                <button
                  type="button"
                  className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2 text-sm font-semibold text-white shadow-primary/40 transition hover:bg-primary/90"
                  onClick={() => openReport(item)}
                >
                  <FileText className="h-4 w-4" />
                  View in editor
                </button>
                <span className="text-xs uppercase tracking-[0.3em] text-slate-500">
                  {item.sources.length} sources captured
                </span>
              </div>
            </article>
          ))}
        </section>
      </main>

      <aside
        className={clsx(
          "fixed right-0 top-0 z-30 h-full w-[480px] border-l border-border-dark bg-surface shadow-2xl transition-transform duration-300",
          isOpen ? "translate-x-0" : "translate-x-full"
        )}
      >
        <ReportEditor />
      </aside>
    </div>
  );
}
