"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { FilingDetailPanel } from "@/components/filings/FilingDetailPanel";
import { FilingSelector } from "@/components/filings/FilingSelector";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { useFilings, useFilingDetail } from "@/hooks/useFilings";
import type { FilingSentimentFilter } from "@/hooks/useFilings";
import { FilingHeaderNotice } from "@/components/legal";

export default function FilingsPage() {
  const searchParams = useSearchParams();
  const initialFilingId = searchParams?.get("filingId");

  const [days, setDays] = useState(30);
  const [sentimentFilter, setSentimentFilter] = useState<FilingSentimentFilter>("all");
  const filingQuery = useMemo(
    () => ({
      days,
      limit: 200,
      sentiment: sentimentFilter
    }),
    [days, sentimentFilter]
  );

  const {
    data: filings = [],
    isLoading,
    isFetching,
    isError,
  } = useFilings(filingQuery);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const {
    data: filingDetail,
    isLoading: isDetailLoading,
    isError: isDetailError,
  } = useFilingDetail(selectedId ?? undefined);

  useEffect(() => {
    if (!filings.length) return;

    setSelectedId((current) => {
      if (current && filings.some((filing) => filing.id === current)) {
        return current;
      }
      if (initialFilingId && filings.some((filing) => filing.id === initialFilingId)) {
        return initialFilingId;
      }
      return filings[0].id;
    });
  }, [filings, initialFilingId]);

  const handleDaysChange = useCallback((value: number) => {
    setDays(value);
  }, []);
  const handleSentimentChange = useCallback((value: FilingSentimentFilter) => {
    setSentimentFilter(value);
  }, []);

  const hasFilings = filings.length > 0;
  const isListLoading = isLoading || isFetching;

  return (
    <AppShell>
      <FilingHeaderNotice className="mb-4 text-xs text-text-secondaryLight dark:text-text-secondaryDark" />
      {isError ? (
        <ErrorState
          title="공시 정보를 불러오지 못했어요"
          description="네트워크 상태를 확인한 뒤 다시 시도해주세요. 문제가 지속되면 관리자에게 문의하세요."
        />
      ) : isLoading && !hasFilings ? (
        <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
          <SkeletonBlock lines={6} />
          <SkeletonBlock lines={8} />
        </div>
      ) : hasFilings ? (
        <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
          <FilingSelector
            filings={filings}
            selectedId={selectedId ?? undefined}
            onSelect={setSelectedId}
            days={days}
            onDaysChange={handleDaysChange}
            sentimentFilter={sentimentFilter}
            onSentimentFilterChange={handleSentimentChange}
            isLoading={isListLoading}
          />
          {isDetailError ? (
            <ErrorState
              title="공시 상세를 불러오지 못했어요"
              description="선택한 공시의 상세정보를 가져오지 못했습니다. 잠시 후 다시 시도해주세요."
            />
          ) : isDetailLoading || !filingDetail ? (
            <SkeletonBlock lines={8} />
          ) : (
            <FilingDetailPanel filing={filingDetail} />
          )}
        </div>
      ) : (
        <EmptyState
          title="표시할 공시가 없습니다"
          description="필터를 조정하거나 다른 기간을 선택해 최신 공시를 확인해보세요."
        />
      )}
    </AppShell>
  );
}
