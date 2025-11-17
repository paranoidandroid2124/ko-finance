"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  useSearchResults,
  type SearchResult,
  type SearchResultType,
  type SearchTotals,
} from "@/hooks/useSearchResults";
import type { SearchFilterState } from "../_components/SearchFiltersSidebar";

const SEARCH_LIMIT = 20;

type ResultMap = Record<SearchResultType, SearchResult[]>;
type OffsetMap = Record<SearchResultType, number>;

type InitialSearchState = {
  query: string;
  type: SearchResultType;
  dateFrom: string;
  dateTo: string;
  sectors: string[];
};

const createInitialOffsets = (): OffsetMap => ({
  filing: 0,
  news: 0,
  table: 0,
  chart: 0,
});

const createEmptyResults = (): ResultMap => ({
  filing: [],
  news: [],
  table: [],
  chart: [],
});

const computeDateRange = (filters: SearchFilterState) => {
  if (filters.datePreset === "custom") {
    return {
      from: filters.customFrom || undefined,
      to: filters.customTo || undefined,
    };
  }
  const days = filters.datePreset === "7d" ? 7 : filters.datePreset === "30d" ? 30 : 90;
  const end = new Date();
  const start = new Date(end);
  start.setDate(end.getDate() - (days - 1));
  return {
    from: start.toISOString(),
    to: end.toISOString(),
  };
};

const buildInitialFilters = (initial: InitialSearchState): SearchFilterState => {
  if (initial.dateFrom || initial.dateTo) {
    return {
      datePreset: "custom",
      customFrom: initial.dateFrom,
      customTo: initial.dateTo,
      sectors: initial.sectors,
    };
  }
  return {
    datePreset: "7d",
    customFrom: "",
    customTo: "",
    sectors: initial.sectors,
  };
};

export type UseSearchControllerValue = {
  searchInput: string;
  setSearchInput: (value: string) => void;
  searchQuery: string;
  hasQuery: boolean;
  filters: SearchFilterState;
  activeFilterChips: string[];
  activeType: SearchResultType;
  searchResults: SearchResult[];
  totals: SearchTotals | null;
  isFetching: boolean;
  isError: boolean;
  canLoadMore: boolean;
  handleSearchSubmit: () => void;
  handleQuickSearch: (value: string) => void;
  handleTypeChange: (type: SearchResultType) => void;
  handleLoadMore: () => void;
  handleFilterChange: (next: SearchFilterState) => void;
};

export function useSearchController(): UseSearchControllerValue {
  const router = useRouter();
  const params = useSearchParams();

  const initialStateRef = useRef<InitialSearchState | null>(null);
  if (!initialStateRef.current) {
    const sectors = params ? params.getAll("sector") : [];
    initialStateRef.current = {
      query: params?.get("q") ?? "",
      type: (params?.get("type") as SearchResultType) ?? "filing",
      dateFrom: params?.get("date_from") ?? "",
      dateTo: params?.get("date_to") ?? "",
      sectors,
    };
  }
  const initialState = initialStateRef.current!;

  const [searchInput, setSearchInput] = useState(initialState.query);
  const [searchQuery, setSearchQuery] = useState(initialState.query);
  const [activeType, setActiveType] = useState<SearchResultType>(initialState.type);
  const [offsetByType, setOffsetByType] = useState<OffsetMap>(createInitialOffsets);
  const [resultsByType, setResultsByType] = useState<ResultMap>(createEmptyResults);
  const [totalsState, setTotalsState] = useState<SearchTotals | null>(null);
  const [filters, setFilters] = useState<SearchFilterState>(() => buildInitialFilters(initialState));

  const resolvedRange = useMemo(() => computeDateRange(filters), [filters]);
  const filterSignature = useMemo(
    () => JSON.stringify({ ...filters, resolvedFrom: resolvedRange.from, resolvedTo: resolvedRange.to }),
    [filters, resolvedRange],
  );

  const searchResultsData = useSearchResults(searchQuery, activeType, SEARCH_LIMIT, offsetByType[activeType], {
    dateFrom: resolvedRange.from,
    dateTo: resolvedRange.to,
    sectors: filters.sectors,
  });
  const { data: searchData, isFetching, isError, refetch } = searchResultsData;

  const searchTotals = totalsState ?? searchData?.totals ?? null;
  const searchResults = resultsByType[activeType];
  const hasQuery = Boolean(searchQuery.trim());

  const resetResultState = useCallback(() => {
    setResultsByType(createEmptyResults());
    setTotalsState(null);
    setOffsetByType(createInitialOffsets());
  }, []);

  useEffect(() => {
    resetResultState();
  }, [filterSignature, resetResultState]);

  useEffect(() => {
    if (!hasQuery) {
      resetResultState();
    }
  }, [hasQuery, resetResultState]);

  useEffect(() => {
    if (!hasQuery || !searchData) {
      return;
    }
    setTotalsState(searchData.totals);
    setResultsByType((previous) => {
      const activeOffset = offsetByType[activeType];
      const baseline = activeOffset === 0 ? [] : previous[activeType] ?? [];
      const merged = activeOffset === 0 ? searchData.results : [...baseline, ...searchData.results];
      const deduped: SearchResult[] = [];
      const seen = new Set<string>();
      for (const item of merged) {
        if (seen.has(item.id)) {
          continue;
        }
        seen.add(item.id);
        deduped.push(item);
      }
      return { ...previous, [activeType]: deduped };
    });
  }, [searchData, hasQuery, activeType, offsetByType]);

  const syncUrl = useCallback(
    (nextQuery: string, nextType: SearchResultType, nextFilters: SearchFilterState) => {
      const range = computeDateRange(nextFilters);
      const nextParams = new URLSearchParams();
      if (nextQuery.trim()) {
        nextParams.set("q", nextQuery.trim());
      }
      nextParams.set("type", nextType);
      if (range.from) {
        nextParams.set("date_from", range.from);
      }
      if (range.to) {
        nextParams.set("date_to", range.to);
      }
      nextFilters.sectors.forEach((sector) => nextParams.append("sector", sector));
      const qs = nextParams.toString();
      router.replace(qs ? `/search?${qs}` : "/search");
    },
    [router],
  );

  const handleQuickSearch = useCallback(
    (rawValue: string) => {
      const trimmed = rawValue.trim();
      if (!trimmed) {
        setSearchInput("");
        setSearchQuery("");
        resetResultState();
        syncUrl("", "filing", filters);
        return;
      }
      setSearchInput(trimmed);
      if (trimmed !== searchQuery) {
        setActiveType("filing");
        resetResultState();
        setSearchQuery(trimmed);
        syncUrl(trimmed, "filing", filters);
      } else {
        void refetch();
      }
    },
    [filters, refetch, resetResultState, searchQuery, syncUrl],
  );

  const handleSearchSubmit = useCallback(() => {
    handleQuickSearch(searchInput);
  }, [handleQuickSearch, searchInput]);

  const handleTypeChange = useCallback(
    (type: SearchResultType) => {
      setActiveType(type);
      if (!resultsByType[type] || resultsByType[type].length === 0) {
        setOffsetByType((previous) => ({ ...previous, [type]: 0 }));
      }
      if (hasQuery) {
        syncUrl(searchQuery, type, filters);
      }
    },
    [filters, hasQuery, resultsByType, searchQuery, syncUrl],
  );

  const handleLoadMore = useCallback(() => {
    if (!hasQuery) {
      return;
    }
    const totals = searchTotals;
    const totalForActive = totals?.[activeType] ?? 0;
    if (totalForActive <= searchResults.length) {
      return;
    }
    setOffsetByType((previous) => ({
      ...previous,
      [activeType]: previous[activeType] + SEARCH_LIMIT,
    }));
  }, [activeType, hasQuery, searchResults.length, searchTotals]);

  const handleFilterChange = useCallback(
    (next: SearchFilterState) => {
      setFilters(next);
      if (hasQuery) {
        syncUrl(searchQuery, activeType, next);
      }
    },
    [activeType, hasQuery, searchQuery, syncUrl],
  );

  const activeFilterChips = useMemo(() => {
    const chips: string[] = [];
    if (filters.datePreset === "custom" && filters.customFrom && filters.customTo) {
      chips.push(`기간: ${filters.customFrom} ~ ${filters.customTo}`);
    } else {
      const label =
        filters.datePreset === "7d"
          ? "최근 7일"
          : filters.datePreset === "30d"
            ? "최근 30일"
            : filters.datePreset === "90d"
              ? "최근 90일"
              : "사용자 지정";
      chips.push(label);
    }
    if (filters.sectors.length > 0) {
      chips.push(`섹터: ${filters.sectors.join(", ")}`);
    }
    return chips;
  }, [filters]);

  const canLoadMore = useMemo(() => {
    if (!hasQuery) {
      return false;
    }
    const totals = searchTotals;
    const totalForActive = totals?.[activeType] ?? 0;
    return totalForActive > searchResults.length;
  }, [activeType, hasQuery, searchResults.length, searchTotals]);

  return {
    searchInput,
    setSearchInput,
    searchQuery,
    hasQuery,
    filters,
    activeFilterChips,
    activeType,
    searchResults,
    totals: searchTotals,
    isFetching,
    isError,
    canLoadMore,
    handleSearchSubmit,
    handleQuickSearch,
    handleTypeChange,
    handleLoadMore,
    handleFilterChange,
  };
}
