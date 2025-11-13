"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import {
  fetchTableSummaries,
  fetchTableDetail,
  type TableListFilters,
  type TableListResponse,
  type TableDetailResponse,
} from "@/lib/tableExplorerApi";

export const useTableExplorerList = (filters: TableListFilters) =>
  useQuery<TableListResponse, Error>({
    queryKey: ["table-explorer", "list", filters],
    queryFn: () => fetchTableSummaries(filters),
    placeholderData: keepPreviousData,
  });

export const useTableExplorerDetail = (tableId: string | null, enabled = true) =>
  useQuery<TableDetailResponse, Error>({
    queryKey: ["table-explorer", "detail", tableId],
    queryFn: () => {
      if (!tableId) {
        throw new Error("tableId가 필요합니다.");
      }
      return fetchTableDetail(tableId);
    },
    enabled: Boolean(tableId) && enabled,
    staleTime: 30_000,
  });

export type { TableListFilters, TableListResponse, TableDetailResponse } from "@/lib/tableExplorerApi";
