type NewsItem = {
  id: string;
  title: string;
  sentiment: "positive" | "neutral" | "negative";
  source: string;
  publishedAt: string;
  sector: string;
};

const sentimentLabel: Record<NewsItem["sentiment"], string> = {
  positive: "긍정",
  neutral: "중립",
  negative: "부정",
};

const sentimentColor: Record<NewsItem["sentiment"], string> = {
  positive: "text-accent-positive",
  neutral: "text-text-secondaryLight dark:text-text-secondaryDark",
  negative: "text-accent-negative",
};

export function NewsList({ items }: { items: NewsItem[] }) {
  return (
    <div className="rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <h3 className="text-sm font-semibold">주요 뉴스</h3>
      <ul className="mt-3 space-y-3 text-sm">
        {items.map((item) => (
          <li key={item.id} className="rounded-lg border border-border-light/60 p-3 dark:border-border-dark/60">
            <div className="flex items-center justify-between gap-3">
              <h4 className="font-medium">{item.title}</h4>
              <span className={`text-xs font-semibold ${sentimentColor[item.sentiment]}`}>
                {sentimentLabel[item.sentiment]}
              </span>
            </div>
            <p className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              {item.source} · {item.sector} · {item.publishedAt}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
