"use client";

import classNames from "classnames";

type NewsItem = {
  title?: string;
  summary?: string;
  source?: string;
  sentiment?: string;
  publishedAt?: string;
  url?: string;
};

type NewsCardsWidgetProps = {
  title?: string;
  description?: string;
  items: Record<string, unknown>[];
};

const sentimentTone: Record<string, string> = {
  positive: "bg-emerald-500/10 text-emerald-200 border-emerald-400/40",
  negative: "bg-rose-500/10 text-rose-200 border-rose-400/40",
  neutral: "bg-slate-600/20 text-slate-200 border-slate-500/40",
};

const formatPublishedAt = (value?: string | null) => {
  if (!value) {
    return "";
  }
  try {
    return new Date(value).toLocaleString("ko-KR", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return value;
  }
};

export default function NewsCardsWidget({ title, description, items }: NewsCardsWidgetProps) {
  const normalized = items
    .filter((item): item is NewsItem => typeof item === "object" && item !== null)
    .slice(0, 3);

  if (!normalized.length) {
    return <p className="text-xs text-slate-400">표시할 뉴스 데이터가 없습니다.</p>;
  }

  return (
    <div className="space-y-3">
      {title ? <p className="text-xs font-semibold uppercase tracking-[0.3em] text-indigo-200">{title}</p> : null}
      {description ? <p className="text-xs text-slate-400">{description}</p> : null}
      <div className="grid gap-3">
        {normalized.map((item, index) => (
          <div key={`${item.title ?? index}`} className="rounded-2xl border border-white/5 bg-slate-900/60 p-3">
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span>{item.source ?? "출처 미상"}</span>
              <span>{formatPublishedAt(item.publishedAt)}</span>
            </div>
            <p className="mt-2 text-sm font-semibold text-white">{item.title ?? "제목 없음"}</p>
            <p className="mt-1 text-sm text-slate-300">{item.summary ?? "요약이 제공되지 않았습니다."}</p>
            <div className="mt-3 flex items-center justify-between text-xs">
              {item.sentiment ? (
                <span
                  className={classNames(
                    "rounded-full border px-3 py-0.5 font-semibold uppercase",
                    sentimentTone[item.sentiment] ?? sentimentTone.neutral,
                  )}
                >
                  {item.sentiment === "positive" ? "긍정" : item.sentiment === "negative" ? "부정" : "중립"}
                </span>
              ) : (
                <span className="rounded-full border border-white/10 px-3 py-0.5 text-slate-300">Sentiment N/A</span>
              )}
              {item.url ? (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-full border border-white/20 px-3 py-0.5 text-xs text-cyan-200 transition hover:border-cyan-300 hover:text-white"
                >
                  원문 보기 ↗
                </a>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
