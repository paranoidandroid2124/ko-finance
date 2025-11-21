"use client";

import { useEffect, useState } from "react";
import { Bell, Check, Trash2 } from "lucide-react";

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

export function ProactiveFeedWidget() {
  const pushToast = useToastStore((state) => state.show);
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(false);

  const loadFeed = async () => {
    setLoading(true);
    try {
      const res = await fetchWithAuth("/api/v1/feed/proactive?limit=5");
      if (!res.ok) {
        throw new Error(`feed ${res.status}`);
      }
      const data = await res.json();
      setItems(Array.isArray(data?.items) ? data.items : []);
    } catch (error) {
      pushToast({
        id: `feed/load/${Date.now()}`,
        intent: "error",
        title: "프로액티브 피드를 불러오지 못했습니다.",
        message: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadFeed();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateStatus = async (id: string, status: "read" | "dismissed") => {
    try {
      const res = await fetchWithAuth(`/api/v1/feed/proactive/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!res.ok) {
        throw new Error(`status ${res.status}`);
      }
      setItems((prev) => prev.filter((item) => item.id !== id));
    } catch (error) {
      pushToast({
        id: `feed/status/${Date.now()}`,
        intent: "error",
        title: "알림 상태를 변경하지 못했습니다.",
        message: error instanceof Error ? error.message : undefined,
      });
    }
  };

  if (loading && items.length === 0) {
    return (
      <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-sm text-slate-400">
        프로액티브 인사이트를 불러오는 중…
      </div>
    );
  }

  if (!items.length) {
    return null;
  }

  return (
    <div className="space-y-3 rounded-2xl border border-white/10 bg-white/[0.04] p-4 shadow-lg">
      <div className="flex items-center gap-2 text-sm font-semibold text-white">
        <Bell className="h-4 w-4 text-blue-400" />
        프로액티브 인사이트
      </div>
      <div className="space-y-2">
        {items.map((item) => (
          <div
            key={item.id}
            className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-200 shadow"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate font-semibold text-white">{item.title || "새 알림"}</p>
                {item.ticker ? <p className="text-xs text-blue-200">{item.ticker}</p> : null}
                {item.summary ? <p className="mt-1 text-xs text-slate-300 line-clamp-2">{item.summary}</p> : null}
              </div>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => updateStatus(item.id, "read")}
                  className="rounded-full border border-white/10 p-1 text-slate-200 transition hover:border-blue-400 hover:text-blue-200"
                  aria-label="읽음 처리"
                >
                  <Check className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => updateStatus(item.id, "dismissed")}
                  className="rounded-full border border-white/10 p-1 text-slate-200 transition hover:border-rose-400 hover:text-rose-200"
                  aria-label="삭제"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
            {item.createdAt ? (
              <p className="mt-1 text-[11px] text-slate-500">{new Date(item.createdAt).toLocaleString()}</p>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
