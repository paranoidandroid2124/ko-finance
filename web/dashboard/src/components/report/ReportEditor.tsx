'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Typography from "@tiptap/extension-typography";
import { ExternalLink, FileSpreadsheet, Loader2, ThumbsDown, ThumbsUp, X } from "lucide-react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import html2canvas from "html2canvas";
import fetchWithAuth from "@/lib/fetchWithAuth";
import { toast } from "@/store/toastStore";
import { useReportStore } from "@/stores/useReportStore";

const CHART_COLORS = ["#3B82F6", "#A855F7", "#10B981", "#F97316", "#F43F5E"];

export function ReportEditor() {
  const { content, isGenerating, sources, ticker, reportId, charts, keyStats } = useReportStore((state) => ({
    content: state.content,
    isGenerating: state.isGenerating,
    sources: state.sources,
    ticker: state.ticker,
    reportId: state.reportId,
    charts: state.charts,
    keyStats: state.keyStats,
  }));
  const [exporting, setExporting] = useState<"pdf" | "docx" | "xlsx" | null>(null);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [feedbackState, setFeedbackState] = useState<"idle" | "liked" | "disliked">("idle");
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false);
  const [feedbackCategory, setFeedbackCategory] = useState("data_error");
  const [feedbackComment, setFeedbackComment] = useState("");
  const [feedbackLoading, setFeedbackLoading] = useState(false);

  const editor = useEditor({
    extensions: [StarterKit, Typography],
    editorProps: {
      attributes: {
        class: "prose prose-sm sm:prose lg:prose-lg xl:prose-xl max-w-none focus:outline-none",
      },
    },
    content: "",
  });

  useEffect(() => {
    if (editor && content) {
      editor.commands.setContent(content);
    }
  }, [content, editor]);

  const chartSeries = useMemo(
    () =>
      (
        charts as {
          series?: Array<{ label?: string; ticker?: string; data?: { date: string; value: number }[] }>;
        }
      )?.series ?? [],
    [charts]
  );

  const chartData = useMemo(() => {
    if (!chartSeries.length) {
      return [];
    }
    const dateMap = new Map<string, Record<string, string | number>>();
    chartSeries.forEach((series) => {
      const label = series.label || series.ticker || "Series";
      (series.data ?? []).forEach((point) => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, { date: point.date });
        }
        dateMap.get(point.date)![label] = point.value;
      });
    });
    return Array.from(dateMap.values()).sort((a, b) => (String(a.date) > String(b.date) ? 1 : -1));
  }, [chartSeries]);

  const submitFeedback = useCallback(
    async (payload: { sentiment: "LIKE" | "DISLIKE"; category?: string; comment?: string }) => {
      if (!reportId) {
        toast.show({
          intent: "warning",
          title: "리포트를 먼저 생성해주세요.",
          message: "생성된 리포트에 대해서만 피드백을 남길 수 있습니다.",
        });
        return;
      }
      try {
        setFeedbackLoading(true);
        const response = await fetchWithAuth(`/api/v1/report/${reportId}/feedback`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(typeof data?.detail === "string" ? data.detail : "피드백 전송에 실패했습니다.");
        }
        setFeedbackState(payload.sentiment === "LIKE" ? "liked" : "disliked");
        toast.show({
          intent: "success",
          title: "피드백이 접수되었습니다.",
          message: "서비스 개선에 적극 반영하겠습니다.",
        });
        setFeedbackModalOpen(false);
        setFeedbackComment("");
        setFeedbackCategory("data_error");
      } catch (error) {
        toast.show({
          intent: "error",
          title: "피드백 전송 실패",
          message: error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다.",
        });
      } finally {
        setFeedbackLoading(false);
      }
    },
    [reportId]
  );

  const handlePositiveFeedback = () => {
    if (feedbackState === "liked") {
      return;
    }
    void submitFeedback({ sentiment: "LIKE" });
  };

  const handleNegativeClick = () => {
    if (!reportId) {
      toast.show({
        intent: "warning",
        title: "리포트를 먼저 생성해주세요.",
        message: "생성된 리포트에 대해서만 피드백을 남길 수 있습니다.",
      });
      return;
    }
    setFeedbackModalOpen(true);
  };

  const feedbackOptions = [
    { value: "data_error", label: "데이터 오류" },
    { value: "hallucination", label: "환각/사실과 다름" },
    { value: "format", label: "형식/가독성 문제" },
    { value: "other", label: "기타" },
  ];

  const handleExport = useCallback(
    async (format: "pdf" | "docx" | "xlsx") => {
      if (!reportId) {
        toast.show({
          intent: "warning",
          title: "리포트가 저장되지 않았습니다.",
          message: "먼저 리포트를 생성한 다음 다시 시도해주세요.",
        });
        return;
      }
      try {
        setExporting(format);
        let chartImage: string | undefined;
        if (chartContainerRef.current) {
          const canvas = await html2canvas(chartContainerRef.current, {
            scale: Math.max(window.devicePixelRatio || 1, 2),
            backgroundColor: "#ffffff",
            useCORS: true,
          });
          chartImage = canvas.toDataURL("image/png");
        }
        const response = await fetchWithAuth(`/api/v1/report/${reportId}/export`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            format,
            chartImage,
            keyStats: keyStats ?? undefined,
          }),
        });
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          const message = typeof payload?.detail === "string" ? payload.detail : "내보내기에 실패했습니다.";
          throw new Error(message);
        }
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        const basename = ticker ? ticker.toUpperCase() : "investment_memo";
        const extension = format === "xlsx" ? "xlsx" : format;
        link.download = `${basename}.${extension}`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
        toast.show({
          intent: "success",
          title: "내보내기 완료",
          message: `${format.toUpperCase()} 파일로 저장했습니다.`,
        });
      } catch (error) {
        toast.show({
          intent: "error",
          title: "내보내기에 실패했습니다.",
          message: error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다.",
        });
      } finally {
        setExporting(null);
      }
    },
    [keyStats, reportId, ticker]
  );

  if (isGenerating) {
    return (
      <div className="flex h-full flex-col items-center justify-center space-y-4 bg-surface">
        <div className="h-4 w-40 animate-pulse rounded bg-slate-800" />
        <div className="h-4 w-28 animate-pulse rounded bg-slate-800" />
        <div className="text-xs text-slate-400">AI Analyst is analyzing market data...</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-surface text-slate-100">
      <div className="sticky top-0 z-10 flex gap-2 border-b border-border-dark bg-surface/80 p-2 backdrop-blur">
        <button
          type="button"
          className="rounded bg-primary px-3 py-1 text-xs font-medium text-white transition hover:bg-primary-hover disabled:cursor-not-allowed disabled:bg-primary/40"
          disabled={exporting !== null}
          onClick={() => handleExport("pdf")}
          data-onboarding-id="export-report-button"
        >
          {exporting === "pdf" ? "Exporting..." : "Export PDF"}
        </button>
        <button
          type="button"
          className="rounded border border-border-dark/70 px-3 py-1 text-xs font-medium text-slate-200 transition hover:border-primary disabled:cursor-not-allowed disabled:border-border-dark/40 disabled:text-slate-500"
          disabled={exporting !== null}
          onClick={() => handleExport("docx")}
        >
          {exporting === "docx" ? "Exporting..." : "Export Word"}
        </button>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded border border-border-dark/70 px-3 py-1 text-xs font-medium text-slate-200 transition hover:border-primary disabled:cursor-not-allowed disabled:border-border-dark/40 disabled:text-slate-500"
          disabled={exporting !== null}
          onClick={() => handleExport("xlsx")}
        >
          <FileSpreadsheet className="h-3.5 w-3.5" />
          {exporting === "xlsx" ? "Exporting..." : "Excel Data"}
        </button>
      </div>
      <div className="relative flex-1 overflow-y-auto p-6">
        {exporting && (
          <div className="no-print pointer-events-none absolute inset-0 z-20 flex items-center justify-center bg-background-dark/80 backdrop-blur">
            <div className="flex items-center gap-3 rounded-lg border border-border-dark bg-surface px-4 py-3 shadow-xl shadow-black/40">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-700 border-t-primary" />
              <span className="text-sm font-medium text-slate-100">문서 생성 중...</span>
            </div>
          </div>
        )}
        <div className="report-container space-y-8 rounded-3xl border border-border-dark/60 bg-surface/95 p-6 shadow-[0_25px_55px_rgba(2,6,23,0.55)]">
          <EditorContent editor={editor} />
          {chartData.length > 0 && (
            <div
              ref={chartContainerRef}
              data-onboarding-id="report-chart"
              className="space-y-4 rounded-2xl border border-border-dark bg-background-dark/60 p-4"
            >
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Market Performance</p>
                <p className="text-sm text-slate-400">Normalized % return over the last period</p>
              </div>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                    <XAxis dataKey="date" stroke="#94A3B8" tick={{ fill: "#94A3B8" }} />
                    <YAxis stroke="#94A3B8" tick={{ fill: "#94A3B8" }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#1E293B",
                        borderColor: "#334155",
                        color: "#F1F5F9",
                      }}
                    />
                    <Legend />
                    {chartSeries.map((series, index) => {
                      const label = series.label || series.ticker || `Series ${index + 1}`;
                      return (
                        <Line
                          key={label}
                          type="monotone"
                          dataKey={label}
                          stroke={CHART_COLORS[index % CHART_COLORS.length]}
                          dot={false}
                          strokeWidth={2}
                        />
                      );
                    })}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
          {sources.length > 0 && (
            <div className="border-t border-border-dark/70 pt-6">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">References</p>
              <div className="mt-4 space-y-3">
                {sources.map((source, idx) => (
                  <a
                    key={`${source.title}-${source.url}`}
                    href={source.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-start justify-between rounded-2xl border border-border-dark/60 px-3 py-2 text-sm text-slate-200 transition hover:border-primary"
                  >
                    <span>
                      <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-slate-800 text-xs font-semibold text-slate-200">
                        {source.index ?? idx + 1}
                      </span>
                      <span className="font-medium text-slate-100">{source.title}</span>
                      <span className="ml-2 text-xs text-slate-400">[{source.date}]</span>
                    </span>
                    <ExternalLink className="h-4 w-4 text-slate-500" />
                  </a>
                ))}
              </div>
            </div>
          )}
          <div className="border-t border-border-dark/70 pt-6">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">이 리포트가 도움이 되었나요?</p>
            <div className="mt-3 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handlePositiveFeedback}
                disabled={feedbackLoading || feedbackState === "liked"}
                className={clsx(
                  "inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold transition",
                  feedbackState === "liked"
                    ? "border-primary bg-primary/20 text-primary"
                    : "border-border-dark text-slate-200 hover:border-primary"
                )}
              >
                <ThumbsUp className="h-4 w-4" />
                도움됨
              </button>
              <button
                type="button"
                onClick={handleNegativeClick}
                disabled={feedbackLoading}
                className={clsx(
                  "inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold transition",
                  feedbackState === "disliked"
                    ? "border-rose-500/60 bg-rose-500/10 text-rose-300"
                    : "border-border-dark text-slate-200 hover:border-rose-400"
                )}
              >
                <ThumbsDown className="h-4 w-4" />
                부정확했어요
              </button>
            </div>
          </div>
        </div>
        {feedbackModalOpen && (
          <div className="no-print pointer-events-auto fixed inset-0 z-30 flex items-center justify-center bg-black/60 backdrop-blur">
            <div className="w-full max-w-md rounded-2xl border border-border-dark bg-surface p-6 text-slate-100 shadow-2xl">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-semibold">어떤 문제가 있었나요?</h3>
                  <p className="mt-1 text-sm text-slate-400">더 정확한 서비스를 위해 아래 내용을 선택해주세요.</p>
                </div>
                <button
                  type="button"
                  onClick={() => setFeedbackModalOpen(false)}
                  className="text-slate-500 transition hover:text-slate-300"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              <div className="mt-4 space-y-3">
                {feedbackOptions.map((option) => (
                  <label
                    key={option.value}
                    className={clsx(
                      "flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm transition",
                      feedbackCategory === option.value
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border-dark text-slate-200 hover:border-primary/60"
                    )}
                  >
                    <input
                      type="radio"
                      className="hidden"
                      value={option.value}
                      checked={feedbackCategory === option.value}
                      onChange={() => setFeedbackCategory(option.value)}
                    />
                    <span>{option.label}</span>
                  </label>
                ))}
              </div>
              <textarea
                value={feedbackComment}
                onChange={(event) => setFeedbackComment(event.target.value)}
                placeholder="자세한 내용을 알려주시면 서비스 개선에 도움이 됩니다. (선택)"
                className="mt-4 w-full rounded-2xl border border-border-dark bg-background-dark/60 p-3 text-sm text-slate-100 placeholder:text-slate-500 focus:border-primary focus:outline-none"
                rows={3}
              />
              <div className="mt-6 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setFeedbackModalOpen(false)}
                  className="text-sm text-slate-400 hover:text-slate-200"
                  disabled={feedbackLoading}
                >
                  취소
                </button>
                <button
                  type="button"
                  onClick={() =>
                    submitFeedback({
                      sentiment: "DISLIKE",
                      category: feedbackCategory,
                      comment: feedbackComment || undefined,
                    })
                  }
                  disabled={feedbackLoading}
                  className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-primary/40 disabled:cursor-not-allowed disabled:bg-primary/40"
                >
                  {feedbackLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ThumbsDown className="h-4 w-4" />}
                  전송하기
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ReportEditor;
