"use client";

import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Loader2 } from "lucide-react";
import { useCompanySearch, type CompanySearchResult } from "@/hooks/useCompanySearch";

type CompanySearchBoxProps = {
  placeholder?: string;
  limit?: number;
};

const buildHref = (item: CompanySearchResult) => {
  if (item.ticker) {
    return `/company/${encodeURIComponent(item.ticker)}`;
  }
  if (item.corpCode) {
    return `/company/${encodeURIComponent(item.corpCode)}`;
  }
  return null;
};

export function CompanySearchBox({ placeholder = "회사명, 티커, 법인코드를 입력하세요", limit = 8 }: CompanySearchBoxProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [isFocused, setIsFocused] = useState(false);

  const { data: suggestions, isFetching } = useCompanySearch(query, limit);
  const list = useMemo(() => suggestions ?? [], [suggestions]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!query.trim()) {
      return;
    }
    if (list.length > 0) {
      const href = buildHref(list[0]);
      if (href) {
        router.push(href);
        return;
      }
    }
    router.push(`/company/${encodeURIComponent(query.trim().toUpperCase())}`);
  };

  const handleSelect = (item: CompanySearchResult) => {
    const href = buildHref(item);
    if (href) {
      router.push(href);
    }
  };

  return (
    <div className="relative">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
        <div>
          <h1 className="text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark">회사 스냅샷 찾기</h1>
          <p className="mt-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            회사명이나 티커를 입력하면 자동으로 후보를 추천해 드립니다. 찾는 회사가 없다면 공시나 뉴스로 등록된 회사인지 확인해주세요.
          </p>
        </div>
        <div className="relative flex items-center gap-3">
          <Search className="h-5 w-5 text-text-secondaryLight dark:text-text-secondaryDark" aria-hidden />
          <input
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setTimeout(() => setIsFocused(false), 150)}
            placeholder={placeholder}
            className="flex-1 rounded-md border border-border-light bg-background-light px-3 py-2 text-sm text-text-primaryLight outline-none transition-colors focus:border-primary dark:border-border-dark dark:bg-background-dark dark:text-text-primaryDark"
          />
          <button
            type="submit"
            className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white shadow transition-colors hover:bg-primary-hover"
          >
            검색
          </button>
          {isFetching ? <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden /> : null}
        </div>
      </form>
      {isFocused && query.trim().length >= 1 && list.length > 0 ? (
        <ul className="absolute z-20 mt-2 max-h-72 w-full overflow-y-auto rounded-xl border border-border-light bg-background-cardLight p-2 text-sm shadow-xl dark:border-border-dark dark:bg-background-cardDark">
          {list.map((item) => {
            const href = buildHref(item);
            return (
              <li key={`${item.corpCode ?? item.ticker ?? item.corpName ?? ""}`} className="rounded-md">
                <button
                  type="button"
                  onClick={() => href && handleSelect(item)}
                  className="flex w-full flex-col items-start gap-1 rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-primary/10 hover:text-primary dark:hover:bg-primary.dark/15"
                >
                  <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                    {item.corpName ?? item.ticker ?? item.corpCode ?? "알 수 없는 회사"}
                  </span>
                  <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                    {item.ticker ? `티커 ${item.ticker}` : null}
                    {item.ticker && item.corpCode ? " · " : ""}
                    {item.corpCode ? `법인코드 ${item.corpCode}` : null}
                  </span>
                  <span className="text-xs text-primary/80 dark:text-primary.dark/80">
                    {item.highlight ?? item.latestReportName ?? "최근 공시 확인 가능"}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
