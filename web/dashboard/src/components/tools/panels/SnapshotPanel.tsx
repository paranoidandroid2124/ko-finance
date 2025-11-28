"use client";

import { useEffect, useState } from "react";

import { GenericToolPlaceholder } from "@/components/tools/panels/GenericToolPlaceholder";

type CommanderToolProps = {
  params?: Record<string, unknown>;
  decision?: unknown;
};

type KeyMetric = { label?: string; value?: string | number | null };
type FilingItem = { id?: string | number; corp_name?: string | null; title?: string | null; filed_at?: string | null };
type SnapshotResponse = {
  corp_name?: string | null;
  ticker?: string | null;
  summary?: { overview?: string | null };
  key_metrics?: KeyMetric[];
  recent_filings?: FilingItem[];
};

export function SnapshotPanel({ params }: CommanderToolProps) {
  const identifier = typeof params?.ticker === "string" ? params.ticker : typeof params?.corp_code === "string" ? params.corp_code : "";
  const [snapshot, setSnapshot] = useState<SnapshotResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!identifier) {
      setError("티커 또는 corp_code가 필요합니다.");
      return;
    }
    let mounted = true;
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    const run = async () => {
      try {
        const response = await fetch(`/api/v1/companies/${encodeURIComponent(identifier)}/snapshot`, {
          method: "GET",
          signal: controller.signal,
        });
        if (!response.ok) {
          const detail = await response.text();
          throw new Error(detail || `HTTP ${response.status}`);
        }
        const payload = (await response.json()) as SnapshotResponse;
        if (!mounted) return;
        setSnapshot(payload);
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "스냅샷을 불러오지 못했습니다.");
        setSnapshot(null);
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
  }, [identifier]);

  if (!identifier) {
    return <GenericToolPlaceholder title="기업 스냅샷" description="요청에 티커/법인코드가 없습니다." />;
  }
  if (loading) {
    return <GenericToolPlaceholder title="기업 스냅샷" description="불러오는 중입니다..." />;
  }
  if (error) {
    return <GenericToolPlaceholder title="기업 스냅샷" description={error} hint="입력값을 확인하고 다시 시도하세요." />;
  }
  if (!snapshot) {
    return <GenericToolPlaceholder title="기업 스냅샷" description="스냅샷 데이터를 찾지 못했습니다." />;
  }

  const metrics = Array.isArray(snapshot.key_metrics) ? snapshot.key_metrics : [];
  const filings = Array.isArray(snapshot.recent_filings) ? snapshot.recent_filings : [];

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
        <p className="text-xs uppercase tracking-[0.4em] text-indigo-200">Company Snapshot</p>
        <p className="mt-2 text-lg font-semibold text-white">{snapshot.corp_name ?? snapshot.ticker ?? identifier}</p>
        <p className="mt-1 text-sm text-slate-300">{snapshot.summary?.overview ?? "요약 정보가 없습니다."}</p>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        {metrics.length ? (
          metrics.slice(0, 6).map((metric, idx) => (
            <div key={`${metric.label ?? idx}`} className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <p className="text-xs uppercase tracking-[0.25em] text-indigo-200">{metric.label ?? "지표"}</p>
              <p className="mt-2 text-xl font-semibold text-white">{metric.value ?? "N/A"}</p>
            </div>
          ))
        ) : (
          <div className="md:col-span-3 rounded-2xl border border-dashed border-white/10 bg-white/5 p-4 text-sm text-slate-300">
            핵심 지표가 없습니다.
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-white/10 bg-white/5">
        <div className="border-b border-white/10 px-4 py-3 text-xs uppercase tracking-[0.2em] text-indigo-200">최근 공시</div>
        {filings.length ? (
          <ul className="divide-y divide-white/5">
            {filings.slice(0, 5).map((filing) => (
              <li key={String(filing.id ?? filing.title ?? Math.random())} className="px-4 py-3 text-sm text-slate-200">
                <div className="font-semibold text-white">{filing.title ?? "제목 없음"}</div>
                <div className="mt-1 text-xs text-slate-400">
                  {filing.corp_name ?? snapshot.corp_name ?? ""} ·{" "}
                  {filing.filed_at ? new Date(filing.filed_at).toLocaleDateString("ko-KR") : "날짜 없음"}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="px-4 py-6 text-sm text-slate-300">표시할 최근 공시가 없습니다.</div>
        )}
      </div>
    </div>
  );
}
