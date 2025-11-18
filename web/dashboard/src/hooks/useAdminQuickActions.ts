"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  AdminUnauthorizedError,
  applyPlanQuickAdjust,
  fetchTossWebhookAudit,
  triggerQuickAction,
  updateUserPlanTier,
  type AdminQuickActionId,
  type AdminQuickActionPayload,
  type AdminQuickActionResult,
  type AdminUserPlanUpdatePayload,
  type AdminUserPlanUpdateResult,
  type PlanQuickAdjustPayload,
  type WebhookAuditEntry,
} from "@/lib/adminApi";
import { usePlanStore, type PlanContextPayload } from "@/store/planStore";

const TOSS_WEBHOOK_AUDIT_KEY = ["admin", "webhooks", "toss", "events"];

type TossWebhookAuditOptions = {
  enabled?: boolean;
};

export const useTossWebhookAudit = (limit = 50, options?: TossWebhookAuditOptions) =>
  useQuery<WebhookAuditEntry[], Error>({
    queryKey: [...TOSS_WEBHOOK_AUDIT_KEY, limit],
    queryFn: () => fetchTossWebhookAudit(limit),
    staleTime: 30_000,
    enabled: options?.enabled ?? true,
    retry: (failureCount, error) => {
      if (error instanceof AdminUnauthorizedError) {
        return false;
      }
      return failureCount < 2;
    },
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

export const useUpdateUserPlanTier = () =>
  useMutation<AdminUserPlanUpdateResult, Error, AdminUserPlanUpdatePayload>({
    mutationFn: (payload) => updateUserPlanTier(payload),
  });

type QuickActionMutationInput = AdminQuickActionPayload & {
  action: AdminQuickActionId;
};

export const useTriggerQuickAction = () =>
  useMutation<AdminQuickActionResult, Error, QuickActionMutationInput>({
    mutationFn: ({ action, actor, note }) =>
      triggerQuickAction(action, {
        actor,
        note: note ?? null,
      }),
  });
