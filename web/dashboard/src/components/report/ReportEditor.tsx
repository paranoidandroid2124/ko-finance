'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Typography from "@tiptap/extension-typography";
import { ExternalLink } from "lucide-react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import html2canvas from "html2canvas";
import fetchWithAuth from "@/lib/fetchWithAuth";
import { toast } from "@/store/toastStore";
import { useReportStore } from "@/stores/useReportStore";

export function ReportEditor() {
  const { content, isGenerating, sources, ticker, reportId, charts } = useReportStore((state) => ({
    content: state.content,
    isGenerating: state.isGenerating,
    sources: state.sources,
    ticker: state.ticker,
    reportId: state.reportId,
    charts: state.charts,
  }));
  const [exporting, setExporting] = useState<"pdf" | "docx" | null>(null);
  const chartContainerRef = useRef<HTMLDivElement>(null);

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

  const chartSeries = (charts as { series?: Array<{ label?: string; ticker?: string; data?: { date: string; value: number }[] }> })
    ?.series ?? [];
  const chartData = useMemo(() => {
    if (!chartSeries.length) {
      return [];
    }
    const dateMap = new Map<string, Record<string, number>>();
    chartSeries.forEach((series) => {
      const label = series.label || series.ticker || "Series";
      (series.data ?? []).forEach((point) => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, { date: point.date });
        }
        dateMap.get(point.date)![label] = point.value;
      });
    });
    return Array.from(dateMap.values()).sort((a, b) => (a.date > b.date ? 1 : -1));
  }, [chartSeries]);

  const handleExport = useCallback(
    async (format: "pdf" | "docx") => {
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
        link.download = `${basename}.${format}`;
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
    [reportId, ticker]
  );

  if (isGenerating) {
    return (
      <div className="flex h-full flex-col items-center justify-center space-y-4">
        <div className="h-4 w-40 animate-pulse rounded bg-slate-100" />
        <div className="h-4 w-28 animate-pulse rounded bg-slate-100" />
        <div className="text-xs text-slate-400">AI Analyst is analyzing market data...</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="sticky top-0 z-10 flex gap-2 border-b bg-white p-2">
        <button
          type="button"
          className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-400"
          disabled={exporting !== null}
          onClick={() => handleExport("pdf")}
        >
          {exporting === "pdf" ? "Exporting..." : "Export PDF"}
        </button>
        <button
          type="button"
          className="rounded bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700 transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
          disabled={exporting !== null}
          onClick={() => handleExport("docx")}
        >
          {exporting === "docx" ? "Exporting..." : "Export Word"}
        </button>
      </div>
      <div className="relative flex-1 overflow-y-auto p-6">
        {exporting && (
          <div className="no-print pointer-events-none absolute inset-0 z-20 flex items-center justify-center bg-white/70 backdrop-blur-sm">
            <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 shadow">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-blue-500" />
              <span className="text-sm font-medium text-slate-700">문서 생성 중...</span>
            </div>
          </div>
        )}
        <div className="report-container space-y-8 rounded-xl bg-white p-4 shadow-card">
          <EditorContent editor={editor} />
          {chartData.length > 0 && (
            <div ref={chartContainerRef} className="space-y-4 rounded-lg border border-slate-100 bg-white p-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Market Performance</p>
                <p className="text-sm text-slate-500">Normalized % return over the last period</p>
              </div>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend />
                    {chartSeries.map((series, index) => {
                      const label = series.label || series.ticker || `Series ${index + 1}`;
                      const colorPalette = ["#3b82f6", "#10b981", "#f97316", "#6366f1", "#ef4444", "#06b6d4"];
                      return (
                        <Line
                          key={label}
                          type="monotone"
                          dataKey={label}
                          stroke={colorPalette[index % colorPalette.length]}
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
            <div className="border-t pt-6">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">References</p>
              <div className="mt-4 space-y-3">
                {sources.map((source) => (
                  <a
                    key={`${source.title}-${source.url}`}
                    href={source.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-start justify-between rounded-lg border border-slate-100 px-3 py-2 text-sm text-slate-700 transition hover:border-blue-200 hover:bg-blue-50"
                  >
                    <span>
                      <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-slate-200 text-xs font-semibold text-slate-700">
                        {source.index ?? sources.indexOf(source) + 1}
                      </span>
                      <span className="font-medium text-slate-900">{source.title}</span>
                      <span className="ml-2 text-xs text-slate-500">[{source.date}]</span>
                    </span>
                    <ExternalLink className="h-4 w-4 text-slate-400" />
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ReportEditor;
