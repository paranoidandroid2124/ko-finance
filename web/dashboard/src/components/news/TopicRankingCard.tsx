'use client';

type Topic = {
  name: string;
  change: string;
  sentiment: "positive" | "neutral" | "negative";
  topArticleId?: string;
  topArticleTitle?: string;
  topArticleUrl?: string;
  topArticleSource?: string;
  topArticlePublishedAt?: string;
};

const sentimentColor: Record<Topic["sentiment"], string> = {
  positive: "text-accent-positive",
  neutral: "text-text-secondaryLight dark:text-text-secondaryDark",
  negative: "text-accent-negative",
};

const sentimentLabel: Record<Topic["sentiment"], string> = {
  positive: "긍정",
  neutral: "중립",
  negative: "부정",
};

export function TopicRankingCard({ topics }: { topics: Topic[] }) {
  return (
    <div className="rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <h3 className="text-sm font-semibold">핫 토픽</h3>
      <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">선택한 기간 동안 언급이 많았던 키워드</p>
      <ul className="mt-3 space-y-2">
        {topics.map((topic, index) => {
          const hasArticle = Boolean(topic.topArticleUrl);
          return (
            <li
              key={topic.topArticleId ?? topic.name}
              className="rounded-lg border border-border-light/70 px-3 py-2 text-sm transition-colors hover:border-primary hover:bg-white/40 dark:border-border-dark/70 dark:hover:border-primary.dark dark:hover:bg-white/10"
            >
              <button
                type="button"
                onClick={() => hasArticle && window.open(topic.topArticleUrl as string, "_blank", "noopener,noreferrer")}
                className="flex w-full items-start justify-between gap-3 text-left disabled:cursor-not-allowed disabled:opacity-70"
                aria-label={
                  hasArticle
                    ? `${topic.name} 관련 기사 열기`
                    : `${topic.name} 관련 기사 없음`
                }
                disabled={!hasArticle}
              >
                <div className="flex flex-1 items-start gap-3">
                  <span className="text-xs font-semibold text-text-secondaryLight dark:text-text-secondaryDark">{index + 1}</span>
                  <div>
                    <p className="font-medium text-text-primaryLight dark:text-text-primaryDark">{topic.name}</p>
                    {topic.topArticleTitle ? (
                      <p className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                        {topic.topArticleTitle}
                      </p>
                    ) : null}
                    {topic.topArticleSource ? (
                      <p className="text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                        {topic.topArticleSource}
                        {topic.topArticlePublishedAt ? ` · ${topic.topArticlePublishedAt}` : ""}
                      </p>
                    ) : null}
                  </div>
                </div>
                <div className="flex flex-none flex-col items-end gap-1 text-xs">
                  <span className={sentimentColor[topic.sentiment]}>{sentimentLabel[topic.sentiment]}</span>
                  <span className="text-text-secondaryLight dark:text-text-secondaryDark">{topic.change}</span>
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
