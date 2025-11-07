"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, X } from "lucide-react";
import clsx from "clsx";

import { resolveCompanyIdentifier, useCompanySearch, type CompanySearchResult } from "@/hooks/useCompanySearch";

type CompanyTickerInputProps = {
  values: string[];
  onChange: (tickers: string[]) => void;
  placeholder?: string;
  id?: string;
  "aria-label"?: string;
  disabled?: boolean;
  helperText?: string;
  staticOptions?: Array<{ ticker: string; label?: string | null }>;
};

type ResolvedTicker = {
  ticker: string;
  corpName?: string | null;
  corpCode?: string | null;
  highlight?: string | null;
};

const normalizeTickers = (values: string[]) =>
  Array.from(
    new Set(
      values
        .map((value) => value.trim())
        .filter((value) => value.length > 0)
        .map((value) => value.toUpperCase()),
    ),
  );

const suggestionKey = (item: CompanySearchResult, index: number) =>
  `${item.ticker ?? item.corpCode ?? item.corpName ?? "company"}-${index}`;

export function CompanyTickerInput({
  values,
  onChange,
  placeholder = "",
  id,
  "aria-label": ariaLabel,
  disabled = false,
  helperText,
  staticOptions = [],
}: CompanyTickerInputProps) {
  const [query, setQuery] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const [resolved, setResolved] = useState<Record<string, ResolvedTicker>>({});

  const normalizedValues = useMemo(() => normalizeTickers(values), [values]);
  const { data: suggestions = [], isFetching } = useCompanySearch(query, 8);

  const emitChange = (next: string[]) => {
    onChange(normalizeTickers(next));
  };

  const handleRemove = (ticker: string) => {
    emitChange(normalizedValues.filter((item) => item !== ticker));
    setResolved((prev) => {
      const next = { ...prev };
      delete next[ticker];
      return next;
    });
  };

  const handleSelect = (item: CompanySearchResult) => {
    const ticker = item.ticker?.trim() || item.corpCode?.trim();
    if (!ticker) {
      return;
    }
    const normalized = ticker.toUpperCase();
    if (normalizedValues.includes(normalized)) {
      setQuery("");
      return;
    }
    emitChange([...normalizedValues, normalized]);
    setResolved((prev) => ({
      ...prev,
      [normalized]: {
        ticker: normalized,
        corpName: item.corpName,
        corpCode: item.corpCode,
        highlight: item.highlight ?? item.latestReportName,
      },
    }));
    setQuery("");
  };

  const handleQuickSelect = (ticker: string, label?: string | null) => {
    const normalized = ticker.trim().toUpperCase();
    if (!normalized || normalizedValues.includes(normalized)) {
      return;
    }
    emitChange([...normalizedValues, normalized]);
    if (label) {
      setResolved((prev) => ({
        ...prev,
        [normalized]: {
          ticker: normalized,
          corpName: label,
        },
      }));
    }
  };

  const handleManualCommit = () => {
    if (suggestions.length > 0) {
      handleSelect(suggestions[0]);
      return;
    }
    const trimmed = query.trim();
    if (!trimmed) {
      return;
    }
    const normalized = trimmed.toUpperCase();
    if (normalizedValues.includes(normalized)) {
      setQuery("");
      return;
    }
    emitChange([...normalizedValues, normalized]);
    setQuery("");
  };

  const handleKeyDown: React.KeyboardEventHandler<HTMLInputElement> = (event) => {
    if (event.key === "Enter" || event.key === "Tab") {
      event.preventDefault();
      handleManualCommit();
      return;
    }
    if (event.key === "Backspace" && query.length === 0 && normalizedValues.length > 0) {
      event.preventDefault();
      const next = [...normalizedValues];
      const removed = next.pop();
      emitChange(next);
      if (removed) {
        setResolved((prev) => {
          const nextResolved = { ...prev };
          delete nextResolved[removed];
          return nextResolved;
        });
      }
    }
  };

  useEffect(() => {
    const missing = normalizedValues.filter((ticker) => !resolved[ticker]);
    if (missing.length === 0) {
      return;
    }
    let cancelled = false;
    const load = async () => {
      const results = await Promise.all(
        missing.map(async (ticker) => {
          try {
            return await resolveCompanyIdentifier(ticker);
          } catch {
            return null;
          }
        }),
      );
      if (cancelled) {
        return;
      }
      setResolved((prev) => {
        const next = { ...prev };
        missing.forEach((ticker, index) => {
          const item = results[index];
          if (item) {
            const resolvedTicker = (item.ticker ?? ticker).toUpperCase();
            next[resolvedTicker] = {
              ticker: resolvedTicker,
              corpName: item.corpName,
              corpCode: item.corpCode,
              highlight: item.highlight ?? item.latestReportName,
            };
          } else if (!next[ticker]) {
            next[ticker] = { ticker };
          }
        });
        return next;
      });
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [normalizedValues, resolved]);

  const activeSuggestions = useMemo(() => {
    if (!query.trim()) {
      return suggestions;
    }
    return suggestions.filter((item) => {
      const ticker = item.ticker?.toUpperCase();
      if (ticker && normalizedValues.includes(ticker)) {
        return false;
      }
      return true;
    });
  }, [query, suggestions, normalizedValues]);

  return (
    <div className="space-y-2">
      <div className="relative">
        <div
          className={clsx(
            "relative flex min-h-[2.75rem] flex-wrap items-center gap-1 rounded-lg border border-border-light bg-background-light px-3 py-1.5 transition-colors focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/40 dark:border-border-dark dark:bg-background-dark",
            disabled && "opacity-60",
          )}
        >
        {normalizedValues.map((ticker) => {
          const info = resolved[ticker];
          return (
            <span
              key={ticker}
              className="group flex items-center gap-2 rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary transition-colors dark:bg-primary.dark/15 dark:text-primary.dark"
            >
              <span className="flex flex-col leading-tight">
                <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                  {info?.corpName ?? ticker}
                </span>
                <span className="text-[10px] uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                  {ticker}
                </span>
              </span>
              <button
                type="button"
                onClick={() => handleRemove(ticker)}
                className="inline-flex h-4 w-4 items-center justify-center rounded-full text-primary/70 transition-all hover:scale-110 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 dark:text-primary.dark/70 dark:hover:text-primary.dark"
              >
                <X className="h-3.5 w-3.5" aria-hidden />
                <span className="sr-only">{ticker} 제거</span>
              </button>
            </span>
          );
        })}
        <input
          id={id}
          aria-label={ariaLabel}
          value={query}
          disabled={disabled}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setTimeout(() => setIsFocused(false), 120)}
          placeholder={placeholder}
          className="flex-1 min-w-[6rem] bg-transparent text-sm text-text-primaryLight placeholder:text-text-secondaryLight focus:outline-none dark:text-text-primaryDark dark:placeholder:text-text-secondaryDark"
        />
        {isFetching ? <Loader2 className="h-4 w-4 animate-spin text-primary dark:text-primary.dark" aria-hidden /> : null}
      </div>
        {isFocused && activeSuggestions.length > 0 ? (
          <ul className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-xl border border-border-light bg-background-cardLight p-1 text-sm shadow-lg dark:border-border-dark dark:bg-background-cardDark">
            {activeSuggestions.map((item, index) => {
              const ticker = item.ticker?.toUpperCase();
              const corpCode = item.corpCode?.toUpperCase();
              const alreadySelected = ticker ? normalizedValues.includes(ticker) : false;
              return (
                <li key={suggestionKey(item, index)} className="rounded-md">
                  <button
                    type="button"
                    disabled={alreadySelected}
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => handleSelect(item)}
                    className={clsx(
                      "flex w-full flex-col items-start gap-0.5 rounded-md px-3 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30",
                      alreadySelected
                        ? "cursor-not-allowed text-text-secondaryLight dark:text-text-secondaryDark"
                        : "hover:bg-primary/10 hover:text-primary dark:hover:bg-primary.dark/15",
                    )}
                  >
                    <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                      {item.corpName ?? ticker ?? corpCode ?? "알 수 없는 회사"}
                    </span>
                    <span className="text-[11px] uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                      {ticker ? `티커 ${ticker}` : null}
                      {ticker && corpCode ? " · " : ""}
                      {corpCode ? `법인코드 ${corpCode}` : null}
                    </span>
                    {item.highlight ? (
                      <span className="text-[11px] text-primary/80 dark:text-primary.dark/80">{item.highlight}</span>
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>
      {helperText ? (
        <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{helperText}</p>
      ) : null}

      {staticOptions.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">추천 티커:</span>
          {staticOptions.map((option) => {
            const ticker = option.ticker.trim().toUpperCase();
            const active = normalizedValues.includes(ticker);
            return (
              <button
                type="button"
                key={ticker}
                disabled={active}
                onClick={() => handleQuickSelect(ticker, option.label)}
                className={clsx(
                  "rounded-full border px-2 py-0.5 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40",
                  active
                    ? "cursor-not-allowed border-border-light/40 bg-border-light/40 text-text-secondaryLight dark:border-border-dark/40 dark:bg-border-dark/30 dark:text-text-secondaryDark"
                    : "border-border-light/70 text-text-secondaryLight hover:border-primary/50 hover:bg-primary/10 hover:text-primary dark:border-border-dark/70 dark:text-text-secondaryDark dark:hover:border-primary.dark/50 dark:hover:bg-primary.dark/10 dark:hover:text-primary.dark",
                )}
              >
                {option.label ? `${option.label} (${ticker})` : ticker}
              </button>
            );
          })}
        </div>
      ) : null}

      {isFocused && query.trim().length > 1 && activeSuggestions.length === 0 && !isFetching ? (
        <p className="rounded-md border border-dashed border-border-light px-3 py-2 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
          일치하는 회사를 찾지 못했습니다. 티커가 등록되어 있는지 확인해 주세요.
        </p>
      ) : null}
    </div>
  );
}
