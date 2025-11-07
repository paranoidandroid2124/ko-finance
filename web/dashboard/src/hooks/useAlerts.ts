"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertRuleCreatePayload,
  AlertRuleListResponse,
  AlertRuleUpdatePayload,
  createAlertRule,
  dispatchWatchlistDigest,
  deleteAlertRule,
  fetchAlertRules,
  fetchAlertChannelSchema,
  type AlertChannelSchemaResponse,
  fetchWatchlistRadar,
  fetchWatchlistRuleDetail,
  type WatchlistDispatchRequest,
  type WatchlistDispatchResponse,
  type WatchlistRadarResponse,
  type WatchlistRadarRequest,
  type WatchlistRuleDetailResponse,
  updateAlertRule,
} from "@/lib/alertsApi";

const ALERT_RULES_QUERY_KEY = ["alerts", "rules"];
const ALERT_CHANNEL_SCHEMA_QUERY_KEY = ["alerts", "channel-schema"];

export const useAlertRules = () =>
  useQuery<AlertRuleListResponse>({
    queryKey: ALERT_RULES_QUERY_KEY,
    queryFn: fetchAlertRules,
    staleTime: 30_000,
  });

export const useCreateAlertRule = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AlertRuleCreatePayload) => createAlertRule(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ALERT_RULES_QUERY_KEY });
    },
  });
};

export const useUpdateAlertRule = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: AlertRuleUpdatePayload }) => updateAlertRule(id, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ALERT_RULES_QUERY_KEY });
    },
  });
};

export const useDeleteAlertRule = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteAlertRule(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ALERT_RULES_QUERY_KEY });
    },
  });
};

export const useAlertChannelSchema = () =>
  useQuery<AlertChannelSchemaResponse>({
    queryKey: ALERT_CHANNEL_SCHEMA_QUERY_KEY,
    queryFn: fetchAlertChannelSchema,
    staleTime: 300_000,
  });

export const useWatchlistRadar = (params: WatchlistRadarRequest = {}) => {
  const {
    windowMinutes = 1440,
    limit = 20,
    channels = [],
    eventTypes = [],
    tickers = [],
    ruleTags = [],
    minSentiment = null,
    maxSentiment = null,
    query,
    windowStart,
    windowEnd,
  } = params;

  const queryKey = [
    "watchlist",
    "radar",
    windowMinutes,
    limit,
    channels.join("|"),
    eventTypes.join("|"),
    tickers.join("|"),
    ruleTags.join("|"),
    minSentiment ?? "",
    maxSentiment ?? "",
    query ?? "",
    windowStart ?? "",
    windowEnd ?? "",
  ];

  const payload: WatchlistRadarRequest = {
    windowMinutes,
    limit,
    channels: [...channels],
    eventTypes: [...eventTypes],
    tickers: [...tickers],
    ruleTags: [...ruleTags],
    minSentiment,
    maxSentiment,
    query,
    windowStart,
    windowEnd,
  };

  return useQuery<WatchlistRadarResponse>({
    queryKey,
    queryFn: () => fetchWatchlistRadar(payload),
    staleTime: 60_000,
  });
};

export const useWatchlistRuleDetail = (
  ruleId: string | null,
  options: { recentLimit?: number } = {},
) =>
  useQuery<WatchlistRuleDetailResponse>({
    queryKey: ["watchlist", "rule-detail", ruleId, options.recentLimit ?? 5],
    enabled: Boolean(ruleId),
    queryFn: () => {
      if (!ruleId) {
        // react-query will skip when enabled=false, but guard for type safety.
        return Promise.reject(new Error("ruleId is required"));
      }
      return fetchWatchlistRuleDetail(ruleId, options);
    },
    staleTime: 30_000,
  });

export const useDispatchWatchlistDigest = () =>
  useMutation<WatchlistDispatchResponse, unknown, WatchlistDispatchRequest>({
    mutationFn: (payload) => dispatchWatchlistDigest(payload),
  });
