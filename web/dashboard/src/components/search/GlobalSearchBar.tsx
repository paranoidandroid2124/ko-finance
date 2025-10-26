"use client";

import { useId } from "react";

type GlobalSearchBarProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onOpenCommand?: () => void;
  placeholder?: string;
  isLoading?: boolean;
};

export function GlobalSearchBar({
  value,
  onChange,
  onSubmit,
  onOpenCommand,
  placeholder = "검색어를 입력하세요 (예: 공시, 뉴스, 섹터)",
  isLoading = false,
}: GlobalSearchBarProps) {
  const inputId = useId();

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
      className="flex flex-col gap-3 rounded-2xl border border-border-light bg-background-cardLight p-4 shadow-card transition-motion-medium hover:shadow-lg dark:border-border-dark dark:bg-background-cardDark"
    >
      <div className="flex items-center justify-between">
        <label htmlFor={inputId} className="text-sm font-semibold text-text-secondaryLight dark:text-text-secondaryDark">
          글로벌 검색
        </label>
        <button
          type="button"
          onClick={onOpenCommand}
          className="inline-flex items-center gap-2 rounded-lg border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition-motion-fast hover:border-primary hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
        >
          <span className="hidden sm:inline">커맨드 팔레트</span>
          <span className="flex items-center gap-1 rounded bg-background-light px-1.5 py-0.5 text-[11px] dark:bg-background-dark">
            ⌘ <span className="text-xs">K</span>
          </span>
        </button>
      </div>
      <div className="flex items-center gap-3 rounded-xl border border-border-light bg-background-light/80 px-4 py-2 shadow-sm focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20 dark:border-border-dark dark:bg-background-dark/70">
        <svg
          aria-hidden="true"
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          className="text-text-secondaryLight dark:text-text-secondaryDark"
        >
          <path
            d="M10.5 4a6.5 6.5 0 015.17 10.5l3.66 3.66a1 1 0 01-1.42 1.42l-3.66-3.66A6.5 6.5 0 1110.5 4zm0 2a4.5 4.5 0 100 9 4.5 4.5 0 000-9z"
            fill="currentColor"
          />
        </svg>
        <input
          id={inputId}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          className="h-10 w-full bg-transparent text-sm text-text-primaryLight outline-none placeholder:text-text-secondaryLight dark:text-text-primaryDark dark:placeholder:text-text-secondaryDark"
        />
        <button
          type="submit"
          disabled={!value.trim() || isLoading}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-white transition-motion-fast hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60"
        >
          검색
          {isLoading ? (
            <span className="h-2 w-2 animate-spin rounded-full border border-white/70 border-t-transparent" aria-hidden />
          ) : null}
        </button>
      </div>
      <div className="flex flex-wrap gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
        <span className="rounded-full border border-border-light px-2 py-1 dark:border-border-dark">공시</span>
        <span className="rounded-full border border-border-light px-2 py-1 dark:border-border-dark">뉴스</span>
        <span className="rounded-full border border-border-light px-2 py-1 dark:border-border-dark">섹터</span>
        <span className="rounded-full border border-border-light px-2 py-1 dark:border-border-dark">감성·수익률</span>
      </div>
    </form>
  );
}
