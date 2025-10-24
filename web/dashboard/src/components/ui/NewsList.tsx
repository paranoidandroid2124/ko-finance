'use client';

type NewsItem = {
  id: string;
  title: string;
  sentiment: "positive" | "neutral" | "negative";
  source?: string;
  publishedAt?: string;
  sector?: string;
  url?: string;
  summary?: string | null;
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

const fallbackSource = "출처 미상";
const fallbackSector = "기타";
const fallbackTimestamp = "시간 정보 없음";

export function NewsList({ items }: { items: NewsItem[] }) {
  return (
    <div className="flex h-full max-h-[calc(100vh-200px)] flex-col rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <h3 className="text-sm font-semibold">주요 뉴스</h3>
      <div className="mt-3 flex-1 overflow-y-auto pr-1">
        <ul className="space-y-3 text-sm">
          {items.map((item) => (
            <li key={item.id} className="space-y-2 rounded-lg border border-border-light/60 p-3 dark:border-border-dark/60">
              <div className="flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() => item.url && window.open(item.url, "_blank", "noopener,noreferrer")}
                  className="text-left font-medium text-text-primaryLight transition hover:text-primary hover:underline dark:text-text-primaryDark"
                >
                  {item.title}
                </button>
                <span className={`text-xs font-semibold ${sentimentColor[item.sentiment]}`}>
                  {sentimentLabel[item.sentiment]}
                </span>
              </div>
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                {(item.source && item.source.trim()) || fallbackSource} · {item.sector ?? fallbackSector} ·{" "}
                {item.publishedAt ?? fallbackTimestamp}
              </p>
              {item.summary ? (
                <p className="text-xs leading-relaxed text-text-secondaryLight dark:text-text-secondaryDark">{item.summary}</p>
              ) : null}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
