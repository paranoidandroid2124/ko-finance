"use client";

import { useQuery } from "@tanstack/react-query";
import { resolveApiBase } from "@/lib/apiBase";

export type BoardSummary = {
  id: string;
  name: string;
  type: "watchlist" | "sector" | "theme";
  description?: string | null;
  tickers: string[];
  eventCount: number;
  recentAlerts: number;
  channels: string[];
  updatedAt?: string | null;
};

export type BoardEntry = {
  ticker: string;
  corpName?: string | null;
  sector?: string | null;
  eventCount: number;
  lastHeadline?: string | null;
  lastEventAt?: string | null;
  sentiment?: number | null;
  alertStatus?: string | null;
  targetUrl?: string | null;
};

export type BoardTimelineItem = {
  id: string;
  headline: string;
  summary?: string | null;
  channel?: string | null;
  sentiment?: number | null;
  deliveredAt?: string | null;
  url?: string | null;
};

export type BoardDetail = {
  board: BoardSummary;
  entries: BoardEntry[];
  timeline: BoardTimelineItem[];
};

type BoardListResponse = {
  boards: BoardSummary[];
};

type BoardListParams = {
  ticker?: string;
};

const fetchBoards = async (params?: BoardListParams): Promise<BoardSummary[]> => {
  const baseUrl = resolveApiBase();
  const query = new URLSearchParams();
  const normalizedTicker = params?.ticker?.trim().toUpperCase();
  if (normalizedTicker) {
    query.set("ticker", normalizedTicker);
  }
  const qs = query.toString();
  const response = await fetch(`${baseUrl}/api/v1/boards${qs ? `?${qs}` : ""}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("보드 목록을 불러오지 못했습니다.");
  }
  const payload = (await response.json()) as BoardListResponse;
  return payload.boards ?? [];
};

const fetchBoardDetail = async (boardId: string): Promise<BoardDetail> => {
  const response = await fetch(`${resolveApiBase()}/api/v1/boards/${boardId}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("보드 세부 정보를 불러오지 못했습니다.");
  }
  return (await response.json()) as BoardDetail;
};

type UseBoardsOptions = {
  ticker?: string | null;
  enabled?: boolean;
};

export function useBoards(options?: UseBoardsOptions) {
  const normalizedTicker = options?.ticker?.trim().toUpperCase();
  return useQuery({
    queryKey: ["boards", "list", normalizedTicker ?? null],
    queryFn: () => fetchBoards(normalizedTicker ? { ticker: normalizedTicker } : undefined),
    enabled: (options?.enabled ?? true) && (options?.ticker ? options.ticker.trim().length > 0 : true),
    staleTime: 60_000,
  });
}

export function useBoardDetail(boardId: string | null) {
  return useQuery({
    queryKey: ["boards", "detail", boardId],
    queryFn: () => fetchBoardDetail(boardId ?? ""),
    enabled: Boolean(boardId),
    staleTime: 30_000,
  });
}
