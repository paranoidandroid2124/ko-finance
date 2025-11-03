"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { CompanySearchBox } from "@/components/company/CompanySearchBox";
import { CompanySuggestionSection } from "@/components/company/CompanySuggestionSection";
import { useCompanySuggestions } from "@/hooks/useCompanySuggestions";
import { normalizeCompanySearchResult, type CompanySearchResult } from "@/hooks/useCompanySearch";

const RECENT_COMPANIES_KEY = "kofilot_recent_companies";

const loadRecentCompanies = (): CompanySearchResult[] => {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const stored = window.localStorage.getItem(RECENT_COMPANIES_KEY);
    if (!stored) return [];
    const parsed = JSON.parse(stored);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((item) => normalizeCompanySearchResult(item))
      .filter((item) => item.corpName || item.ticker || item.corpCode)
      .slice(0, 6);
  } catch {
    return [];
  }
};

export default function CompanyLandingPage() {
  const { data: suggestions } = useCompanySuggestions(6);
  const [recentViewed, setRecentViewed] = useState<CompanySearchResult[]>([]);

  useEffect(() => {
    setRecentViewed(loadRecentCompanies());
  }, []);

  return (
    <AppShell>
      <div className="space-y-6">
        <CompanySearchBox />
        {recentViewed.length ? (
          <CompanySuggestionSection
            title="최근 열어본 회사"
            description="최근 살펴본 회사 스냅샷을 빠르게 다시 확인하세요."
            items={recentViewed}
          />
        ) : null}
        {suggestions?.recentFilings?.length ? (
          <CompanySuggestionSection
            title="따끈한 공시"
            description="최근 공시를 제출한 회사입니다."
            items={suggestions.recentFilings}
          />
        ) : null}
        {suggestions?.trendingNews?.length ? (
          <CompanySuggestionSection
            title="뉴스에서 주목받는 회사"
            description="최근 7일간 기사량이 많았던 회사입니다."
            items={suggestions.trendingNews}
          />
        ) : null}
      </div>
    </AppShell>
  );
}
