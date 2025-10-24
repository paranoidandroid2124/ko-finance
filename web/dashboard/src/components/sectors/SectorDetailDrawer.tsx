"use client";

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

  const sanitizeSummary = (summary: string): string =>
    summary.replace(/<[^>]*>/g, ' ').replace(/&nbsp;/gi, ' ').replace(/\s+/g, ' ').trim();

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
              <p className="mt-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                감성 Z {point?.sentimentZ?.toFixed(2) ?? "--"} · 기사량 Z {point?.volumeZ?.toFixed(2) ?? "--"}
              </p>
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
                            {new Date(item.publishedAt).toLocaleString()} · 톤{" "}
                            {item.tone != null ? item.tone.toFixed(2) : "N/A"}
                          </p>
                          {item.summary ? (
                            <p className="mt-2 text-xs leading-relaxed text-text-secondaryLight dark:text-text-secondaryDark">
                              {item.summary}
                            </p>
                          ) : null}
                        </div>
                          </div>
                          {item.summary ? (
                            <p className="mt-2 text-xs leading-relaxed text-text-secondaryLight dark:text-text-secondaryDark">
                              {sanitizeSummary(item.summary)}
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
