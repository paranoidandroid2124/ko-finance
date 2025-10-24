
"use client";

import { NewsWindowInsight } from "@/hooks/useCompanySnapshot";

type NewsSignalCardsProps = {
  signals: NewsWindowInsight[];
  companyName?: string | null;
};

const formatNumber = (value?: number | null, fractionDigits = 2) => {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "N/A";
  }
  return value.toFixed(fractionDigits);
};

const scopeLabel = (scope: string, ticker?: string | null, companyName?: string | null) => {
  if (scope === "ticker" && ticker) {
    return companyName ? `${companyName} (${ticker}) 뉴스` : `${ticker} 뉴스`;
  }
  return "시장 전체";
};

export function NewsSignalCards({ signals, companyName }: NewsSignalCardsProps) {
  if (!signals.length) {
    return (
      <section className="rounded-xl border border-dashed border-border-light p-6 text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
        뉴스 시그널이 아직 계산되지 않았습니다. 최근 7~30일 뉴스가 축적되면 자동으로 제공됩니다.
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">뉴스 시그널</h2>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {signals.map((signal) => (
          <article
            key={`${signal.scope}-${signal.ticker ?? "global"}-${signal.windowDays}`}
            className="rounded-lg border border-border-light bg-background-light/70 p-4 text-sm dark:border-border-dark dark:bg-background-dark/60"
          >
            <header className="flex items-baseline justify-between gap-2">
              <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                {scopeLabel(signal.scope, signal.ticker, companyName)}
              </p>
              <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{signal.windowDays}일</span>
            </header>
            <dl className="mt-3 grid grid-cols-2 gap-3 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              <div>
                <dt className="font-semibold uppercase tracking-wide text-[10px]">기사수</dt>
                <dd className="mt-1 text-sm text-text-primaryLight dark:text-text-primaryDark">{signal.articleCount}</dd>
              </div>
              <div>
                <dt className="font-semibold uppercase tracking-wide text-[10px]">평균 감성</dt>
                <dd className="mt-1 text-sm text-text-primaryLight dark:text-text-primaryDark">{formatNumber(signal.avgSentiment)}</dd>
              </div>
              <div>
                <dt className="font-semibold uppercase tracking-wide text-[10px]">감성 Z</dt>
                <dd className="mt-1 text-sm text-text-primaryLight dark:text-text-primaryDark">{formatNumber(signal.sentimentZ)}</dd>
              </div>
              <div>
                <dt className="font-semibold uppercase tracking-wide text-[10px]">새로운 주제</dt>
                <dd className="mt-1 text-sm text-text-primaryLight dark:text-text-primaryDark">{formatNumber(signal.noveltyKl)}</dd>
              </div>
              <div>
                <dt className="font-semibold uppercase tracking-wide text-[10px]">주제 이동</dt>
                <dd className="mt-1 text-sm text-text-primaryLight dark:text-text-primaryDark">{formatNumber(signal.topicShift)}</dd>
              </div>
              <div>
                <dt className="font-semibold uppercase tracking-wide text-[10px]">국내 비중</dt>
                <dd className="mt-1 text-sm text-text-primaryLight dark:text-text-primaryDark">{formatNumber(signal.domesticRatio, 3)}</dd>
              </div>
              <div>
                <dt className="font-semibold uppercase tracking-wide text-[10px]">도메인 다양성</dt>
                <dd className="mt-1 text-sm text-text-primaryLight dark:text-text-primaryDark">{formatNumber(signal.domainDiversity, 3)}</dd>
              </div>
            </dl>
            {signal.topTopics.length ? (
              <div className="mt-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">Top Topics</p>
                <ul className="mt-2 flex flex-wrap gap-2 text-xs text-text-primaryLight dark:text-text-primaryDark">
                  {signal.topTopics.map((topic) => (
                    <li
                      key={`${topic.topic}-${topic.weight}`}
                      className="rounded-full bg-primary/10 px-2 py-1 text-primary dark:bg-primary.dark/15 dark:text-primary.dark"
                    >
                      {topic.topic} · {(topic.weight * 100).toFixed(1)}%
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}
