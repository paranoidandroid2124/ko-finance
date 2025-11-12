"use client";

import { HelpCircle } from "lucide-react";
import { useEffect } from "react";
import { useSectorTopArticles } from "@/hooks/useSectorTopArticles";
import type { SectorSignalPoint } from "@/hooks/useSectorSignals";

type SectorDetailDrawerProps = {
  open: boolean;
  point: SectorSignalPoint | null;
  onClose: () => void;
};

export function SectorDetailDrawer({ open, point, onClose }: SectorDetailDrawerProps) {
  const sectorId = point?.sector.id ?? null;
  const { data, isLoading, isError, refetch } = useSectorTopArticles(sectorId, 72, 3);

  useEffect(() => {
    if (open && sectorId) {
      void refetch();
    }
  }, [open, refetch, sectorId]);

  const handleBackdropClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className={`fixed inset-0 z-40 transition ${open ? "pointer-events-auto" : "pointer-events-none"}`}
      role="dialog"
      aria-modal="true"
    >
      <div
        className={`absolute inset-0 bg-black/40 transition-opacity ${open ? "opacity-100" : "opacity-0"}`}
        onClick={handleBackdropClick}
      />
      <div
        className={`absolute right-0 top-0 h-full w-full max-w-lg transform bg-background-cardLight shadow-2xl transition-transform dark:bg-background-cardDark ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex h-full flex-col gap-4 border-l border-border-light p-6 dark:border-border-dark">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">{point?.sector.slug}</p>
              <h2 className="text-lg font-semibold">{point?.sector.name ?? "섹터 상세"}</h2>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                <span>평균 감성 {point?.sentimentMean?.toFixed(2) ?? "--"}</span>
                <span className="inline-flex items-center gap-1">
                  감성 Z {point?.sentimentZ?.toFixed(2) ?? "--"}
                  <span className="group relative inline-flex items-center text-[11px] text-text-tertiaryLight dark:text-text-ter티aryDark">
                    <HelpCircle className="h-3.5 w-3.5" aria-hidden />
                    <span className="pointer-events-none absolute left-1/2 top-full z-10 w-max -translate-x-1/2 translate-y-2 rounded-md border border-border-light bg-background-cardLight px-3 py-1 text-[11px] text-text-secondaryLight opacity-0 shadow-lg transition-opacity group-hover:opacity-100 dark:border-border-dark dark:bg-background-cardDark dark:text-text-secondaryDark">
                      감성 Z는 이 섹터의 최근 평균 감성이 과거 평균 대비 몇 표준편차 떨어져 있는지를 나타냅니다.
                    </span>
                  </span>
                </span>
                <span className="inline-flex items-center gap-1">
                  기사량 Z {point?.volumeZ?.toFixed(2) ?? "--"}
                  <span className="group relative inline-flex items-center text-[11px] text-text-ter티aryLight dark:text-text-tertiaryDark">
                    <HelpCircle className="h-3.5 w-3.5" aria-hidden />
                    <span className="pointer-events-none absolute left-1/2 top-full z-10 w-max -translate-x-1/2 translate-y-2 rounded-md border border-border-light bg-background-cardLight px-3 py-1 text-[11px] text-text-secondaryLight opacity-0 shadow-lg transition-opacity group-hover:opacity-100 dark:border-border-dark dark:bg-background-cardDark dark:text-text-secondaryDark">
                      기사량 Z는 최근 기사 건수가 과거 평균 대비 얼마나 이례적인지를 보여 줍니다.
                    </span>
                  </span>
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-border-light px-3 py-1 text-xs font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
            >
              닫기
            </button>
          </div>

          <div className="space-y-2 text-sm">
            <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              72시간 기준 주요 기사. 점수를 높인 순서대로 정렬되어 있습니다.
            </p>
            {isLoading ? (
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">기사를 불러오는 중...</p>
            ) : isError ? (
              <p className="text-xs text-destructive">주요 기사를 가져오지 못했습니다.</p>
            ) : (
              <ul className="space-y-3">
                {data?.items.length ? (
                  data.items.map((item) => (
                    <li key={item.id} className="rounded-lg border border-border-light/70 p-3 dark:border-border-dark/70">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <button
                            type="button"
                            onClick={() => window.open(item.targetUrl || item.url, "_blank", "noopener,noreferrer")}
                            className="text-left text-sm font-semibold text-primary underline-offset-2 hover:underline"
                          >
                            {item.title}
                          </button>
                          <p className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                            {new Date(item.publishedAt).toLocaleString()} · 톤 {item.tone != null ? item.tone.toFixed(2) : "N/A"}
                          </p>
                        </div>
                      </div>
                      {item.summary ? (
                        <p className="mt-2 whitespace-pre-line text-xs leading-relaxed text-text-secondaryLight dark:text-text-secondaryDark">
                          {item.summary}
                        </p>
                      ) : null}
                    </li>
                  ))
                ) : (
                  <li className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">표시할 기사가 없습니다.</li>
                )}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
