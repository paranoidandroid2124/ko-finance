"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { GenericToolPlaceholder } from "@/components/tools/panels/GenericToolPlaceholder";
import { useGenerateReport } from "@/hooks/useGenerateReport";
import { useReportStore } from "@/stores/useReportStore";

type CommanderToolProps = {
  params?: Record<string, unknown>;
  decision?: unknown;
};

export function InvestmentReportPanel({ params }: CommanderToolProps) {
  const initialTicker = useMemo(
    () => (typeof params?.ticker === "string" && params.ticker.trim() ? params.ticker.trim().toUpperCase() : ""),
    [params?.ticker],
  );
  const [ticker, setTicker] = useState(initialTicker);
  const [error, setError] = useState<string | null>(null);
  const generateReport = useGenerateReport();
  const isGenerating = useReportStore((state) => state.isGenerating);

  useEffect(() => {
    if (initialTicker) {
      setTicker(initialTicker);
    }
  }, [initialTicker]);

  const handleSubmit = useCallback(
    (e?: React.FormEvent) => {
      e?.preventDefault();
      const normalized = ticker.trim().toUpperCase();
      if (!normalized) {
        setError("티커를 입력하세요.");
        return;
      }
      setError(null);
      generateReport.mutate({ ticker: normalized });
    },
    [generateReport, ticker],
  );

  if (!generateReport) {
    return <GenericToolPlaceholder title="투자 리포트" description="리포트 생성 훅을 불러오지 못했습니다." />;
  }

  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-white/10 bg-white/5 p-4">
      <div>
        <p className="text-xs uppercase tracking-[0.3em] text-indigo-200">Investment Report</p>
        <p className="mt-1 text-lg font-semibold text-white">티커 기반 리포트 생성</p>
        <p className="mt-1 text-sm text-slate-300">뉴스·피어 데이터를 모아 자동으로 Markdown 메모를 만듭니다.</p>
      </div>

      <form className="flex flex-col gap-3 md:flex-row md:items-center" onSubmit={handleSubmit}>
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="예: 005930"
          className="w-full rounded-xl border border-white/15 bg-black/20 px-4 py-3 text-sm text-white outline-none focus:border-primary focus:ring-1 focus:ring-primary"
        />
        <button
          type="submit"
          disabled={generateReport.isPending || isGenerating}
          className="rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-white transition hover:bg-primary/90 disabled:opacity-60"
        >
          {generateReport.isPending || isGenerating ? "생성 중..." : "리포트 생성"}
        </button>
      </form>
      {error ? <p className="text-sm text-rose-300">{error}</p> : null}
      {generateReport.isError ? (
        <p className="text-sm text-rose-300">
          {generateReport.error instanceof Error ? generateReport.error.message : "리포트 생성에 실패했습니다."}
        </p>
      ) : null}
      <p className="text-xs text-slate-400">
        생성된 리포트는 우측 패널에 열리고, 필요하면 PDF/문서로 내보낼 수 있습니다.
      </p>
    </div>
  );
}
