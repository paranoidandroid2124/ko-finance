"use client";

import { useState } from "react";

import { CalendarDays, Download, FileText, Loader2, RefreshCw } from "lucide-react";

import { useDailyBriefRuns, useGenerateDailyBrief } from "@/hooks/useReports";
import { ApiError, buildDailyBriefDownloadUrl } from "@/lib/reportsApi";
import { formatKoreanDateTime } from "@/lib/datetime";
import { useToastStore } from "@/store/toastStore";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";

const formatBytes = (value?: number | null) => {
  if (!value || value <= 0) {
    return "-";
  }
  if (value < 1024) {
    return `${value}B`;
  }
  const units = ["KB", "MB", "GB", "TB"];
  let size = value / 1024;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(size >= 100 ? 0 : 1)}${units[index]}`;
};

export function AdminReportsPanel() {
  const limit = 10;
  const [targetDate, setTargetDate] = useState<string>("");
  const [compilePdf, setCompilePdf] = useState(true);
  const [forceRun, setForceRun] = useState(false);

  const {
    data: runs,
    isLoading,
    isFetching,
    isError,
    refetch,
  } = useDailyBriefRuns(limit);
  const generateBrief = useGenerateDailyBrief();
  const showToast = useToastStore((state) => state.show);

  const handleGenerate = async () => {
    try {
      const payload = {
        asyncMode: true,
        compilePdf,
        force: forceRun,
        referenceDate: targetDate ? targetDate : undefined,
      };
      const result = await generateBrief.mutateAsync(payload);
      const status =
        result.status === "queued"
          ? "데일리 브리프 생성 작업을 큐에 등록했어요."
          : result.status === "already_generated"
            ? "이미 생성된 브리프가 있어요. force 옵션을 확인해 주세요."
            : "데일리 브리프를 생성했어요.";
      showToast({
        intent: result.status === "already_generated" ? "warning" : "success",
        message: status,
      });
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : "데일리 브리프 생성 요청에 실패했어요.";
      showToast({
        intent: "error",
        message,
      });
    }
  };

  const handleRefresh = () => {
    void refetch();
  };

  const isEmpty = !isLoading && !isError && (runs?.length ?? 0) === 0;

  const renderRunsTable = () => {
    if (!runs || runs.length === 0) {
      return null;
    }

    return (
      <div className="overflow-x-auto rounded-lg border border-border-light dark:border-border-dark">
        <table className="min-w-full divide-y divide-border-light/70 text-sm dark:divide-border-dark/60">
          <thead className="bg-border-light/40 text-xs uppercase tracking-wide text-text-secondaryLight dark:bg-border-dark/30 dark:text-text-secondaryDark">
            <tr>
              <th scope="col" className="px-4 py-3 text-left">
                기준일
              </th>
              <th scope="col" className="px-4 py-3 text-left">
                생성 시각
              </th>
              <th scope="col" className="px-4 py-3 text-left">
                PDF
              </th>
              <th scope="col" className="px-4 py-3 text-left">
                TeX
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-light/50 dark:divide-border-dark/40">
        {runs.map((run) => {
          const pdfUrl = run.pdf.downloadUrl ?? buildDailyBriefDownloadUrl(run.referenceDate, "pdf");
          const texUrl = run.tex.downloadUrl ?? buildDailyBriefDownloadUrl(run.referenceDate, "tex");
          const hasPdf = run.pdf.exists || Boolean(run.pdf.downloadUrl);
          const hasTex = run.tex.exists || Boolean(run.tex.downloadUrl);
          return (
            <tr key={run.id} className="bg-background-cardLight hover:bg-primary/5 dark:bg-background-cardDark dark:hover:bg-primary.dark/10">
                  <td className="px-4 py-3">
                    <div className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{run.referenceDate}</div>
                    <div className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{run.channel}</div>
                  </td>
                  <td className="px-4 py-3 text-text-secondaryLight dark:text-text-secondaryDark">
                    {formatKoreanDateTime(run.generatedAt, { includeSeconds: true })}
                  </td>
                  <td className="px-4 py-3">
                    {hasPdf ? (
                      <div className="flex items-center gap-2">
                        <a
                          href={pdfUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-2 py-1 text-xs font-semibold text-primary transition hover:bg-primary/20 dark:bg-primary.dark/15 dark:text-primary.dark dark:hover:bg-primary.dark/25"
                        >
                          <Download className="h-3.5 w-3.5" aria-hidden />
                          PDF 다운로드
                        </a>
                        <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                          {formatBytes(run.pdf.sizeBytes)}
                        </span>
                        {run.pdf.provider ? (
                          <span className="text-[10px] uppercase text-text-secondaryLight dark:text-text-secondaryDark">
                            {run.pdf.provider}
                          </span>
                        ) : null}
                      </div>
                    ) : (
                      <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">생성 전</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {hasTex ? (
                      <div className="flex items-center gap-2">
                        <a
                          href={texUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 rounded-md border border-border-light px-2 py-1 text-xs font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
                        >
                          <FileText className="h-3.5 w-3.5" aria-hidden />
                          TeX 열기
                        </a>
                        <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                          {formatBytes(run.tex.sizeBytes)}
                        </span>
                        {run.tex.provider ? (
                          <span className="text-[10px] uppercase text-text-secondaryLight dark:text-text-secondaryDark">
                            {run.tex.provider}
                          </span>
                        ) : null}
                      </div>
                    ) : (
                      <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">생성 전</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="space-y-4 rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <header className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">데일리 브리프 PDF</h3>
          <p className="mt-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            매일 생성되는 LaTeX 브리프를 확인하고 필요할 때 즉시 재생성할 수 있어요. 생성된 PDF는 다운로드 링크로 제공돼요.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleRefresh}
            className="inline-flex items-center gap-2 rounded-md border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} aria-hidden />
            새로고침
          </button>
        </div>
      </header>

      <section className="rounded-lg border border-dashed border-border-light/80 bg-background-light/60 p-4 text-sm text-text-secondaryLight dark:border-border-dark/70 dark:bg-background-dark/40 dark:text-text-secondaryDark">
        <h4 className="flex items-center gap-2 text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
          <CalendarDays className="h-4 w-4" aria-hidden />
          생성 옵션
        </h4>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-semibold uppercase tracking-wide">대상 날짜</span>
            <input
              type="date"
              value={targetDate}
              onChange={(event) => setTargetDate(event.target.value)}
              className="rounded-md border border-border-light bg-background-cardLight px-2 py-1 text-sm text-text-primaryLight shadow-sm outline-none transition focus:border-primary focus:ring-1 focus:ring-primary dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
            />
            <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">비워두면 오늘 날짜 기준으로 생성돼요.</span>
          </label>
          <label className="flex items-center gap-2 text-xs font-semibold text-text-secondaryLight dark:text-text-secondaryDark">
            <input
              type="checkbox"
              checked={compilePdf}
              onChange={(event) => setCompilePdf(event.target.checked)}
              className="h-4 w-4 rounded border-border-light text-primary focus:ring-primary dark:border-border-dark"
            />
            PDF까지 컴파일하기
          </label>
          <label className="flex items-center gap-2 text-xs font-semibold text-text-secondaryLight dark:text-text-secondaryDark">
            <input
              type="checkbox"
              checked={forceRun}
              onChange={(event) => setForceRun(event.target.checked)}
              className="h-4 w-4 rounded border-border-light text-primary focus:ring-primary dark:border-border-dark"
            />
            기존 결과가 있어도 재생성 (force)
          </label>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleGenerate}
            disabled={generateBrief.isPending}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-semibold text-white shadow transition hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-70 dark:bg-primary.dark dark:hover:bg-primary.dark/90"
          >
            {generateBrief.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
            데일리 브리프 생성
          </button>
          <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            생성된 결과는 목록에 자동으로 업데이트돼요.
          </span>
        </div>
      </section>

      {isLoading ? (
        <SkeletonBlock lines={6} />
      ) : isError ? (
        <ErrorState
          title="데일리 브리프 목록을 불러오지 못했어요."
          description="네트워크 상태를 확인한 뒤 다시 시도해 주세요."
          action={
            <button
              type="button"
              onClick={handleRefresh}
              className="inline-flex items-center gap-2 rounded-md border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
            >
              다시 시도
            </button>
          }
        />
      ) : isEmpty ? (
        <EmptyState
          title="아직 생성된 데일리 브리프가 없어요."
          description="상단의 생성 버튼을 눌러 첫 번째 브리프를 만들어보세요."
          action={
            <button
              type="button"
              onClick={handleGenerate}
              disabled={generateBrief.isPending}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-semibold text-white shadow transition hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-70 dark:bg-primary.dark dark:hover:bg-primary.dark/90"
            >
              {generateBrief.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
              지금 생성하기
            </button>
          }
        />
      ) : (
        renderRunsTable()
      )}
    </div>
  );
}
