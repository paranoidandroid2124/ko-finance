"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronUp, Sparkles } from "lucide-react";

import { fetchWithAuth } from "@/lib/fetchWithAuth";
import { useToastStore } from "@/store/toastStore";

type FeedItem = {
  id: string;
  title?: string | null;
  summary?: string | null;
  ticker?: string | null;
  type?: string | null;
  targetUrl?: string | null;
  createdAt?: string | null;
  status?: string | null;
};

type FeedBriefing = {
  id: string;
  title: string;
  summary?: string | null;
  ticker?: string | null;
  count: number;
  items: FeedItem[];
};

export function ProactiveBriefingsWidget() {
  const pushToast = useToastStore((state) => state.show);
  const [briefings, setBriefings] = useState<FeedBriefing[]>([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetchWithAuth("/api/v1/feed/proactive/briefings?limit=30");
      if (!res.ok) {
        throw new Error(`briefings ${res.status}`);
      }
      const data = await res.json();
      setBriefings(Array.isArray(data?.items) ? data.items : []);
    } catch (error) {
      pushToast({
        id: `briefings/load/${Date.now()}`,
        intent: "error",
        title: "브리핑을 불러오지 못했습니다.",
        message: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading && briefings.length === 0) {
    return (
      <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-sm text-slate-400">
        프로액티브 브리핑을 불러오는 중…
      </div>
    );
  }

  if (!briefings.length) {
    return null;
  }

  return (
    <div className="space-y-3 rounded-2xl border border-white/10 bg-white/[0.04] p-4 shadow-lg">
      <div className="flex items-center gap-2 text-sm font-semibold text-white">
        <Sparkles className="h-4 w-4 text-blue-400" />
        오늘의 브리핑
      </div>
      <div className="space-y-2">
        {briefings.map((briefing) => {
          const isOpen = expanded[briefing.id] ?? false;
          return (
            <div
              key={briefing.id}
              className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-200 shadow"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate font-semibold text-white">{briefing.title}</p>
                  {briefing.ticker ? <p className="text-xs text-blue-200">{briefing.ticker}</p> : null}
                  <p className="text-[11px] text-slate-400">
                    관련 소식 {briefing.count}건
                  </p>
                  {briefing.summary ? (
                    <p className="mt-1 text-xs text-slate-300 line-clamp-2">{briefing.summary}</p>
                  ) : null}
                </div>
                <button
                  type="button"
                  onClick={() => setExpanded((prev) => ({ ...prev, [briefing.id]: !isOpen }))}
                  className="rounded-full border border-white/10 p-1 text-slate-200 transition hover:border-blue-400 hover:text-blue-200"
                  aria-label="브리핑 자세히"
                >
                  {isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </button>
              </div>
              {isOpen ? (
                <div className="mt-2 space-y-2">
                  {briefing.items.map((item) => (
                    <div key={item.id} className="rounded-lg border border-white/5 bg-white/5 p-2 text-xs text-slate-200">
                      <p className="font-semibold text-white">{item.title || "알림"}</p>
                      {item.ticker ? <p className="text-[11px] text-blue-200">{item.ticker}</p> : null}
                      {item.summary ? <p className="text-[11px] text-slate-300">{item.summary}</p> : null}
                      {item.createdAt ? (
                        <p className="mt-1 text-[10px] text-slate-500">{new Date(item.createdAt).toLocaleString()}</p>
                      ) : null}
                      {item.targetUrl ? (
                        <a
                          href={item.targetUrl}
                          className="mt-1 inline-flex text-[11px] font-semibold text-blue-300 underline"
                          target="_blank"
                          rel="noreferrer"
                        >
                          원문 보기
                        </a>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
