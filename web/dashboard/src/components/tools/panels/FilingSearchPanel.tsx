"use client";

import { useEffect, useState } from "react";

import { GenericToolPlaceholder } from "@/components/tools/panels/GenericToolPlaceholder";

type CommanderToolProps = {
  params?: Record<string, unknown>;
  decision?: unknown;
};

type FilingItem = {
  id: string;
  company?: string | null;
  title?: string | null;
  filed_at?: string | null;
  sentiment_label?: string | null;
};

export function FilingSearchPanel({ params }: CommanderToolProps) {
  const ticker = typeof params?.ticker === "string" ? params.ticker.toUpperCase() : undefined;
  const corpCode = typeof params?.corp_code === "string" ? params.corp_code : undefined;
  const days = typeof params?.days === "number" ? Math.max(1, Math.min(params.days, 365)) : 7;
  const [filings, setFilings] = useState<FilingItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ticker && !corpCode) {
      setError("티커 또는 corp_code가 필요합니다.");
      return;
    }
    let mounted = true;
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    const run = async () => {
      try {
        const searchParams = new URLSearchParams();
        if (ticker) searchParams.set("ticker", ticker);
        if (corpCode) searchParams.set("corp_code", corpCode);
        searchParams.set("days", String(days));
        searchParams.set("limit", "20");
        const response = await fetch(`/api/v1/filings?${searchParams.toString()}`, { signal: controller.signal });
        if (!response.ok) {
          const detail = await response.text();
          throw new Error(detail || `HTTP ${response.status}`);
        }
        const payload = (await response.json()) as FilingItem[];
        if (!mounted) return;
        setFilings(Array.isArray(payload) ? payload : []);
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "공시 목록을 불러오지 못했습니다.");
        setFilings([]);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    void run();
    return () => {
      mounted = false;
      controller.abort();
    };
  }, [ticker, corpCode, days]);

  if (!ticker && !corpCode) {
    return <GenericToolPlaceholder title="공시 검색" description="검색 조건이 없습니다." />;
  }
  if (loading) {
    return <GenericToolPlaceholder title="공시 검색" description="불러오는 중입니다..." />;
  }
  if (error) {
    return <GenericToolPlaceholder title="공시 검색" description={error} hint="다른 기간이나 티커로 시도하세요." />;
  }

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-white/5 p-4">
      <div>
        <p className="text-xs uppercase tracking-[0.3em] text-indigo-200">Filing Search</p>
        <p className="mt-1 text-lg font-semibold text-white">
          {ticker ?? corpCode} 최근 {days}일 공시
        </p>
      </div>
      {filings.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/10 bg-white/5 p-4 text-sm text-slate-300">
          조회된 공시가 없습니다.
        </div>
      ) : (
        <ul className="divide-y divide-white/5 rounded-xl border border-white/10">
          {filings.map((filing) => (
            <li key={filing.id} className="px-4 py-3 text-sm text-slate-200">
              <div className="flex items-center justify-between gap-3">
                <div className="flex flex-col gap-1">
                  <p className="font-semibold text-white">{filing.title ?? "제목 없음"}</p>
                  <p className="text-xs text-slate-400">
                    {filing.company ?? ticker ?? corpCode} ·{" "}
                    {filing.filed_at ? new Date(filing.filed_at).toLocaleDateString("ko-KR") : "날짜 없음"}
                  </p>
                </div>
                {filing.sentiment_label ? (
                  <span className="rounded-full bg-white/10 px-3 py-1 text-[11px] uppercase text-indigo-100">
                    {filing.sentiment_label}
                  </span>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
