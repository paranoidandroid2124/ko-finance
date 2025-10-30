"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertRuleCreatePayload,
  AlertRuleListResponse,
  AlertRuleUpdatePayload,
  createAlertRule,
  deleteAlertRule,
  fetchAlertRules,
  fetchAlertChannelSchema,
  type AlertChannelSchemaResponse,
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
