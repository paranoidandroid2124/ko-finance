"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchDailyBriefRuns,
  triggerDailyBrief,
  type DailyBriefGenerateRequest,
  type DailyBriefGenerateResponse,
  type DailyBriefRun,
} from "@/lib/reportsApi";

const DAILY_BRIEF_QUERY_KEY = ["reports", "daily-brief"];

export const useDailyBriefRuns = (limit = 10) =>
  useQuery<DailyBriefRun[]>({
    queryKey: [...DAILY_BRIEF_QUERY_KEY, limit],
    queryFn: () => fetchDailyBriefRuns(limit),
    staleTime: 60_000,
  });

export const useGenerateDailyBrief = () => {
  const queryClient = useQueryClient();
  return useMutation<DailyBriefGenerateResponse, unknown, DailyBriefGenerateRequest>({
    mutationFn: (payload) => triggerDailyBrief(payload),
    onSuccess: (_data, _variables, _context) => {
      void queryClient.invalidateQueries({ queryKey: DAILY_BRIEF_QUERY_KEY });
    },
  });
};
