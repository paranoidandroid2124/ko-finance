"use client";

import { Lock } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { nextTier, usePlanTier } from "@/store/planStore";
import type {
  SearchResult as SearchResultItem,
  SearchResultType,
  SearchTotals,
} from "@/hooks/useSearchResults";

type ResultType = SearchResultType;

const TAB_LABELS: Record<ResultType, string> = {
  filing: "공시",
  news: "뉴스",
  table: "표",
  chart: "차트",
};

type SearchResultsProps = {
  results: SearchResultItem[];
  totals?: SearchTotals | null;
  activeType?: ResultType;
  isLoading?: boolean;
  onChangeType?: (type: ResultType) => void;
  onLoadMore?: () => void;
  canLoadMore?: boolean;
};

type TabSummary = {
  type: ResultType;
  label: string;
  count: number;
};

export function SearchResults({
  results,
  totals,
  activeType = "filing",
  isLoading = false,
  onChangeType,
  onLoadMore,
  canLoadMore = false,
}: SearchResultsProps) {
  const isControlled = typeof onChangeType === "function";
  const [internalType, setInternalType] = useState<ResultType>(activeType);
  const currentType = isControlled ? activeType : internalType;

  const tabs = useMemo<TabSummary[]>(() => {
    return (Object.keys(TAB_LABELS) as ResultType[]).map((type) => ({
      type,
      label: TAB_LABELS[type],
      count: totals ? totals[type] : results.filter((entry) => entry.type === type).length,
    }));
  }, [results, totals]);

  useEffect(() => {
    if (isControlled) {
      return;
    }
    const nextType =
      tabs.find((tab) => tab.count > 0)?.type ??
      (results[0]?.type ?? internalType);
    if (nextType !== internalType) {
      setInternalType(nextType);
    }
  }, [isControlled, tabs, results, internalType]);

  const filtered = results.filter((entry) => entry.type === currentType);

  const handleTabClick = (type: ResultType) => {
    if (isControlled) {
      onChangeType?.(type);
    } else {
      setInternalType(type);
    }
  };

  return (
    <section className="space-y-6">
      <nav className="flex flex-wrap gap-2">
        {tabs.map((tab) => {
          const isActive = tab.type === currentType;
          return (
            <button
              key={tab.type}
              type="button"
              onClick={() => handleTabClick(tab.type)}
              className={`group relative inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold transition-motion-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
                isActive
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border-light text-text-secondaryLight hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark"
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`rounded-full px-2 py-0.5 text-xs ${
                  isActive
                    ? "bg-primary text-white"
                    : "bg-background-light text-text-secondaryLight dark:bg-background-dark dark:text-text-secondaryDark"
                }`}
              >
                {tab.count}
              </span>
            </button>
          );
        })}
      </nav>

      {isLoading && filtered.length === 0 ? (
        <SkeletonBlock lines={8} />
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border-light p-6 text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
          현재 탭에 표시할 결과가 없습니다. 다른 키워드나 탭을 선택해 보세요.
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {filtered.map((result) => (
            <article
              key={result.id}
              className="flex flex-col gap-4 rounded-xl border border-border-light bg-background-cardLight p-5 shadow-card transition-motion-medium hover:-translate-y-1.5 hover:shadow-lg dark:border-border-dark dark:bg-background-cardDark"
            >
              <header className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">{result.title}</p>
                  <div className="flex flex-wrap gap-2 text-[11px] uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                    <span className="rounded border border-border-light px-2 py-0.5 dark:border-border-dark">{result.category}</span>
                    {result.filedAt ? <span>{result.filedAt}</span> : null}
                    {result.latestIngestedAt ? <span>업데이트 {result.latestIngestedAt}</span> : null}
                  </div>
                </div>
                {typeof result.sourceReliability === "number" ? (
                  <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary dark:bg-primary/20 dark:text-primary">
                    신뢰도 {(result.sourceReliability * 100).toFixed(0)}%
                  </span>
                ) : null}
              </header>

              {result.evidenceCounts ? (
                <div className="flex flex-wrap gap-2 text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
                  {Object.entries(result.evidenceCounts)
                    .filter(([, count]) => (count ?? 0) > 0)
                    .map(([key, count]) => (
                      <span key={key} className="rounded-full border border-border-light px-2 py-0.5 dark:border-border-dark">
                        {badgeLabel(key)} · {count}
                      </span>
                    ))}
                </div>
              ) : null}

              <footer className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="rounded-lg border border-border-light px-3 py-2 text-xs font-semibold text-text-secondaryLight transition-motion-fast hover:border-primary hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary dark:hover:text-primary"
                >
                  근거 보기
                </button>
                <LockedButton label="비교에 추가" isLocked={result.actions?.compareLocked} />
                <LockedButton label="알림 설정" isLocked={result.actions?.alertLocked} />
                <LockedButton label="내보내기" isLocked={result.actions?.exportLocked} />
              </footer>
            </article>
          ))}
        </div>
      )}

      {canLoadMore ? (
        <div className="flex justify-center">
          <button
            type="button"
            onClick={onLoadMore}
            disabled={isLoading}
            className="inline-flex items-center gap-2 rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-secondaryLight transition-motion-fast hover:border-primary hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-60 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary dark:hover:text-primary"
          >
            더 보기
            {isLoading ? <span className="h-2.5 w-2.5 animate-spin rounded-full border border-current border-t-transparent" aria-hidden /> : null}
          </button>
        </div>
      ) : null}
    </section>
  );
}

function LockedButton({ label, isLocked }: { label: string; isLocked?: boolean }) {
  const router = useRouter();
  const currentTier = usePlanTier();
  const upgradeTier = nextTier(currentTier) ?? "enterprise";
  const targetLabel = upgradeTier === "enterprise" ? "Enterprise" : "Pro";

  if (!isLocked) {
    return (
      <button
        type="button"
        className="rounded-lg border border-border-light px-3 py-2 text-xs font-semibold text-text-secondaryLight transition-motion-fast hover:border-primary hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary dark:hover:text-primary"
      >
        {label}
      </button>
    );
  }

  return (
    <button
      type="button"
      className="group relative inline-flex items-center gap-2 rounded-lg border border-dashed border-border-light px-3 py-2 text-xs font-semibold text-text-secondaryLight transition-motion-tactile hover:border-primary hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary dark:border-border-dark dark:text-text-secondaryDark"
      onClick={() => router.push(`/settings?panel=plan&tier=${upgradeTier}`)}
    >
      <span>{label}</span>
      <Lock aria-hidden className="h-4 w-4 text-primary" />
      <span className="pointer-events-none absolute -bottom-10 left-1/2 w-max -translate-x-1/2 rounded-lg border border-border-light bg-background-cardLight px-3 py-1 text-[11px] opacity-0 shadow-md transition-motion-medium group-hover:translate-y-2 group-hover:opacity-100 dark:border-border-dark dark:bg-background-cardDark">
        {targetLabel} 플랜으로 업그레이드하면 곧바로 사용할 수 있어요.
      </span>
    </button>
  );
}

function badgeLabel(key: string): string {
  switch (key) {
    case "filings":
      return "공시";
    case "news":
      return "뉴스";
    case "tables":
      return "표";
    case "charts":
      return "차트";
    default:
      return key;
  }
}

