"use client";

import clsx from "clsx";
import { CalendarDays, Newspaper, Radar, Sparkles, TrendingUp } from "lucide-react";

type Trend = "up" | "down" | "flat";
type StatusTone = "positive" | "negative" | "neutral";

export type DigestNewsItem = {
  headline: string;
  summary?: string;
  source?: string;
  link?: string;
};

export type DigestWatchlistItem = {
  title: string;
  description: string;
  changeLabel?: string;
  tone: StatusTone | "alert";
};

export type DigestIndicator = {
  name: string;
  value: string;
  status: StatusTone;
};

export type DigestSentimentBlock = {
  summary: string;
  scoreLabel?: string;
  trend: Trend;
  indicators: DigestIndicator[];
};

export type DigestActionItem = {
  title: string;
  note: string;
  tone?: StatusTone;
};

export type DigestPayload = {
  timeframe: "daily" | "weekly";
  periodLabel: string;
  generatedAtLabel: string;
  sourceLabel?: string;
  news: DigestNewsItem[];
  watchlist: DigestWatchlistItem[];
  sentiment: DigestSentimentBlock | null;
  actions: DigestActionItem[];
  llmOverview?: string;
  llmPersonalNote?: string;
};

type DigestCardProps = {
  data: DigestPayload;
  isEmpty?: boolean;
};

const toneClass: Record<StatusTone | "alert", string> = {
  positive: "bg-accent-positive/10 text-accent-positive border-accent-positive/40",
  negative: "bg-accent-negative/10 text-accent-negative border-accent-negative/40",
  neutral: "bg-border-light/50 text-text-secondaryLight border-border-light/80 dark:text-text-secondaryDark dark:bg-border-dark/40 dark:border-border-dark/80",
  alert: "bg-accent-warning/15 text-accent-warning border-accent-warning/40",
};

const trendLabel: Record<Trend, string> = {
  up: "상승 추세",
  down: "하락 추세",
  flat: "변동 없음",
};

export function DigestCard({ data, isEmpty }: DigestCardProps) {
  const { timeframe, periodLabel, generatedAtLabel, sourceLabel, llmOverview, llmPersonalNote } = data;

  const sectionHeading = (index: number, icon: React.ReactNode, title: string) => (
    <div className="flex items-center gap-3">
      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary dark:bg-primary.dark/15 dark:text-primary.dark">
        {index.toString().padStart(2, "0")}
      </span>
      <div className="flex items-center gap-2 text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">
        {icon}
        <span>{title}</span>
      </div>
    </div>
  );

  return (
    <div className="rounded-3xl border border-border-light bg-gradient-to-b from-background-body via-white to-background-body p-6 shadow-lg transition-colors dark:border-border-dark dark:from-background-body.dark/90 dark:via-background-cardDark/90 dark:to-background-body.dark/95">
      <header className="space-y-2 text-center">
        <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-4 py-1 text-xs font-semibold uppercase tracking-wide text-primary dark:bg-primary.dark/15 dark:text-primary.dark">
          <CalendarDays className="h-4 w-4" />
          {timeframe === "daily" ? "Daily Digest" : "Weekly Digest"}
        </div>
        <h2 className="text-2xl font-semibold text-text-primaryLight dark:text-text-primaryDark">K-Finance Digest</h2>
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">{periodLabel}</p>
      </header>

      <main className="mt-8 space-y-6">
        {llmOverview && (
          <section className="rounded-2xl border border-primary/20 bg-primary/5 p-5 shadow-sm transition-colors dark:border-primary.dark/25 dark:bg-primary.dark/10">
            <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-primary dark:text-primary.dark">
              <Sparkles className="h-4 w-4" />
              LLM Insight
            </div>
            <div className="mt-3 space-y-2 text-sm leading-relaxed text-text-primaryLight dark:text-text-primaryDark">
              {llmOverview.split(/\r?\n/).map((line, idx) => (
                <p key={idx}>{line}</p>
              ))}
            </div>
          </section>
        )}
        {llmPersonalNote && (
          <section className="rounded-2xl border border-border-light/70 bg-background-cardLight p-5 shadow-sm transition-colors dark:border-border-dark/70 dark:bg-background-cardDark/90">
            <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
              <Radar className="h-4 w-4" />
              Personal Note
            </div>
            <div className="mt-3 space-y-2 text-sm leading-relaxed text-text-primaryLight dark:text-text-primaryDark">
              {llmPersonalNote.split(/\r?\n/).map((line, idx) => (
                <p key={`personal-${idx}`}>{line}</p>
              ))}
            </div>
          </section>
        )}
        <section className="rounded-2xl border border-border-light/60 bg-background-cardLight p-5 shadow-sm transition-colors dark:border-border-dark/60 dark:bg-background-cardDark/90">
          {sectionHeading(1, <Newspaper className="h-5 w-5 text-primary" />, "주요 뉴스 하이라이트")}
          <div className="mt-4 space-y-3">
            {isEmpty || data.news.length === 0 ? (
              <p className="rounded-xl border border-dashed border-border-light px-4 py-5 text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
                아직 요약할 뉴스가 모이지 않았습니다.
              </p>
            ) : (
              data.news.map((item, idx) => (
                <div
                  key={`${item.headline}-${idx}`}
                  className="rounded-xl border border-border-light/60 bg-white/75 px-4 py-3 text-sm shadow-inner transition-colors dark:border-border-dark/60 dark:bg-background-cardDark/80"
                >
                  <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{item.headline}</p>
                  {item.summary && (
                    <p className="mt-1 text-text-secondaryLight dark:text-text-secondaryDark">{item.summary}</p>
                  )}
                  <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                    {item.source && <span className="font-medium">{item.source}</span>}
                    {item.link && (
                      <a
                        href={item.link}
                        className="text-primary hover:underline dark:text-primary.dark"
                        target="_blank"
                        rel="noreferrer"
                      >
                        자세히 보기
                      </a>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-border-light/60 bg-background-cardLight p-5 shadow-sm transition-colors dark:border-border-dark/60 dark:bg-background-cardDark/90">
          {sectionHeading(2, <Radar className="h-5 w-5 text-primary" />, "워치리스트 변화")}
          <ul className="mt-4 space-y-3">
            {isEmpty || data.watchlist.length === 0 ? (
              <li className="rounded-xl border border-dashed border-border-light px-4 py-5 text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
                최근 24시간 동안 알림이 발생하지 않았습니다.
              </li>
            ) : (
              data.watchlist.map((item, idx) => (
                <li
                  key={`${item.title}-${idx}`}
                  className="flex flex-col gap-2 rounded-xl border border-border-light/60 bg-white/75 px-4 py-3 text-sm shadow-inner transition-colors dark:border-border-dark/60 dark:bg-background-cardDark/80"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{item.title}</div>
                    {item.changeLabel && (
                      <span className={clsx("rounded-full border px-3 py-1 text-xs font-medium", toneClass[item.tone])}>
                        {item.changeLabel}
                      </span>
                    )}
                  </div>
                  <p className="text-text-secondaryLight dark:text-text-secondaryDark">{item.description}</p>
                </li>
              ))
            )}
          </ul>
        </section>

        <section className="rounded-2xl border border-border-light/60 bg-background-cardLight p-5 shadow-sm transition-colors dark:border-border-dark/60 dark:bg-background-cardDark/90">
          {sectionHeading(3, <TrendingUp className="h-5 w-5 text-primary" />, "감성 & 지표")}
          {isEmpty || !data.sentiment ? (
            <p className="mt-4 rounded-xl border border-dashed border-border-light px-4 py-5 text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
              분석에 필요한 신호가 아직 수집되지 않았습니다.
            </p>
          ) : (
            <div className="mt-4 space-y-4">
              <div className="rounded-xl border border-border-light/60 bg-white/80 px-4 py-3 text-sm shadow-inner transition-colors dark:border-border-dark/60 dark:bg-background-cardDark/85">
                <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{data.sentiment.summary}</p>
                <div className="mt-2 flex flex-wrap gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  {data.sentiment.scoreLabel && (
                    <span className="rounded-full bg-primary/10 px-3 py-1 font-semibold text-primary dark:bg-primary.dark/15 dark:text-primary.dark">
                      점수 {data.sentiment.scoreLabel}
                    </span>
                  )}
                  <span className="rounded-full bg-border-light/60 px-3 py-1 font-medium text-text-secondaryLight dark:bg-border-dark/60 dark:text-text-secondaryDark">
                    {trendLabel[data.sentiment.trend]}
                  </span>
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                {data.sentiment.indicators.map((indicator) => (
                  <div
                    key={indicator.name}
                    className={clsx(
                      "rounded-xl border px-4 py-3 text-sm transition-colors",
                      toneClass[indicator.status]
                    )}
                  >
                    <p className="text-xs font-semibold uppercase tracking-wide">{indicator.name}</p>
                    <p className="mt-1 text-base font-semibold">{indicator.value}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-border-light/60 bg-background-cardLight p-5 shadow-sm transition-colors dark:border-border-dark/60 dark:bg-background-cardDark/90">
          {sectionHeading(4, <Sparkles className="h-5 w-5 text-primary" />, "맞춤 액션")}
          <ul className="mt-4 space-y-3">
            {isEmpty || data.actions.length === 0 ? (
              <li className="rounded-xl border border-dashed border-border-light px-4 py-5 text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
                추천할 신규 액션이 아직 없습니다. 워치리스트를 업데이트해 주세요.
              </li>
            ) : (
              data.actions.map((action, idx) => (
                <li
                  key={`${action.title}-${idx}`}
                  className="rounded-xl border border-border-light/60 bg-white/80 px-4 py-3 text-sm shadow-inner transition-colors dark:border-border-dark/60 dark:bg-background-cardDark/85"
                >
                  <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{action.title}</p>
                  <p className="mt-1 text-text-secondaryLight dark:text-text-secondaryDark">{action.note}</p>
                  {action.tone && (
                    <span className={clsx("mt-2 inline-block rounded-full border px-3 py-1 text-xs font-medium", toneClass[action.tone])}>
                      {action.tone === "positive" ? "긍정" : action.tone === "negative" ? "주의" : "중립"}
                    </span>
                  )}
                </li>
              ))
            )}
          </ul>
        </section>
      </main>

      <footer className="mt-8 rounded-2xl bg-border-light/30 px-5 py-4 text-xs text-text-secondaryLight shadow-inner transition-colors dark:bg-border-dark/35 dark:text-text-secondaryDark">
        <p>
          {generatedAtLabel}
          {sourceLabel ? ` · ${sourceLabel}` : ""}
        </p>
        <p className="mt-1 text-[11px] leading-relaxed text-text-tertiaryLight dark:text-text-tertiaryDark">
          이 다이제스트는 K-Finance Copilot이 수집한 공시·뉴스·시장 지표를 바탕으로 자동 생성되었습니다. 링크된
          데이터는 최신 정보를 기준으로 하며, 투자 결정은 사용자 책임입니다.
        </p>
      </footer>
    </div>
  );
}
