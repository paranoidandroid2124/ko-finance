"use client";

import Link from "next/link";
import { FilingHeadline, SummaryBlock } from "@/hooks/useCompanySnapshot";

type CompanySummaryCardProps = {
  name: string;
  ticker?: string | null;
  headline?: FilingHeadline | null;
  summary?: SummaryBlock | null;
};

const summaryOrder: Array<keyof SummaryBlock> = ["insight", "what", "why", "how", "who", "when", "where"];

export function CompanySummaryCard({ name, ticker, headline, summary }: CompanySummaryCardProps) {
  return (
    <section className="rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark">
            {ticker ? `${name} (${ticker})` : name}
          </h1>
          {!ticker ? null : (
            <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              티커 {ticker}
            </p>
          )}
        </div>
        {headline?.viewerUrl ? (
          <Link
            href={headline.viewerUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-md border border-border-light px-3 py-1.5 text-xs font-semibold text-primary transition-colors hover:bg-primary/10 dark:border-border-dark dark:text-primary.dark dark:hover:bg-primary.dark/15"
          >
            DART 바로가기
          </Link>
        ) : null}
      </header>
      <div className="mt-4 space-y-3 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
        {headline ? (
          <div className="rounded-lg border border-border-light bg-background-light/60 px-4 py-3 dark:border-border-dark dark:bg-background-dark/40">
            <p className="font-medium text-text-primaryLight dark:text-text-primaryDark">{headline.title ?? headline.reportName}</p>
            <div className="mt-1 flex flex-wrap gap-3 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              {headline.reportName ? <span>{headline.reportName}</span> : null}
              {headline.filedAt ? <span>{new Date(headline.filedAt).toLocaleString()}</span> : null}
              {headline.receiptNo ? <span>접수번호 {headline.receiptNo}</span> : null}
            </div>
          </div>
        ) : null}
        {summary ? (
          <ul className="space-y-2">
            {summaryOrder
              .map((key) => ({ key, value: summary[key] }))
              .filter((item) => item.value)
              .map((item) => (
                <li key={item.key} className="rounded-lg border border-border-light px-4 py-2 dark:border-border-dark">
                  <p className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">{item.key}</p>
                  <p className="mt-1 text-sm text-text-primaryLight dark:text-text-primaryDark">{item.value}</p>
                </li>
              ))}
          </ul>
        ) : (
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">요약 정보가 아직 준비되지 않았습니다.</p>
        )}
      </div>
    </section>
  );
}
