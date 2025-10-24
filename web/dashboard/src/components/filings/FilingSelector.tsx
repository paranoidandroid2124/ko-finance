import classNames from "classnames";
import { useMemo, useState } from "react";
import type { FilingListItem } from "@/hooks/useFilings";

type Props = {
  filings: FilingListItem[];
  selectedId?: string;
  onSelect?: (id: string) => void;
  days: number;
  onDaysChange?: (days: number) => void;
  isLoading?: boolean;
};

const sentimentBadge: Record<FilingListItem["sentiment"], string> = {
  positive: "bg-accent-positive/15 text-accent-positive",
  neutral: "bg-border-light/60 text-text-secondaryLight dark:bg-border-dark/60 dark:text-text-secondaryDark",
  negative: "bg-accent-negative/15 text-accent-negative"
};

const DAY_OPTIONS = [7, 30, 90];

export function FilingSelector({ filings, selectedId, onSelect, days, onDaysChange, isLoading }: Props) {
  const [searchTerm, setSearchTerm] = useState("");

  const filteredFilings = useMemo(() => {
    const keyword = searchTerm.trim().toLowerCase();
    if (!keyword) {
      return filings;
    }
    return filings.filter((filing) => {
      const company = filing.company?.toLowerCase() ?? "";
      const title = filing.title?.toLowerCase() ?? "";
      const type = filing.type?.toLowerCase() ?? "";
      return company.includes(keyword) || title.includes(keyword) || type.includes(keyword);
    });
  }, [filings, searchTerm]);

  const handleSelect = (id: string) => {
    if (onSelect) {
      onSelect(id);
    }
  };

  return (
    <aside className="flex h-full max-h-[calc(100vh-160px)] min-h-0 flex-col overflow-hidden rounded-xl border border-border-light bg-background-cardLight shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <header className="flex items-center justify-between border-b border-border-light px-4 py-3 dark:border-border-dark">
        <div>
          <p className="text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">최근 공시</p>
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">최근 {days}일 이내</p>
        </div>
        <div className="flex gap-1">
          {DAY_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => onDaysChange?.(option)}
              className={classNames(
                "rounded-md px-3 py-1 text-xs font-semibold transition-colors",
                option === days
                  ? "bg-primary text-white"
                  : "border border-border-light text-text-secondaryLight hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
              )}
            >
              {option}일
            </button>
          ))}
        </div>
      </header>

      <div className="border-b border-border-light px-4 py-3 dark:border-border-dark">
        <input
          type="search"
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
          placeholder="기업·공시 제목 검색"
          className="w-full rounded-md border border-border-light/80 bg-background-cardLight px-3 py-2 text-sm text-text-primaryLight outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark dark:focus:border-primary.dark dark:focus:ring-primary.dark/20"
        />
      </div>

      <div className="flex-1 overflow-y-auto pr-1 min-h-0">
        {isLoading ? (
          <div className="flex h-full items-center justify-center text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            불러오는 중...
          </div>
        ) : filteredFilings.length === 0 ? (
          <div className="flex h-full items-center justify-center px-4 text-center text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            검색 조건에 맞는 공시가 없습니다.
          </div>
        ) : (
          <ul className="divide-y divide-border-light dark:divide-border-dark">
            {filteredFilings.map((filing) => (
              <li key={filing.id}>
                <button
                  type="button"
                  onClick={() => handleSelect(filing.id)}
                  className={classNames(
                    "w-full px-4 py-3 text-left transition-colors hover:bg-primary/5 dark:hover:bg-primary.dark/10",
                    selectedId === filing.id && "bg-primary/10 dark:bg-primary.dark/15"
                  )}
                >
                  <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">{filing.company}</p>
                  <p className="mt-1 line-clamp-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">{filing.title}</p>
                  <div className="mt-3 flex items-center justify-between text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
                    <span className="truncate">{filing.filedAt}</span>
                    <span
                      className={classNames(
                        "ml-2 inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 font-semibold",
                        sentimentBadge[filing.sentiment]
                      )}
                      title={filing.sentimentReason}
                    >
                      {filing.sentiment === "positive" ? "긍정" : filing.sentiment === "negative" ? "부정" : "중립"}
                    </span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
