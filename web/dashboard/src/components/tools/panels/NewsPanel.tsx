"use client";

import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";

import SpotlightCard from "@/components/ui/SpotlightCard";
import type { CommanderRouteDecision } from "@/lib/chatApi";
import { useToolStore } from "@/store/toolStore";

type NewsPanelProps = {
  params?: Record<string, unknown>;
  decision?: CommanderRouteDecision | null;
};

type NewsItem = {
  id?: string | null;
  title?: string | null;
  summary: string;
  sentiment?: string | null;
  sentimentScore?: number | null;
  source?: string | null;
  publishedAt?: string | null;
  url?: string | null;
};

const sentimentTone: Record<string, string> = {
  positive: "border-emerald-400/40 bg-emerald-500/10 text-emerald-200",
  negative: "border-rose-400/40 bg-rose-500/10 text-rose-200",
  neutral: "border-slate-500/30 bg-white/5 text-slate-200",
};

const formatPublishedAt = (value?: string | null) => {
  if (!value) {
    return "발행일 미상";
  }
  try {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return date.toLocaleString("ko-KR", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return value;
  }
};

export function NewsPanel({ params, decision }: NewsPanelProps) {
  const query =
    typeof params?.query === "string" && params.query.trim()
      ? params.query.trim()
      : typeof decision?.metadata?.question === "string" && decision.metadata.question.trim()
        ? decision.metadata.question.trim()
        : "";
  const ticker = typeof params?.ticker === "string" && params.ticker.trim() ? params.ticker.trim() : undefined;
  const limit = typeof params?.limit === "number" ? Math.min(Math.max(params.limit, 1), 20) : 6;

  const [items, setItems] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const sessionId = useToolStore((state) => state.entry?.sessionId ?? null);
  const registerToolContext = useToolStore((state) => state.registerToolContext);
  const publishToolSnapshot = useToolStore((state) => state.publishToolSnapshot);

  useEffect(() => {
    if (!query) {
      setItems([]);
      setError("질문이 필요합니다. 다시 시도해 주세요.");
      setLoading(false);
      return;
    }
    let mounted = true;
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    const fetchNews = async () => {
      try {
        const response = await fetch("/api/v1/tools/news-rag", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query, ticker, limit }),
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const payload = (await response.json()) as { items?: NewsItem[]; llm_summary?: string };
        if (!mounted) {
          return;
        }
        const items = Array.isArray(payload.items) ? payload.items : [];
        setItems(items);
        if (payload.llm_summary) {
          registerToolContext(sessionId, payload.llm_summary);
        }
        publishToolSnapshot({
          sessionId,
          summary: `${ticker} 관련 최신 뉴스 카드가 준비되었습니다.`,
          attachments: [
            {
              type: "news_cards",
              title: `${ticker} Top 뉴스`,
              data: { items },
            },
          ],
        });
      } catch (fetchError) {
        if (!mounted) {
          return;
        }
        setError(fetchError instanceof Error ? fetchError.message : "뉴스를 불러오지 못했습니다.");
        setItems([]);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };
    void fetchNews();

    return () => {
      mounted = false;
      controller.abort();
    };
  }, [query, ticker, limit, registerToolContext, sessionId, publishToolSnapshot]);

  const skeletonCards = useMemo(() => Array.from({ length: 3 }).map((_, idx) => <SkeletonCard key={idx} />), []);

  if (!query) {
    return (
      <div className="flex h-full items-center justify-center rounded-3xl border border-white/10 bg-white/5 text-sm text-slate-300">
        분석할 질문이 필요합니다. Commander에게 “삼성전자 최근 악재?”처럼 물어보세요.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-hidden">
      <div className="rounded-3xl border border-white/10 bg-white/5 p-4 text-sm text-slate-200">
        <p className="text-xs uppercase tracking-[0.4em] text-indigo-300">News Workspace</p>
        <p className="mt-2 text-lg font-semibold text-white">{ticker ? `${ticker} ·` : null} 요약된 최신 뉴스</p>
        <p className="mt-1 text-slate-400">
          원문은 링크로 이동해 확인하고, AI가 정리한 요약만 화면에 표시됩니다.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {loading ? (
          skeletonCards
        ) : error ? (
          <div className="col-span-full rounded-3xl border border-rose-500/40 bg-rose-500/5 px-4 py-6 text-sm text-rose-100">
            {error}
          </div>
        ) : items.length === 0 ? (
          <div className="col-span-full rounded-3xl border border-white/10 bg-white/5 px-4 py-6 text-sm text-slate-300">
            관련 뉴스 요약을 찾지 못했습니다. 다른 키워드로 다시 시도해 보세요.
          </div>
        ) : (
          items.map((item) => (
            <SpotlightCard key={item.id ?? item.url ?? item.summary.slice(0, 24)} className="h-full bg-white/[0.02] p-5">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
                <span>{formatPublishedAt(item.publishedAt)}</span>
                <span className="text-slate-500">{item.source ?? "출처 미상"}</span>
              </div>
              <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded-full border border-white/10 px-3 py-1 text-[11px] uppercase tracking-wide text-indigo-200">
                  News Summary
                </span>
                {item.sentiment ? (
                  <span className={clsx("rounded-full border px-3 py-1 text-[11px] font-semibold uppercase", sentimentTone[item.sentiment] ?? sentimentTone.neutral)}>
                    {item.sentiment === "positive"
                      ? "긍정"
                      : item.sentiment === "negative"
                        ? "부정"
                        : "중립"}
                  </span>
                ) : null}
              </div>
              <p className="text-sm leading-relaxed text-slate-100">{item.summary ?? "요약이 제공되지 않았습니다."}</p>
              <div className="mt-4 flex items-center justify-between text-sm text-slate-400">
                {item.title ? <p className="font-semibold text-white">{item.title}</p> : <div />}
                {item.url ? (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-full border border-white/20 px-3 py-1 text-xs font-medium text-slate-200 transition hover:border-cyan-300 hover:text-white"
                  >
                    원문 보기 ↗
                  </a>
                ) : null}
              </div>
            </SpotlightCard>
          ))
        )}
      </div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <SpotlightCard className="h-full animate-pulse bg-white/[0.01] p-5">
      <div className="mb-3 flex justify-between text-xs text-slate-500">
        <div className="h-3 w-20 rounded-full bg-white/10" />
        <div className="h-3 w-16 rounded-full bg-white/10" />
      </div>
      <div className="mb-2 h-5 w-32 rounded-full bg-white/10" />
      <div className="space-y-2">
        <div className="h-3 rounded-full bg-white/10" />
        <div className="h-3 rounded-full bg-white/10" />
        <div className="h-3 rounded-full bg-white/10" />
      </div>
      <div className="mt-4 h-3 w-24 rounded-full bg-white/10" />
    </SpotlightCard>
  );
}
