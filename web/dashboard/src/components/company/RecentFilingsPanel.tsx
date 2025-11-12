"use client";

import { useEffect, useMemo, useState } from "react";
import { CompanyFilingSummary, SummaryBlock } from "@/hooks/useCompanySnapshot";
import { formatKoreanDateTime } from "@/lib/datetime";

type RecentFilingsPanelProps = {
  filings: CompanyFilingSummary[];
  companyName: string;
};

const summaryKeys: Array<keyof SummaryBlock> = ["insight", "what", "why", "how", "who", "when", "where"];

const sentimentStyles: Record<string, string> = {
  positive: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300",
  negative: "bg-rose-500/15 text-rose-600 dark:text-rose-300",
  neutral: "bg-slate-500/15 text-slate-600 dark:text-slate-300",
};

export function RecentFilingsPanel({ filings, companyName }: RecentFilingsPanelProps) {
  const [selectedId, setSelectedId] = useState<string | null>(filings[0]?.id ?? null);

  useEffect(() => {
    if (!filings.length) {
      setSelectedId(null);
      return;
    }
    setSelectedId((current) => {
      if (current && filings.some((filing) => filing.id === current)) {
        return current;
      }
      return filings[0].id;
    });
  }, [filings]);

  const selected = useMemo(
    () => filings.find((filing) => filing.id === selectedId) ?? null,
    [filings, selectedId]
  );

  if (!filings.length) {
    return (
      <section className="rounded-xl border border-dashed border-border-light p-6 text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
        최근 30일 내 제출된 공시가 없습니다.
      </section>
    );
  }

  return (
    <section className="grid gap-4 lg:grid-cols-[minmax(0,280px)_minmax(0,1fr)]">
      <div className="rounded-xl border border-border-light bg-background-cardLight dark:border-border-dark dark:bg-background-cardDark">
        <h3 className="border-b border-border-light px-4 py-3 text-sm font-semibold dark:border-border-dark">최근 공시</h3>
        <div className="max-h-[420px] space-y-1 overflow-y-auto px-2 py-2">
          {filings.map((filing) => {
            const filedAt = filing.filedAt ? formatKoreanDateTime(filing.filedAt) : "제출 시각 미상";
            const sentimentLabel = filing.sentiment?.toLowerCase() ?? "neutral";
            return (
              <button
                key={filing.id}
                type="button"
                onClick={() => setSelectedId(filing.id)}
                className={`w-full rounded-lg border px-4 py-3 text-left text-sm transition-colors ${
                  selectedId === filing.id
                    ? "border-primary bg-primary/10 text-text-primaryLight dark:bg-primary.dark/20"
                    : "border-transparent bg-transparent text-text-secondaryLight hover:border-border-light hover:bg-background-light/60 dark:hover:border-border-dark dark:hover:bg-background-dark/50"
                }`}
              >
                <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                  {filing.reportName ?? filing.title ?? "공시"}
                </p>
                <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{filedAt}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                  {filing.category ? <span className="rounded-full bg-background-light/70 px-2 py-0.5 dark:bg-background-dark/40">{filing.category}</span> : null}
                  <span className={`rounded-full px-2 py-0.5 ${sentimentStyles[sentimentLabel] ?? sentimentStyles.neutral}`}>
                    {sentimentLabel === "positive" ? "긍정" : sentimentLabel === "negative" ? "부정" : "중립"}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
        {selected ? (
          <>
            <header className="space-y-2">
              <div>
                <p className="text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">공시 요약</p>
                <h3 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">
                  {companyName} · {selected.reportName ?? selected.title ?? "공시"}
                </h3>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                {selected.filedAt ? <span>{formatKoreanDateTime(selected.filedAt)}</span> : null}
                {selected.receiptNo ? <span>접수번호 {selected.receiptNo}</span> : null}
              </div>
              {selected.viewerUrl ? (
                <a
                  href={selected.viewerUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center text-xs font-semibold text-primary hover:underline"
                >
                  DART 원문 보기
                </a>
              ) : null}
            </header>
            <div className="mt-4 space-y-3 text-sm">
              {selected.summary ? (
                summaryKeys
                  .map((key) => ({ key, value: selected.summary?.[key] }))
                  .filter((item) => item.value)
                  .map((item) => (
                    <div key={item.key} className="rounded-lg border border-border-light px-4 py-3 text-sm dark:border-border-dark">
                      <p className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">{item.key}</p>
                      <p className="mt-1 text-text-primaryLight dark:text-text-primaryDark">{item.value}</p>
                    </div>
                  ))
              ) : (
                <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">요약 정보가 아직 준비되지 않았습니다.</p>
              )}
            </div>
          </>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            표시할 공시를 선택해 주세요.
          </div>
        )}
      </div>
    </section>
  );
}
