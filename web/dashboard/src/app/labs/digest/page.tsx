"use client";

import { useState } from "react";
import clsx from "clsx";
import { RefreshCw } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { DigestCard } from "@/components/digest/DigestCard";
import { sampleDigest } from "@/components/digest/sampleData";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { ErrorState } from "@/components/ui/ErrorState";
import { useDigestPreview } from "@/hooks/useDigestPreview";

const TIMEFRAME_OPTIONS: Array<{ value: "daily" | "weekly"; label: string }> = [
  { value: "daily", label: "Daily Digest" },
  { value: "weekly", label: "Weekly Highlight" },
];

export default function DigestLabPage() {
  const [timeframe, setTimeframe] = useState<"daily" | "weekly">("daily");
  const { data, isLoading, isFetching, isError, refetch } = useDigestPreview({ timeframe });

  const payload = data ?? sampleDigest;
  const isEmpty = Boolean(data) && payload.news.length === 0 && payload.watchlist.length === 0;

  return (
    <AppShell title="Digest 미리보기">
      <div className="flex flex-col gap-6">
        <section className="rounded-2xl border border-border-light bg-background-cardLight p-5 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
          <h1 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">Watchlist Digest 프리뷰</h1>
          <p className="mt-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            실제 다이제스트 파이프라인에서 수집한 데이터로 카드 미리보기를 제공합니다. 기간을 선택하고 필요하면 새로 고침하세요.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
            <div className="inline-flex overflow-hidden rounded-full border border-border-light bg-background-body dark:border-border-dark dark:bg-background-body.dark">
              {TIMEFRAME_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setTimeframe(option.value)}
                  className={clsx(
                    "px-4 py-1.5 font-medium transition-colors",
                    timeframe === option.value
                      ? "bg-primary text-white"
                      : "text-text-secondaryLight hover:bg-border-light/40 dark:text-text-secondaryDark dark:hover:bg-border-dark/40",
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => refetch()}
              className={clsx(
                "inline-flex items-center gap-2 rounded-full border border-border-light px-4 py-1.5 font-medium text-text-secondaryLight transition-colors hover:bg-border-light/40 dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40",
                isFetching ? "opacity-60" : "",
              )}
              disabled={isFetching}
            >
              <RefreshCw className={clsx("h-4 w-4", isFetching ? "animate-spin" : "")} />
              새로 고침
            </button>
          </div>
        </section>

        {isError && (
          <ErrorState
            title="다이제스트 데이터를 불러오지 못했어요"
            description="네트워크 상태를 확인한 뒤 다시 새로 고침해 주세요. 임시로 샘플 데이터를 표시합니다."
          />
        )}

        <section className="flex justify-center">
          {isLoading && !data ? (
            <SkeletonBlock className="h-[620px] w-full max-w-4xl rounded-3xl" />
          ) : (
            <DigestCard data={payload} isEmpty={isEmpty} />
          )}
        </section>
      </div>
    </AppShell>
  );
}
