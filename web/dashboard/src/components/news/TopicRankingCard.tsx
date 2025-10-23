type Topic = {
  name: string;
  change: string;
  sentiment: "positive" | "neutral" | "negative";
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
        {topics.map((topic, index) => (
          <li
            key={topic.name}
            className="flex items-center justify-between rounded-lg border border-border-light/70 px-3 py-2 text-sm dark:border-border-dark/70"
          >
            <div className="flex items-center gap-3">
              <span className="text-xs font-semibold text-text-secondaryLight dark:text-text-secondaryDark">{index + 1}</span>
              <span className="font-medium">{topic.name}</span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className={sentimentColor[topic.sentiment]}>{sentimentLabel[topic.sentiment]}</span>
              <span className="text-text-secondaryLight dark:text-text-secondaryDark">{topic.change}</span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
