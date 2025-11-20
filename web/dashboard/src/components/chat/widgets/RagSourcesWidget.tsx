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
      <div className="space-y-3">
        {sources.map((source) => {
          const title = source.title || source.label || source.source || "출처 미상";
          const snippet = source.snippet;
          const pageLabel = source.pageLabel ?? (typeof source.page !== "undefined" ? `p.${source.page}` : null);
          return (
            <div
              key={source.id ?? `${title}-${pageLabel ?? ""}`}
              className="rounded-2xl border border-white/10 bg-black/20 p-3"
            >
              <div className="flex flex-col gap-1">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-white">{title}</p>
                    {pageLabel ? <p className="text-[11px] uppercase tracking-wide text-slate-400">{pageLabel}</p> : null}
                  </div>
                  <button
                    type="button"
                    onClick={() => handleOpen(typeof source.sourceUrl === "string" ? source.sourceUrl : undefined)}
                    className="rounded-full border border-white/15 px-3 py-1 text-[11px] font-semibold text-white transition hover:border-white/40 hover:text-primary disabled:opacity-40"
                    disabled={!source.sourceUrl}
                  >
                    열기
                  </button>
                </div>
                {snippet ? <p className="text-xs text-slate-400">{snippet}</p> : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
