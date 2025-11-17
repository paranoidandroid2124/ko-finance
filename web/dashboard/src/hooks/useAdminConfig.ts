"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  AdminUnauthorizedError,
  evaluateGuardrailSample,
  fetchGuardrailPolicy,
  fetchGuardrailSamples,
  fetchLlmProfiles,
  fetchNewsPipeline,
  fetchOpsApiKeys,
  fetchOpsAlertChannels,
  fetchAlertTemplates,
  generateAlertSampleMetadata,
  fetchOpsRunHistory,
  fetchOpsSchedules,
  fetchAlertPresetUsage,
  fetchRagConfig,
  fetchRagReindexHistory,
  fetchRagReindexQueue,
  fetchRagSlaSummary,
  fetchSystemPrompts,
  fetchUiUxSettings,
  fetchAlertPresetUsage,
  triggerOpsSchedule,
  triggerRagReindex,
  retryRagReindexQueue,
  rotateLangfuseKeys,
  createOpsAlertChannel,
  previewOpsAlertChannel,
  updateOpsAlertChannelStatus,
  updateGuardrailPolicy,
  updateGuardrailBookmark,
  updateNewsPipeline,
  updateOpsApiKeys,
  updateOpsAlertChannels,
  updateRagConfig,
  updateSystemPrompt,
  updateUiUxSettings,
  upsertLlmProfile,
  type AdminGuardrailEvaluatePayload,
  type AdminGuardrailEvaluateResult,
  type AdminGuardrailPolicyResponse,
  type AdminGuardrailSample,
  type AdminGuardrailSampleList,
  type AdminGuardrailBookmarkPayload,
  type AdminGuardrailPolicyUpdatePayload,
  type AdminLlmProfileList,
  type AdminLlmProfileUpsertPayload,
  type AdminLlmProfileUpsertResult,
  type AdminOpsApiKeyResponse,
  type AdminOpsApiKeyUpdatePayload,
  type AdminOpsAlertChannelCreatePayload,
  type AdminOpsAlertChannelResponse,
  type AdminOpsAlertChannelPreviewPayload,
  type AdminOpsAlertChannelPreviewResult,
  type AdminOpsAlertChannelStatusPayload,
  type AdminOpsAlertChannelUpdatePayload,
  type AdminOpsNewsPipelineResponse,
  type AdminOpsNewsPipelineUpdatePayload,
  type AdminOpsRunHistoryResponse,
  type AdminOpsTemplateList,
  type AdminOpsSampleMetadataPayload,
  type AdminOpsSampleMetadataResult,
  type AdminOpsScheduleList,
  type AdminOpsTriggerPayload,
  type AdminOpsTriggerResult,
  type AdminAlertPresetUsageResponse,
  type AdminRagConfig,
  type AdminUiUxSettingsResponse,
  type AdminUiUxSettingsUpdatePayload,
  type AdminRagConfigUpdatePayload,
  deleteRagReindexQueueEntry,
  type AdminRagReindexHistory,
  type AdminRagReindexPayload,
  type AdminRagReindexResult,
  type AdminRagReindexQueue,
  type AdminRagReindexRetryPayload,
  type AdminRagReindexRetryResult,
  type AdminRagSlaResponse,
  type AdminSystemPrompt,
  type AdminSystemPromptList,
  type AdminSystemPromptUpdatePayload,
  type PromptChannel,
} from "@/lib/adminApi";

const shouldRetry = (failureCount: number, error: unknown) => {
  if (error instanceof AdminUnauthorizedError) {
    return false;
  }
  return failureCount < 2;
};

export const ADMIN_LLM_PROFILES_KEY = ["admin", "llm", "profiles"] as const;
export const ADMIN_SYSTEM_PROMPTS_KEY = ["admin", "llm", "prompts"] as const;
export const ADMIN_GUARDRAIL_SAMPLES_KEY = ["admin", "llm", "guardrails", "samples"] as const;
export const ADMIN_GUARDRAIL_POLICY_KEY = ["admin", "llm", "guardrails", "policy"] as const;
export const ADMIN_GUARDRAIL_EVAL_KEY = ["admin", "llm", "guardrails", "evaluate"] as const;
export const ADMIN_UI_UX_SETTINGS_KEY = ["admin", "ui", "settings"] as const;
export const ADMIN_RAG_CONFIG_KEY = ["admin", "rag", "config"] as const;
export const ADMIN_RAG_REINDEX_KEY = ["admin", "rag", "reindex"] as const;
export const ADMIN_RAG_REINDEX_HISTORY_KEY = ["admin", "rag", "reindexHistory"] as const;
export const ADMIN_RAG_REINDEX_QUEUE_KEY = ["admin", "rag", "reindexQueue"] as const;
export const ADMIN_RAG_SLA_SUMMARY_KEY = ["admin", "rag", "slaSummary"] as const;
export const ADMIN_OPS_SCHEDULES_KEY = ["admin", "ops", "schedules"] as const;
export const ADMIN_OPS_NEWS_PIPELINE_KEY = ["admin", "ops", "newsPipeline"] as const;
export const ADMIN_OPS_API_KEYS_KEY = ["admin", "ops", "apiKeys"] as const;
export const ADMIN_OPS_RUN_HISTORY_KEY = ["admin", "ops", "runHistory"] as const;
export const ADMIN_ALERT_TEMPLATES_KEY = ["admin", "ops", "alertTemplates"] as const;
export const ADMIN_OPS_ALERT_CHANNELS_KEY = ["admin", "ops", "alertChannels"] as const;
export const ADMIN_ALERT_PRESET_USAGE_KEY = ["admin", "ops", "alertPresets", "usage"] as const;

export const useLlmProfiles = (enabled = true) =>
  useQuery<AdminLlmProfileList, Error>({
    queryKey: ADMIN_LLM_PROFILES_KEY,
    queryFn: fetchLlmProfiles,
    enabled,
    staleTime: 30_000,
    retry: shouldRetry,
  });

export const useUpsertLlmProfile = () => {
  const queryClient = useQueryClient();
  return useMutation<AdminLlmProfileUpsertResult, Error, { name: string; payload: AdminLlmProfileUpsertPayload }>({
    mutationFn: ({ name, payload }) => upsertLlmProfile(name, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ADMIN_LLM_PROFILES_KEY });
    },
  });
};

export const useSystemPrompts = (channel?: PromptChannel, enabled = true) =>
  useQuery<AdminSystemPromptList, Error>({
    queryKey: [...ADMIN_SYSTEM_PROMPTS_KEY, channel ?? "all"],
    queryFn: () => fetchSystemPrompts(channel),
    enabled,
    staleTime: 30_000,
    retry: shouldRetry,
  });

export const useUpdateSystemPrompt = () => {
  const queryClient = useQueryClient();
  return useMutation<AdminSystemPrompt, Error, AdminSystemPromptUpdatePayload>({
    mutationFn: (payload) => updateSystemPrompt(payload),
    onSuccess: async (_data, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ADMIN_SYSTEM_PROMPTS_KEY }),
        queryClient.invalidateQueries({ queryKey: [...ADMIN_SYSTEM_PROMPTS_KEY, variables.channel] }),
      ]);
    },
  });
};

export const useGuardrailPolicy = (enabled = true) =>
  useQuery<AdminGuardrailPolicyResponse, Error>({
    queryKey: ADMIN_GUARDRAIL_POLICY_KEY,
    queryFn: fetchGuardrailPolicy,
    enabled,
    staleTime: 30_000,
    retry: shouldRetry,
  });

export const useUpdateGuardrailPolicy = () => {
  const queryClient = useQueryClient();
  return useMutation<AdminGuardrailPolicyResponse, Error, AdminGuardrailPolicyUpdatePayload>({
    mutationFn: (payload) => updateGuardrailPolicy(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ADMIN_GUARDRAIL_POLICY_KEY });
    },
  });
};

export const useUiUxSettings = (enabled = true) =>
  useQuery<AdminUiUxSettingsResponse, Error>({
    queryKey: ADMIN_UI_UX_SETTINGS_KEY,
    queryFn: fetchUiUxSettings,
    enabled,
    staleTime: 30_000,
    retry: shouldRetry,
  });

export const useUpdateUiUxSettings = () => {
  const queryClient = useQueryClient();
  return useMutation<AdminUiUxSettingsResponse, Error, AdminUiUxSettingsUpdatePayload>({
    mutationFn: (payload) => updateUiUxSettings(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ADMIN_UI_UX_SETTINGS_KEY });
    },
  });
};

export const useEvaluateGuardrail = () =>
  useMutation<AdminGuardrailEvaluateResult, Error, AdminGuardrailEvaluatePayload>({
    mutationFn: (payload) => evaluateGuardrailSample(payload),
  });

export const useRagConfig = (enabled = true) =>
  useQuery<AdminRagConfig, Error>({
    queryKey: ADMIN_RAG_CONFIG_KEY,
    queryFn: fetchRagConfig,
    enabled,
    staleTime: 60_000,
    retry: shouldRetry,
  });

export const useUpdateRagConfig = () => {
  const queryClient = useQueryClient();
  return useMutation<AdminRagConfig, Error, AdminRagConfigUpdatePayload>({
    mutationFn: (payload) => updateRagConfig(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ADMIN_RAG_CONFIG_KEY });
    },
  });
};

export const useGuardrailSamples = (params?: { limit?: number; search?: string; bookmarked?: boolean | null }) =>
  useQuery<AdminGuardrailSampleList, Error>({
    queryKey: [...ADMIN_GUARDRAIL_SAMPLES_KEY, params ?? {}],
    queryFn: () => fetchGuardrailSamples(params),
    staleTime: 10_000,
    retry: shouldRetry,
  });

export const useUpdateGuardrailBookmark = () => {
  const queryClient = useQueryClient();
  return useMutation<AdminGuardrailSample, Error, { sampleId: string; payload: AdminGuardrailBookmarkPayload }>(
    {
      mutationFn: ({ sampleId, payload }) => updateGuardrailBookmark(sampleId, payload),
      onSuccess: async () => {
        await queryClient.invalidateQueries({ queryKey: ADMIN_GUARDRAIL_SAMPLES_KEY });
      },
    },
  );
};


export const useTriggerRagReindex = () => {
  const queryClient = useQueryClient();
  return useMutation<AdminRagReindexResult, Error, AdminRagReindexPayload>({
    mutationFn: (payload) => triggerRagReindex(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ADMIN_RAG_CONFIG_KEY });
      await queryClient.invalidateQueries({ queryKey: ADMIN_RAG_REINDEX_KEY });
      await queryClient.invalidateQueries({ queryKey: ADMIN_RAG_REINDEX_HISTORY_KEY });
      await queryClient.invalidateQueries({ queryKey: ADMIN_RAG_REINDEX_QUEUE_KEY });
      await queryClient.invalidateQueries({ queryKey: ADMIN_RAG_SLA_SUMMARY_KEY });
    },
  });
};

export const useRagReindexHistory = (
  enabled = true,
  params?: { status?: string[]; q?: string; limit?: number },
) =>
  useQuery<AdminRagReindexHistory, Error>({
    queryKey: [...ADMIN_RAG_REINDEX_HISTORY_KEY, params ?? {}],
    queryFn: () => fetchRagReindexHistory(params),
    enabled,
    staleTime: 30_000,
    refetchInterval: enabled ? 10_000 : false,
    retry: shouldRetry,
  });

export const useRagReindexQueue = (
  enabled = true,
  params?: { status?: string[]; q?: string },
) =>
  useQuery<AdminRagReindexQueue, Error>({
    queryKey: [...ADMIN_RAG_REINDEX_QUEUE_KEY, params ?? {}],
    queryFn: () => fetchRagReindexQueue(params),
    enabled,
    staleTime: 30_000,
    refetchInterval: enabled ? 10_000 : false,
    retry: shouldRetry,
  });

export const useRagSlaSummary = (enabled = true, rangeDays = 7) =>
  useQuery<AdminRagSlaResponse, Error>({
    queryKey: [...ADMIN_RAG_SLA_SUMMARY_KEY, rangeDays],
    queryFn: () => fetchRagSlaSummary(rangeDays),
    enabled,
    staleTime: 60_000,
    refetchInterval: enabled ? 60_000 : false,
    retry: shouldRetry,
  });

export const useRetryRagReindexQueue = () => {
  const queryClient = useQueryClient();
  return useMutation<AdminRagReindexRetryResult, Error, AdminRagReindexRetryPayload>({
    mutationFn: (payload) => retryRagReindexQueue(payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ADMIN_RAG_REINDEX_HISTORY_KEY }),
        queryClient.invalidateQueries({ queryKey: ADMIN_RAG_REINDEX_QUEUE_KEY }),
        queryClient.invalidateQueries({ queryKey: ADMIN_RAG_SLA_SUMMARY_KEY }),
      ]);
    },
  });
};

export const useRemoveRagQueueEntry = () => {
  const queryClient = useQueryClient();
  return useMutation<AdminRagReindexRetryResult, Error, string>({
    mutationFn: (queueId) => deleteRagReindexQueueEntry(queueId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ADMIN_RAG_REINDEX_QUEUE_KEY }),
        queryClient.invalidateQueries({ queryKey: ADMIN_RAG_REINDEX_HISTORY_KEY }),
        queryClient.invalidateQueries({ queryKey: ADMIN_RAG_SLA_SUMMARY_KEY }),
      ]);
    },
  });
};

export const useOpsSchedules = (enabled = true) =>
  useQuery<AdminOpsScheduleList, Error>({
    queryKey: ADMIN_OPS_SCHEDULES_KEY,
    queryFn: fetchOpsSchedules,
    enabled,
    staleTime: 30_000,
    retry: shouldRetry,
  });

export const useTriggerOpsSchedule = () => {
  const queryClient = useQueryClient();
  return useMutation<AdminOpsTriggerResult, Error, { jobId: string; payload: AdminOpsTriggerPayload }>({
    mutationFn: ({ jobId, payload }) => triggerOpsSchedule(jobId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ADMIN_OPS_SCHEDULES_KEY });
      await queryClient.invalidateQueries({ queryKey: ADMIN_OPS_RUN_HISTORY_KEY });
    },
  });
};

export const useNewsPipeline = (enabled = true) =>
  useQuery<AdminOpsNewsPipelineResponse, Error>({
    queryKey: ADMIN_OPS_NEWS_PIPELINE_KEY,
    queryFn: fetchNewsPipeline,
    enabled,
    staleTime: 30_000,
    retry: shouldRetry,
  });

export const useUpdateNewsPipeline = () => {
  const queryClient = useQueryClient();
  return useMutation<AdminOpsNewsPipelineResponse, Error, AdminOpsNewsPipelineUpdatePayload>({
    mutationFn: (payload) => updateNewsPipeline(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ADMIN_OPS_NEWS_PIPELINE_KEY });
    },
  });
};

export const useOpsApiKeys = (enabled = true) =>
  useQuery<AdminOpsApiKeyResponse, Error>({
    queryKey: ADMIN_OPS_API_KEYS_KEY,
    queryFn: fetchOpsApiKeys,
    enabled,
    staleTime: 30_000,
    retry: shouldRetry,
  });

export const useUpdateOpsApiKeys = () => {
  const queryClient = useQueryClient();
  return useMutation<AdminOpsApiKeyResponse, Error, AdminOpsApiKeyUpdatePayload>({
    mutationFn: (payload) => updateOpsApiKeys(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ADMIN_OPS_API_KEYS_KEY });
    },
  });
};

export const useRotateLangfuseKeys = () => {
  const queryClient = useQueryClient();
  return useMutation<AdminOpsApiKeyResponse, Error, AdminOpsTriggerPayload>({
    mutationFn: (payload) => rotateLangfuseKeys(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ADMIN_OPS_API_KEYS_KEY });
    },
  });
};


export const useAlertTemplates = (enabled = true) =>
  useQuery<AdminOpsTemplateList, Error>({
    queryKey: ADMIN_ALERT_TEMPLATES_KEY,
    queryFn: fetchAlertTemplates,
    enabled,
    staleTime: 60_000,
    retry: shouldRetry,
  });

export const useGenerateAlertSampleMetadata = () =>
  useMutation<AdminOpsSampleMetadataResult, Error, AdminOpsSampleMetadataPayload>({
    mutationFn: (payload) => generateAlertSampleMetadata(payload),
  });

export const useOpsAlertChannels = (enabled = true) =>
  useQuery<AdminOpsAlertChannelResponse, Error>({
    queryKey: ADMIN_OPS_ALERT_CHANNELS_KEY,
    queryFn: fetchOpsAlertChannels,
    enabled,
    staleTime: 30_000,
    retry: shouldRetry,
  });

export const useUpdateOpsAlertChannels = () => {
  const queryClient = useQueryClient();
  return useMutation<AdminOpsAlertChannelResponse, Error, AdminOpsAlertChannelUpdatePayload>({
    mutationFn: (payload) => updateOpsAlertChannels(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ADMIN_OPS_ALERT_CHANNELS_KEY });
    },
  });
};

export const useCreateOpsAlertChannel = () => {
  const queryClient = useQueryClient();
  return useMutation<AdminOpsAlertChannelResponse, Error, AdminOpsAlertChannelCreatePayload>({
    mutationFn: (payload) => createOpsAlertChannel(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ADMIN_OPS_ALERT_CHANNELS_KEY });
    },
  });
};

export const useUpdateOpsAlertChannelStatus = () => {
  const queryClient = useQueryClient();
  return useMutation<AdminOpsAlertChannelResponse, Error, AdminOpsAlertChannelStatusPayload>({
    mutationFn: (payload) => updateOpsAlertChannelStatus(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ADMIN_OPS_ALERT_CHANNELS_KEY });
    },
  });
};

export const usePreviewOpsAlertChannel = () =>
  useMutation<AdminOpsAlertChannelPreviewResult, Error, AdminOpsAlertChannelPreviewPayload>({
    mutationFn: (payload) => previewOpsAlertChannel(payload),
  });

export const useOpsRunHistory = (enabled = true) =>
  useQuery<AdminOpsRunHistoryResponse, Error>({
    queryKey: ADMIN_OPS_RUN_HISTORY_KEY,
    queryFn: fetchOpsRunHistory,
    enabled,
    staleTime: 30_000,
    retry: shouldRetry,
  });

export const useAlertPresetUsage = (windowDays = 14, enabled = true) =>
  useQuery<AdminAlertPresetUsageResponse, Error>({
    queryKey: [...ADMIN_ALERT_PRESET_USAGE_KEY, windowDays],
    queryFn: () => fetchAlertPresetUsage(windowDays),
    enabled,
    staleTime: 60_000,
    retry: shouldRetry,
  });
