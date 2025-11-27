"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Calendar, Filter, RefreshCcw, Search } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { Card } from "@/components/ui/Card";
import { FilingsTable } from "@/components/filings/FilingsTable";
import { FilingDetailPanel } from "@/components/filings/FilingDetailPanel";
import { type FilingListItem, useFilingDetail, useFilings, type FilingSentimentFilter } from "@/hooks/useFilings";

type DateInputEvent = React.ChangeEvent<HTMLInputElement>;

function buildParams(
  ticker: string,
  startDate: string,
  endDate: string,
  sentiment: FilingSentimentFilter,
  page: number,
  limit: number,
) {
  const skip = (page - 1) * limit;
  return {
    ticker: ticker.trim() || undefined,
    startDate: startDate || undefined,
    endDate: endDate || undefined,
    sentiment: sentiment === "all" ? undefined : sentiment,
    limit,
    skip,
    days: !startDate && !endDate ? 30 : undefined,
  };
}

export default function FilingsArchivePage() {
  const [ticker, setTicker] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [sentiment, setSentiment] = useState<FilingSentimentFilter>("all");
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(50);
  const [selectedId, setSelectedId] = useState<string | undefined>(undefined);

  const params = useMemo(
    () => buildParams(ticker, startDate, endDate, sentiment, page, limit),
    [ticker, startDate, endDate, sentiment, page, limit],
  );

  const { data, isLoading, refetch, isFetching } = useFilings(params);
  const filings: FilingListItem[] = data ?? [];

  const { data: selectedDetail } = useFilingDetail(selectedId);

  useEffect(() => {
    setPage(1);
  }, [ticker, startDate, endDate, sentiment, limit]);

  const hasFilters = Boolean(ticker || startDate || endDate || sentiment !== "all");

  const handleReset = () => {
    setTicker("");
    setStartDate("");
    setEndDate("");
    setSentiment("all");
    setPage(1);
  };

  const totalLabel = `페이지 ${page} · ${limit}건 씩`;

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl space-y-6 px-4 py-8">
        <header className="flex flex-col gap-3">
          <div className="inline-flex items-center gap-2 text-xs text-text-secondary">
            <Link
              href="/insights"
              className="inline-flex items-center gap-1 rounded-full border border-border-light px-2.5 py-1 transition hover:border-primary hover:text-primary"
            >
              <ArrowLeft className="h-4 w-4" />
              인사이트 허브로 돌아가기
            </Link>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full border border-border-light bg-surface-1/80 px-3 py-1 text-xs font-semibold text-text-secondary">
            <Filter className="h-3.5 w-3.5" />
            공시 아카이브
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-text-primary">전체 공시 탐색</h1>
            <p className="text-sm text-text-secondary">
              날짜, 티커, 감성 필터로 전 기간 공시를 조회합니다. 한 번에 최대 500건까지 로드됩니다.
            </p>
          </div>
        </header>

        <Card variant="glass" padding="md" className="rounded-2xl shadow-lg">
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-semibold text-text-secondary">티커/회사</label>
              <div className="flex items-center gap-2 rounded-xl border border-border-light bg-surface-2 px-3 py-2 text-sm text-text-primary">
                <Search className="h-4 w-4 text-text-tertiary" />
                <input
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value)}
                  placeholder="005930 또는 삼성전자"
                  className="w-40 bg-transparent outline-none"
                />
              </div>
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-xs font-semibold text-text-secondary">시작일</label>
              <div className="flex items-center gap-2 rounded-xl border border-border-light bg-surface-2 px-3 py-2 text-sm text-text-primary">
                <Calendar className="h-4 w-4 text-text-tertiary" />
                <input
                  type="date"
                  value={startDate}
                  onChange={(e: DateInputEvent) => setStartDate(e.target.value)}
                  className="bg-transparent outline-none"
                />
              </div>
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-xs font-semibold text-text-secondary">종료일</label>
              <div className="flex items-center gap-2 rounded-xl border border-border-light bg-surface-2 px-3 py-2 text-sm text-text-primary">
                <Calendar className="h-4 w-4 text-text-tertiary" />
                <input
                  type="date"
                  value={endDate}
                  onChange={(e: DateInputEvent) => setEndDate(e.target.value)}
                  className="bg-transparent outline-none"
                />
              </div>
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-xs font-semibold text-text-secondary">감성</label>
              <select
                value={sentiment}
                onChange={(e) => setSentiment(e.target.value as FilingSentimentFilter)}
                className="rounded-xl border border-border-light bg-surface-2 px-3 py-2 text-sm text-text-primary outline-none"
              >
                <option value="all">전체</option>
                <option value="positive">긍정</option>
                <option value="negative">부정</option>
                <option value="neutral">중립</option>
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-xs font-semibold text-text-secondary">페이지당</label>
              <select
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="rounded-xl border border-border-light bg-surface-2 px-3 py-2 text-sm text-text-primary outline-none"
              >
                {[25, 50, 100, 200, 500].map((value) => (
                  <option key={value} value={value}>
                    {value}건
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-1 items-center justify-end gap-2">
              {hasFilters && (
                <button
                  type="button"
                  onClick={handleReset}
                  className="inline-flex items-center gap-2 rounded-lg border border-border-light px-3 py-2 text-xs font-semibold text-text-secondary hover:border-primary hover:text-primary"
                >
                  <RefreshCcw className="h-4 w-4" />
                  초기화
                </button>
              )}
              <button
                type="button"
                onClick={() => refetch()}
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-primary/90"
                disabled={isFetching}
              >
                {isFetching ? "불러오는 중..." : "적용"}
              </button>
            </div>
          </div>
        </Card>

        <Card variant="glass" padding="md" className="rounded-2xl shadow-lg">
          <div className="mb-4 flex items-center justify-between text-sm text-text-secondary">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-text-primary">조회 결과</span>
              <span>{totalLabel}</span>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="rounded-lg border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondary hover:border-primary hover:text-primary disabled:opacity-50"
                disabled={page <= 1 || isFetching}
                onClick={() => setPage((prev) => Math.max(1, prev - 1))}
              >
                이전
              </button>
              <button
                type="button"
                className="rounded-lg border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondary hover:border-primary hover:text-primary disabled:opacity-50"
                disabled={filings.length < limit || isFetching}
                onClick={() => setPage((prev) => prev + 1)}
              >
                다음
              </button>
            </div>
          </div>

          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, idx) => (
                <div key={idx} className="h-20 rounded-2xl bg-surface-2 animate-pulse" />
              ))}
            </div>
          ) : filings.length ? (
            <FilingsTable filings={filings} selectedId={selectedId} onSelect={setSelectedId} />
          ) : (
            <div className="rounded-2xl border border-dashed border-border-light bg-surface-2/50 p-6 text-sm text-text-secondary">
              <p className="font-semibold text-text-primary">조건에 맞는 공시가 없습니다.</p>
              <p className="mt-1">필터를 줄이거나 기간을 넓혀 다시 조회해 주세요.</p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <button
                  type="button"
                  className="rounded-lg border border-border-light px-3 py-1 text-text-secondary hover:border-primary hover:text-primary"
                  onClick={() => {
                    setStartDate("");
                    setEndDate("");
                    setTicker("");
                    setSentiment("all");
                    setPage(1);
                    void refetch();
                  }}
                >
                  필터 초기화
                </button>
              </div>
            </div>
          )}
        </Card>

        {selectedId && selectedDetail && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            onClick={() => setSelectedId(undefined)}
          >
            <div className="w-full max-w-2xl px-4" onClick={(e) => e.stopPropagation()}>
              <FilingDetailPanel filing={selectedDetail} />
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
