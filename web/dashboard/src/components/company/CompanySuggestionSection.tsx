"use client";

import Link from "next/link";
import type { Route } from "next";
import type { CompanySearchResult } from "@/hooks/useCompanySearch";

type CompanySuggestionSectionProps = {
  title: string;
  description?: string;
  items: CompanySearchResult[];
};

const buildHref = (item: CompanySearchResult): Route | undefined => {
  if (item.ticker) {
    return `/company/${encodeURIComponent(item.ticker)}` as Route;
  }
  if (item.corpCode) {
    return `/company/${encodeURIComponent(item.corpCode)}` as Route;
  }
  return undefined;
};

export function CompanySuggestionSection({ title, description, items }: CompanySuggestionSectionProps) {
  if (!items.length) {
    return null;
  }

  return (
    <section className="rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <header className="flex flex-col gap-1">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
          {title}
        </h2>
        {description ? (
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{description}</p>
        ) : null}
      </header>
      <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => {
          const href = buildHref(item);
          const key = item.corpCode ?? item.ticker ?? item.corpName ?? "";
          const content = (
            <>
              <span className="text-sm font-semibold text-text-primaryLight transition-colors group-hover:text-primary dark:text-text-primaryDark dark:group-hover:text-primary.dark">
                {item.corpName ?? item.ticker ?? item.corpCode ?? "기업 정보를 찾을 수 없어요"}
              </span>
              <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                {item.ticker ? `티커 ${item.ticker}` : null}
                {item.ticker && item.corpCode ? " · " : ""}
                {item.corpCode ? `법인등록번호 ${item.corpCode}` : null}
              </span>
              {item.highlight ? (
                <span className="text-xs text-primary/80 dark:text-primary.dark/80">{item.highlight}</span>
              ) : item.latestReportName ? (
                <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  {item.latestReportName}
                </span>
              ) : null}
            </>
          );

          if (href) {
            return (
              <Link
                key={key}
                href={href}
                className="group flex flex-col gap-1 rounded-lg border border-border-light bg-background-light/60 px-4 py-3 text-sm transition-colors hover:border-primary hover:bg-primary/10 dark:border-border-dark dark:bg-background-dark/60 dark:hover:border-primary.dark dark:hover:bg-primary.dark/15"
              >
                {content}
              </Link>
            );
          }

          return (
            <div
              key={key}
              className="group flex flex-col gap-1 rounded-lg border border-border-light bg-background-light/60 px-4 py-3 text-sm transition-colors dark:border-border-dark dark:bg-background-dark/60"
            >
              {content}
            </div>
          );
        })}
      </div>
    </section>
  );
}
