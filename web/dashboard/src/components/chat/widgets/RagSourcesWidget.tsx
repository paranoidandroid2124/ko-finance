"use client";

import type { RagSourceReference } from "@/store/chatStore";
import { useToastStore } from "@/store/toastStore";

type RagSourcesWidgetProps = {
  sources: RagSourceReference[];
};

export default function RagSourcesWidget({ sources }: RagSourcesWidgetProps) {
  const showToast = useToastStore((state) => state.show);

  const handleOpen = (url?: string) => {
    if (!url) {
      showToast({
        intent: "warning",
        title: "링크를 열 수 없습니다",
        message: "출처에 연결된 URL이 없습니다.",
      });
      return;
    }
    const opened = window.open(url, "_blank", "noopener,noreferrer");
    if (!opened) {
      showToast({
        intent: "warning",
        title: "팝업이 차단되었어요",
        message: "팝업 차단을 해제하거나, 링크를 길게 눌러 새 탭에서 열어주세요.",
      });
    }
  };

  if (!sources.length) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-200">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div>
          <p className="text-[11px] uppercase tracking-[0.3em] text-slate-500">Evidence</p>
          <p className="text-base font-semibold text-white">연결된 근거</p>
        </div>
        <span className="rounded-full border border-white/10 px-3 py-0.5 text-[11px] text-slate-400">
          {sources.length}개
        </span>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {sources.map((source) => {
          const title = source.title || source.label || source.source || "출처 미상";
          const snippet = source.snippet;
          const pageLabel = source.pageLabel ?? (typeof source.page !== "undefined" ? `p.${source.page}` : undefined);
          const url = typeof source.sourceUrl === "string" ? source.sourceUrl : undefined;
          const score = typeof source.score === "number" ? source.score : undefined;
          const published = typeof source.publishedAt === "string" ? source.publishedAt : undefined;
          const badge = [pageLabel, published, score !== undefined ? `score ${score.toFixed(2)}` : null]
            .filter(Boolean)
            .join(" · ");

          return (
            <button
              key={source.id ?? `${title}-${pageLabel ?? ""}`}
              type="button"
              onClick={() => handleOpen(url)}
              className="group flex flex-col items-start gap-2 rounded-2xl border border-white/10 bg-black/20 p-4 text-left transition hover:-translate-y-0.5 hover:border-primary/60 hover:bg-white/10"
            >
              <div className="flex w-full items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-white">{title}</p>
                  {badge ? <p className="text-[11px] uppercase tracking-wide text-slate-400">{badge}</p> : null}
                </div>
                <span className="rounded-full border border-white/15 px-3 py-1 text-[11px] font-semibold text-white transition group-hover:border-primary/60 group-hover:text-primary">
                  보기
                </span>
              </div>
              {snippet ? <p className="line-clamp-3 text-xs text-slate-300">{snippet}</p> : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}
