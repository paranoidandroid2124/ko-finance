"use client";

import { useState } from "react";
import clsx from "clsx";
import { AppShell } from "@/components/layout/AppShell";
import { DigestCard } from "@/components/digest/DigestCard";
import { emptyDigest, sampleDigest } from "@/components/digest/sampleData";

type ViewMode = "sample" | "empty";

export default function DigestLabPage() {
  const [viewMode, setViewMode] = useState<ViewMode>("sample");

  const payload = viewMode === "sample" ? sampleDigest : emptyDigest;

  return (
    <AppShell title="Digest 미리보기">
      <div className="flex flex-col gap-6">
        <section className="rounded-2xl border border-border-light bg-background-cardLight p-5 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
          <h1 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">Watchlist Digest 시안</h1>
          <p className="mt-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            Figma 시안을 기반으로 한 Digest 템플릿 프리뷰입니다. 아래 토글을 통해 샘플 데이터와 빈 상태를 확인할 수 있습니다.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
            <div className="inline-flex overflow-hidden rounded-full border border-border-light bg-background-body dark:border-border-dark dark:bg-background-body.dark">
              {(["sample", "empty"] as ViewMode[]).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => setViewMode(mode)}
                  className={clsx(
                    "px-4 py-1.5 font-medium transition-colors",
                    viewMode === mode
                      ? "bg-primary text-white"
                      : "text-text-secondaryLight hover:bg-border-light/40 dark:text-text-secondaryDark dark:hover:bg-border-dark/40"
                  )}
                >
                  {mode === "sample" ? "샘플 데이터" : "빈 상태"}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => setViewMode((prev) => (prev === "sample" ? "empty" : "sample"))}
              className="rounded-full border border-border-light px-4 py-1.5 font-medium text-text-secondaryLight transition-colors hover:bg-border-light/40 dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/30"
            >
              보기 전환
            </button>
          </div>
        </section>

        <section className="flex justify-center">
          <DigestCard data={payload} isEmpty={viewMode === "empty"} />
        </section>
      </div>
    </AppShell>
  );
}
