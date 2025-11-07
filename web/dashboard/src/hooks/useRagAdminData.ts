"use client";

import { useMemo } from "react";

import {
  useRagConfig,
  useRagReindexHistory,
  useRagReindexQueue,
  useRagSlaSummary,
  useTriggerRagReindex,
  useUpdateRagConfig,
  useRetryRagReindexQueue,
  useRemoveRagQueueEntry,
} from "@/hooks/useAdminConfig";
import { useToastStore } from "@/store/toastStore";

export const useRagAdminData = () => {
  const toast = useToastStore((state) => state.show);
  const ragConfigQuery = useRagConfig();
  const ragHistoryQuery = useRagReindexHistory();
  const ragQueueQuery = useRagReindexQueue();
  const ragSlaQuery = useRagSlaSummary();
  const updateConfigMutation = useUpdateRagConfig();
  const triggerReindexMutation = useTriggerRagReindex();
  const retryQueueMutation = useRetryRagReindexQueue();
  const removeQueueMutation = useRemoveRagQueueEntry();

  const queueEntries = useMemo(() => {
    const entries = ragQueueQuery.data?.entries ?? [];
    return [...entries].sort((a, b) => {
      const left = a.updatedAt ?? a.createdAt ?? "";
      const right = b.updatedAt ?? b.createdAt ?? "";
      return right.localeCompare(left);
    });
  }, [ragQueueQuery.data?.entries]);

  const queueSummary = ragQueueQuery.data?.summary ?? null;
  const historySummary = ragHistoryQuery.data?.summary ?? null;
  const slaSummary = ragSlaQuery.data ?? null;

  return {
    toast,
    ragConfigQuery,
    ragHistoryQuery,
    ragQueueQuery,
    ragSlaQuery,
    updateConfigMutation,
    triggerReindexMutation,
    retryQueueMutation,
    removeQueueMutation,
    queueEntries,
    queueSummary,
    historySummary,
    slaSummary,
  };
};

