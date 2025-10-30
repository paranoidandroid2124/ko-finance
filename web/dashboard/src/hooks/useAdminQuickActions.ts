"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  applyPlanQuickAdjust,
  fetchTossWebhookAudit,
  type PlanQuickAdjustPayload,
  type WebhookAuditEntry,
} from "@/lib/adminApi";
import { usePlanStore, type PlanContextPayload } from "@/store/planStore";

const TOSS_WEBHOOK_AUDIT_KEY = ["admin", "webhooks", "toss", "events"];

export const useTossWebhookAudit = (limit = 50) =>
  useQuery<WebhookAuditEntry[]>({
    queryKey: [...TOSS_WEBHOOK_AUDIT_KEY, limit],
    queryFn: () => fetchTossWebhookAudit(limit),
    staleTime: 30_000,
  });

export const usePlanQuickAdjust = () => {
  const setPlanFromServer = usePlanStore((state) => state.setPlanFromServer);
  const fetchPlan = usePlanStore((state) => state.fetchPlan);
  const queryClient = useQueryClient();

  return useMutation<PlanContextPayload, Error, PlanQuickAdjustPayload>({
    mutationFn: (payload) => applyPlanQuickAdjust(payload),
    onSuccess: async (planPayload) => {
      setPlanFromServer(planPayload);
      await fetchPlan().catch(() => undefined);
      void queryClient.invalidateQueries({ queryKey: TOSS_WEBHOOK_AUDIT_KEY });
    },
  });
};
