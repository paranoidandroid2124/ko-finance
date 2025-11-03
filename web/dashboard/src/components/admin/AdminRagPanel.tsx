"use client";

import clsx from "classnames";
import { useEffect, useMemo, useState } from "react";

import {
  useRagConfig,
  useRagReindexHistory,
  useRagReindexQueue,
  useTriggerRagReindex,
  useUpdateRagConfig,
  useRetryRagReindexQueue,
  useRemoveRagQueueEntry,
} from "@/hooks/useAdminConfig";
import { AdminActorNoteFields } from "@/components/admin/AdminActorNoteFields";
import { useAdminSession } from "@/hooks/useAdminSession";
import { resolveApiBase } from "@/lib/apiBase";
import type { AdminRagFilter, AdminRagReindexRecord, AdminRagReindexQueueEntry } from "@/lib/adminApi";
import { useToastStore } from "@/store/toastStore";

type RagSourceDraft = {
  key: string;
  name: string;
  enabled: boolean;
  metadataText: string;
};

type RagFormState = {
  sources: RagSourceDraft[];
  filtersJson: string;
  similarityThreshold: string;
  rerankModel: string;
  actor: string;
  note: string;
  error?: string | null;
};

type ReindexState = {
  selectedSources: Set<string>;
  note: string;
  feedback?: string | null;
  lastTaskId?: string | null;
  lastTraceUrl?: string | null;
  lastStatus?: string | null;
};

type BadgePreset = {
  label: string;
  className: string;
};

const EMPTY_METADATA_JSON = "{\n  \"language\": \"ko\"\n}";
const DEFAULT_FILTERS_JSON = "[]";

const REINDEX_STATUS_BADGES: Record<string, BadgePreset> = {
  queued: {
    label: "대기",
    className: "bg-amber-100 text-amber-700 dark:bg-amber-400/20 dark:text-amber-200",
  },
  running: {
    label: "진행 중",
    className: "bg-sky-100 text-sky-700 dark:bg-sky-400/20 dark:text-sky-200",
  },
  completed: {
    label: "완료",
    className: "bg-emerald-100 text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-200",
  },
  failed: {
    label: "실패",
    className: "bg-rose-100 text-rose-700 dark:bg-rose-400/20 dark:text-rose-200",
  },
  retrying: {
    label: "재시도 중",
    className: "bg-violet-100 text-violet-700 dark:bg-violet-400/20 dark:text-violet-200",
  },
  partial: {
    label: "부분 성공",
    className: "bg-amber-200 text-amber-800 dark:bg-amber-400/20 dark:text-amber-100",
  },
};

const resolveReindexBadge = (status: string | undefined): BadgePreset => {
  if (!status) {
    return { label: "확인 필요", className: "bg-border-light text-text-secondaryLight dark:bg-border-dark/50 dark:text-text-secondaryDark" };
  }
  const normalized = status.toLowerCase();
  return REINDEX_STATUS_BADGES[normalized] ?? {
    label: status,
    className: "bg-border-light text-text-secondaryLight dark:bg-border-dark/50 dark:text-text-secondaryDark",
  };
};

const EVIDENCE_DIFF_BADGES: Record<string, BadgePreset> = {
  created: {
    label: "새 Evidence",
    className: "bg-emerald-100 text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-200",
  },
  updated: {
    label: "내용 갱신",
    className: "bg-sky-100 text-sky-700 dark:bg-sky-400/20 dark:text-sky-200",
  },
  removed: {
    label: "제거됨",
    className: "bg-amber-100 text-amber-700 dark:bg-amber-400/20 dark:text-amber-200",
  },
};

const resolveEvidenceDiffBadge = (diffType: string | undefined): BadgePreset => {
  if (!diffType) {
    return { label: "미분류", className: "bg-border-light text-text-secondaryLight dark:bg-border-dark/50 dark:text-text-secondaryDark" };
  }
  const normalized = diffType.toLowerCase();
  return EVIDENCE_DIFF_BADGES[normalized] ?? {
    label: diffType,
    className: "bg-border-light text-text-secondaryLight dark:bg-border-dark/50 dark:text-text-secondaryDark",
  };
};

const REINDEX_STATUS_FILTERS = [
  { value: "queued", label: "대기" },
  { value: "running", label: "진행 중" },
  { value: "completed", label: "완료" },
  { value: "failed", label: "실패" },
  { value: "retrying", label: "재시도 중" },
  { value: "partial", label: "부분 성공" },
];

const QUEUE_STATUS_FILTERS = [
  { value: "queued", label: "대기" },
  { value: "running", label: "진행 중" },
  { value: "failed", label: "실패" },
  { value: "completed", label: "완료" },
];

const formatHistoryTimestamp = (value?: string | null) => {
  if (!value) {
    return "시간 정보 없음";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString("ko-KR");
};

const formatDuration = (value?: number | null) => {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "—";
  }
  if (value < 1000) {
    return `${value}ms`;
  }
  const seconds = value / 1000;
  if (seconds < 60) {
    return `${seconds.toFixed(seconds < 10 ? 1 : 0)}초`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainSeconds = Math.round(seconds % 60);
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    const remainMinutes = minutes % 60;
    return `${hours}시간 ${remainMinutes}분`;
  }
  return `${minutes}분 ${remainSeconds}초`;
};

const formatScopeLabel = (scope?: string | null) => {
  if (!scope || scope === "all") {
    return "전체 소스";
  }
  return scope
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .join(", ");
};

const formatRagModeLabel = (value?: string | null) => {
  switch ((value ?? "vector").toLowerCase()) {
    case "optional":
      return "선택형 RAG";
    case "none":
      return "RAG 없이 응답";
    case "vector":
    default:
      return "벡터 RAG";
  }
};

const createSourceDraft = (seed?: Partial<RagSourceDraft>): RagSourceDraft => ({
  key: seed?.key ?? "",
  name: seed?.name ?? "",
  enabled: seed?.enabled ?? true,
  metadataText: seed?.metadataText ?? EMPTY_METADATA_JSON,
});

export function AdminRagPanel() {
  const toast = useToastStore((state) => state.show);
  const {
    data: adminSession,
    isLoading: isAdminSessionLoading,
    isUnauthorized,
    refetch: refetchAdminSession,
  } = useAdminSession();

  const isSessionReady = Boolean(adminSession) && !isUnauthorized;

  const [formState, setFormState] = useState<RagFormState>({
    sources: [createSourceDraft()],
    filtersJson: DEFAULT_FILTERS_JSON,
    similarityThreshold: "0.62",
    rerankModel: "",
    actor: "",
    note: "",
  });

  const [reindexState, setReindexState] = useState<ReindexState>({
    selectedSources: new Set<string>(),
    note: "",
    lastTaskId: null,
    lastTraceUrl: null,
    lastStatus: null,
  });

  const [historySearch, setHistorySearch] = useState("");
  const [historyStatusFilter, setHistoryStatusFilter] = useState<Set<string>>(new Set());
  const [queueSearch, setQueueSearch] = useState("");
  const [queueStatusFilter, setQueueStatusFilter] = useState<Set<string>>(new Set(["queued", "failed"]));

  const historyStatusParams = useMemo(
    () => (historyStatusFilter.size ? Array.from(historyStatusFilter) : undefined),
    [historyStatusFilter],
  );
  const queueStatusParams = useMemo(
    () => (queueStatusFilter.size ? Array.from(queueStatusFilter) : undefined),
    [queueStatusFilter],
  );
  const historySearchQuery = useMemo(() => {
    const trimmed = historySearch.trim();
    return trimmed.length > 0 ? trimmed : undefined;
  }, [historySearch]);
  const queueSearchQuery = useMemo(() => {
    const trimmed = queueSearch.trim();
    return trimmed.length > 0 ? trimmed : undefined;
  }, [queueSearch]);

  const {
    data: ragConfig,
    isLoading: isConfigLoading,
    isError: isConfigError,
    refetch: refetchRagConfig,
  } = useRagConfig(isSessionReady);
  const {
    data: reindexHistory,
    isLoading: isHistoryLoading,
    refetch: refetchReindexHistory,
  } = useRagReindexHistory(isSessionReady, {
    status: historyStatusParams,
    q: historySearchQuery,
  });

  const {
    data: reindexQueue,
    isLoading: isQueueLoading,
    refetch: refetchReindexQueue,
  } = useRagReindexQueue(isSessionReady, {
    status: queueStatusParams,
    q: queueSearchQuery,
  });

  const updateRagConfig = useUpdateRagConfig();
  const triggerReindex = useTriggerRagReindex();
  const retryQueueMutation = useRetryRagReindexQueue();
  const removeQueueMutation = useRemoveRagQueueEntry();

  useEffect(() => {
    if (!ragConfig) {
      return;
    }
    setFormState((prev) => ({
      ...prev,
      sources:
        ragConfig.sources?.length
          ? ragConfig.sources.map((source) =>
              createSourceDraft({
                key: source.key,
                name: source.name,
                enabled: source.enabled,
                metadataText: JSON.stringify(source.metadata ?? {}, null, 2) || EMPTY_METADATA_JSON,
              }),
            )
          : [createSourceDraft()],
      filtersJson: ragConfig.filters?.length ? JSON.stringify(ragConfig.filters, null, 2) : DEFAULT_FILTERS_JSON,
      similarityThreshold: String(ragConfig.similarityThreshold ?? 0.62),
      rerankModel: ragConfig.rerankModel ?? "",
      actor: adminSession?.actor ?? prev.actor,
      note: "",
      error: undefined,
    }));
  }, [ragConfig, adminSession?.actor]);

  const toggleHistoryStatus = (value: string) => {
    setHistoryStatusFilter((prev) => {
      const next = new Set(prev);
      if (next.has(value)) {
        next.delete(value);
      } else {
        next.add(value);
      }
      return next;
    });
  };

  const toggleQueueStatus = (value: string) => {
    setQueueStatusFilter((prev) => {
      const next = new Set(prev);
      if (next.has(value)) {
        next.delete(value);
      } else {
        next.add(value);
      }
      return next;
    });
  };

  const defaultActor = useMemo(() => {
    const actorFromForm = formState.actor?.trim();
    if (actorFromForm) {
      return actorFromForm;
    }
    if (adminSession?.actor) {
      return adminSession.actor;
    }
    return "admin@kfinance.ai";
  }, [formState.actor, adminSession?.actor]);

  const handleRetryQueueEntry = async (entry: AdminRagReindexQueueEntry) => {
    try {
      const result = await retryQueueMutation.mutateAsync({
        queueId: entry.queueId,
        actor: defaultActor,
        note: entry.note ?? null,
      });
      toast({
        id: `rag/reindex/queue/retry/${entry.queueId}`,
        intent: "success",
        title: "재시도 요청 완료",
        message:
          result.status === "completed"
            ? "Langfuse 기록도 함께 갱신되고 있어요."
            : "재시도가 대기열에 등록되었어요.",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "재시도를 실행하지 못했어요.";
      toast({
        id: `rag/reindex/queue/retry/error-${entry.queueId}`,
        intent: "error",
        title: "재시도 실패",
        message,
      });
    }
  };

  const handleRemoveQueueEntry = async (queueId: string) => {
    try {
      await removeQueueMutation.mutateAsync(queueId);
      toast({
        id: `rag/reindex/queue/remove/${queueId}`,
        intent: "success",
        title: "큐에서 제거했어요",
        message: "대기열 정리가 완료되었어요.",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "큐 항목을 제거하지 못했어요.";
      toast({
        id: `rag/reindex/queue/remove/error-${queueId}`,
        intent: "error",
        title: "삭제 실패",
        message,
      });
    }
  };

  const handleCopyTraceId = async (traceId: string) => {
    try {
      if (!navigator?.clipboard?.writeText) {
        throw new Error("브라우저의 클립보드 API를 사용할 수 없어요.");
      }
      await navigator.clipboard.writeText(traceId);
      toast({
        id: `rag/reindex/trace/${traceId}`,
        intent: "success",
        title: "Trace ID를 복사했어요",
        message: "필요한 로그 확인이 조금 더 편해졌어요.",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Trace ID를 복사하지 못했어요.";
      toast({
        id: `rag/reindex/trace/error-${traceId}`,
        intent: "error",
        title: "복사에 실패했어요",
        message,
      });
    }
  };

  useEffect(() => {
    if (!ragConfig?.sources?.length) {
      return;
    }
    setReindexState((prev) => ({
      ...prev,
      selectedSources: new Set(ragConfig.sources.filter((item) => item.enabled).map((item) => item.key)),
    }));
  }, [ragConfig]);

  const auditDownloadUrl = `${resolveApiBase()}/api/v1/admin/rag/audit/logs`;

  const lastUpdatedLabel = useMemo(() => {
    if (!ragConfig?.updatedAt) {
      return null;
    }
    const parsed = new Date(ragConfig.updatedAt);
    return Number.isNaN(parsed.getTime()) ? ragConfig.updatedAt : parsed.toLocaleString();
  }, [ragConfig?.updatedAt]);

  const queueEntries = useMemo(() => {
    const entries = reindexQueue?.entries ?? [];
    return [...entries].sort((a, b) => {
      const left = a.updatedAt ?? a.createdAt;
      const right = b.updatedAt ?? b.createdAt;
      return right.localeCompare(left);
    });
  }, [reindexQueue?.entries]);

  const retryingQueueId = retryQueueMutation.isPending ? retryQueueMutation.variables?.queueId ?? null : null;
  const removingQueueId = removeQueueMutation.isPending ? removeQueueMutation.variables ?? null : null;

  const historyGroups = useMemo(() => {
    const runs = reindexHistory?.runs ?? [];
    const grouped: Array<{ latest: AdminRagReindexRecord; events: AdminRagReindexRecord[] }> = [];
    const lookup = new Map<string, { latest: AdminRagReindexRecord; events: AdminRagReindexRecord[] }>();

    for (const record of runs) {
      const existing = lookup.get(record.taskId);
      if (!existing) {
        const group = { latest: record, events: [record] };
        lookup.set(record.taskId, group);
        grouped.push(group);
      } else {
        existing.events.push(record);
      }
    }
    return grouped;
  }, [reindexHistory?.runs]);

  const [selectedHistoryTaskId, setSelectedHistoryTaskId] = useState<string | null>(null);
  const selectedHistoryGroup = useMemo(
    () => historyGroups.find((group) => group.latest.taskId === selectedHistoryTaskId) ?? null,
    [historyGroups, selectedHistoryTaskId],
  );

  useEffect(() => {
    if (!historyGroups.length) {
      setSelectedHistoryTaskId(null);
      return;
    }
    if (selectedHistoryTaskId) {
      const exists = historyGroups.some((group) => group.latest.taskId === selectedHistoryTaskId);
      if (!exists) {
        setSelectedHistoryTaskId(historyGroups[0].latest.taskId);
      }
      return;
    }
    setSelectedHistoryTaskId(historyGroups[0].latest.taskId);
  }, [historyGroups, selectedHistoryTaskId]);

  const handleSourceChange = (index: number, field: keyof RagSourceDraft, value: string | boolean) => {
    setFormState((prev) => {
      const next = [...prev.sources];
      const draft = { ...next[index] };
      if (field === "enabled") {
        draft.enabled = Boolean(value);
      } else {
        draft[field] = String(value);
      }
      next[index] = draft;
      return { ...prev, sources: next };
    });
  };

  const handleAddSource = () => {
    setFormState((prev) => ({ ...prev, sources: [...prev.sources, createSourceDraft()] }));
  };

  const handleRemoveSource = (index: number) => {
    setFormState((prev) => {
      const next = prev.sources.filter((_, idx) => idx !== index);
      return { ...prev, sources: next.length ? next : [createSourceDraft()] };
    });
  };

  const handleReindexSelect = (key: string, checked: boolean) => {
    setReindexState((prev) => {
      const next = new Set(prev.selectedSources);
      if (checked) {
        next.add(key);
      } else {
        next.delete(key);
      }
      return { ...prev, selectedSources: next };
    });
  };

  const handleSave = async () => {
    let filtersPayload: AdminRagFilter[] = [];
    try {
      const parsedFilters = formState.filtersJson.trim() ? JSON.parse(formState.filtersJson) : [];
      if (!Array.isArray(parsedFilters)) {
        throw new Error("filters는 배열 형태여야 해요.");
      }
      filtersPayload = parsedFilters.map((rawFilter, index) => {
        if (!rawFilter || typeof rawFilter !== "object" || Array.isArray(rawFilter)) {
          throw new Error(`${index + 1}번째 필터는 객체 형태여야 해요.`);
        }
        const record = rawFilter as Record<string, unknown>;
        const field = record.field;
        const operator = record.operator;
        if (typeof field !== "string" || typeof operator !== "string") {
          throw new Error(`${index + 1}번째 필터에는 field와 operator 문자열이 필요해요.`);
        }
        return {
          field,
          operator,
          value: record.value,
        };
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "filters JSON이 올바르지 않아요.";
      setFormState((prev) => ({ ...prev, error: message }));
      return;
    }

    const parsedSources = [];
    for (const draft of formState.sources) {
      const key = draft.key.trim();
      if (!key) {
        setFormState((prev) => ({ ...prev, error: "모든 소스에 고유한 key가 필요해요." }));
        return;
      }
      try {
        const metadata = draft.metadataText.trim() ? JSON.parse(draft.metadataText) : {};
        if (metadata === null || typeof metadata !== "object" || Array.isArray(metadata)) {
          throw new Error();
        }
        parsedSources.push({
          key,
          name: draft.name.trim() || key,
          enabled: draft.enabled,
          metadata: metadata as Record<string, unknown>,
        });
      } catch {
        setFormState((prev) => ({
          ...prev,
          error: `${draft.name || draft.key}의 metadata JSON이 올바르지 않아요.`,
        }));
        return;
      }
    }

    const threshold = Number(formState.similarityThreshold);
    if (Number.isNaN(threshold)) {
      setFormState((prev) => ({ ...prev, error: "유사도 임계값은 숫자여야 해요." }));
      return;
    }

    try {
      await updateRagConfig.mutateAsync({
        sources: parsedSources,
        filters: filtersPayload,
        similarityThreshold: threshold,
        rerankModel: formState.rerankModel.trim() || null,
        actor: formState.actor.trim() || adminSession?.actor || "unknown-admin",
        note: formState.note.trim() || null,
      });
      toast({
        id: "admin/rag/config/success",
        title: "RAG 설정이 저장됐어요",
        message: "근거 패널 구성이 최신 상태예요.",
        intent: "success",
      });
      setFormState((prev) => ({ ...prev, error: undefined, note: "" }));
      await refetchRagConfig();
    } catch (error) {
      const message = error instanceof Error ? error.message : "설정을 저장하지 못했어요.";
      toast({
        id: "admin/rag/config/error",
        title: "RAG 설정 저장 실패",
        message,
        intent: "error",
      });
    }
  };

  const handleReindex = async () => {
    const sources =
      reindexState.selectedSources.size > 0
        ? Array.from(reindexState.selectedSources)
        : formState.sources.map((source) => source.key).filter(Boolean);

    try {
      const result = await triggerReindex.mutateAsync({
        sources,
        actor: formState.actor.trim() || adminSession?.actor || "unknown-admin",
        note: reindexState.note.trim() || null,
      });
      const historyResult = await refetchReindexHistory();
      const matchingRuns = (historyResult.data?.runs ?? []).filter((run) => run.taskId === result.taskId);
      const latestRun = matchingRuns[0];
      const latestStatus = latestRun?.status ?? result.status;
      const badge = resolveReindexBadge(latestStatus);
      const traceUrl = latestRun?.langfuseTraceUrl ?? null;

      toast({
        id: "admin/rag/reindex/success",
        title: "재색인이 요청됐어요",
        message: `작업 ID ${result.taskId} (${badge.label})`,
        intent: "success",
        actionLabel: traceUrl ? "Langfuse 열기" : undefined,
        actionHref: traceUrl ?? undefined,
      });
      setReindexState((prev) => ({
        ...prev,
        feedback: `작업 ID ${result.taskId} · ${badge.label}`,
        note: "",
        lastTaskId: result.taskId,
        lastTraceUrl: traceUrl,
        lastStatus: latestStatus,
      }));
      setSelectedHistoryTaskId(result.taskId);
    } catch (error) {
      const message = error instanceof Error ? error.message : "재색인 요청에 실패했어요.";
      toast({
        id: "admin/rag/reindex/error",
        title: "재색인 실패",
        message,
        intent: "error",
      });
      await refetchReindexHistory();
    }
  };

  if (isAdminSessionLoading) {
    return (
      <section className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">관리자 세션을 확인하는 중이에요…</p>
      </section>
    );
  }

  if (isUnauthorized) {
    return (
      <section className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          RAG 설정을 보려면 관리자 토큰 로그인이 필요해요.
        </p>
        <button
          type="button"
          onClick={() => refetchAdminSession()}
          className="mt-4 inline-flex items-center rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-primaryLight transition hover:bg-border-light/40 dark:border-border-dark dark:text-text-primaryDark dark:hover:bg-border-dark/40"
        >
          다시 시도
        </button>
      </section>
    );
  }

  if (!adminSession) {
    return null;
  }

  return (
    <section className="space-y-6 rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <header className="space-y-2 border-b border-border-light pb-4 dark:border-border-dark">
        <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">RAG 컨텍스트 설정</h2>
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          데이터 소스, 필터, 임계값을 조정해 근거 패널의 신뢰도를 높여 주세요.
        </p>
        <div className="flex flex-wrap items-center gap-4 text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
          <span>최근 수정: {lastUpdatedLabel ?? "기록 없음"}</span>
          <span>작성자: {ragConfig?.updatedBy ?? "—"}</span>
          <a
            href={auditDownloadUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="font-semibold text-primary hover:underline dark:text-primary.dark"
          >
            감사 로그 다운로드 (rag_audit.jsonl)
          </a>
        </div>
      </header>

      {isConfigError ? (
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:border-amber-500/70 dark:bg-amber-500/10 dark:text-amber-200">
          RAG 설정을 불러오지 못했어요. 새로고침 후 다시 시도해 주세요.
        </div>
      ) : null}

      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
            데이터 소스
          </h3>
          <button
            type="button"
            onClick={handleAddSource}
            className="inline-flex items-center rounded-lg border border-border-light px-3 py-1.5 text-sm font-semibold text-text-primaryLight transition hover:bg-border-light/40 dark:border-border-dark dark:text-text-primaryDark dark:hover:bg-border-dark/40"
          >
            소스 추가
          </button>
        </div>

        <div className="space-y-4">
          {formState.sources.map((source, index) => (
            <article
              key={`rag-source-${index}`}
              className="rounded-xl border border-border-light bg-background-base p-4 dark:border-border-dark dark:bg-background-cardDark"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h4 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">소스 {index + 1}</h4>
                <div className="flex items-center gap-2">
                  <label className="inline-flex items-center gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                    <input
                      type="checkbox"
                      checked={source.enabled}
                      onChange={(event) => handleSourceChange(index, "enabled", event.target.checked)}
                      className="h-4 w-4 rounded border-border-light text-primary focus:ring-primary dark:border-border-dark"
                    />
                    활성화
                  </label>
                  <button
                    type="button"
                    onClick={() => handleRemoveSource(index)}
                    className="inline-flex items-center rounded-lg border border-border-light px-3 py-1 text-xs font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
                  >
                    삭제
                  </button>
                </div>
              </div>

              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                  Key
                  <input
                    type="text"
                    value={source.key}
                    onChange={(event) => handleSourceChange(index, "key", event.target.value)}
                    placeholder="예: filings"
                    className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                  />
                </label>
                <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                  표시 이름
                  <input
                    type="text"
                    value={source.name}
                    onChange={(event) => handleSourceChange(index, "name", event.target.value)}
                    placeholder="예: 공시/재무제표"
                    className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                  />
                </label>
              </div>

              <label className="mt-3 flex flex-col gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                Metadata (JSON)
                <textarea
                  value={source.metadataText}
                  onChange={(event) => handleSourceChange(index, "metadataText", event.target.value)}
                  className="min-h-[140px] rounded-lg border border-border-light bg-background-base px-3 py-2 font-mono text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                  placeholder='{"language": "ko"}'
                />
              </label>
            </article>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <label className="flex flex-col gap-2 text-sm">
          <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">필터 설정 (JSON)</span>
          <textarea
            value={formState.filtersJson}
            onChange={(event) => setFormState((prev) => ({ ...prev, filtersJson: event.target.value }))}
            className="min-h-[180px] rounded-lg border border-border-light bg-background-base px-3 py-2 font-mono text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
            placeholder='[{"field":"sector","operator":"in","value":["금융"]}]'
          />
        </label>

        <div className="space-y-4">
          <label className="flex flex-col gap-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            유사도 임계값
            <input
              type="number"
              min="0"
              max="1"
              step="0.01"
              value={formState.similarityThreshold}
              onChange={(event) => setFormState((prev) => ({ ...prev, similarityThreshold: event.target.value }))}
              className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
            />
          </label>

          <label className="flex flex-col gap-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            Rerank 모델
            <input
              type="text"
              value={formState.rerankModel}
              onChange={(event) => setFormState((prev) => ({ ...prev, rerankModel: event.target.value }))}
              placeholder="예: bge-reranker-large"
              className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
            />
          </label>

          <AdminActorNoteFields
            actor={formState.actor}
            note={formState.note}
            onActorChange={(value) => setFormState((prev) => ({ ...prev, actor: value }))}
            onNoteChange={(value) => setFormState((prev) => ({ ...prev, note: value }))}
            actorPlaceholder={adminSession?.actor ?? "운영자 이름"}
            notePlaceholder="예: 뉴스 소스 metadata 정리"
          />

          {formState.error ? (
            <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-700 dark:border-amber-500/70 dark:bg-amber-500/10 dark:text-amber-200">
              {formState.error}
            </p>
          ) : null}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-end gap-3">
        <button
          type="button"
          onClick={() => refetchRagConfig()}
          className="inline-flex items-center rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
          disabled={isConfigLoading}
        >
          최신 상태 불러오기
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={updateRagConfig.isPending}
          className={clsx(
            "inline-flex items-center rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-white transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
            updateRagConfig.isPending && "cursor-not-allowed opacity-60",
          )}
        >
          {updateRagConfig.isPending ? "저장 중…" : "설정 저장"}
        </button>
      </div>

      <div className="rounded-xl border border-dashed border-border-light bg-background-base p-4 dark:border-border-dark dark:bg-background-cardDark">
        <h3 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">재색인 요청</h3>
        <p className="mt-1 text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
          선택한 소스로 벡터 재색인을 즉시 실행해요. 선택하지 않으면 활성화된 모든 소스를 재색인합니다.
        </p>
        <div className="mt-3 flex flex-wrap gap-3">
          {formState.sources.map((source, index) => (
            <label
              key={`reindex-${index}-${source.key}`}
              className="inline-flex items-center gap-2 rounded-lg border border-border-light px-3 py-2 text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark"
            >
              <input
                type="checkbox"
                checked={reindexState.selectedSources.has(source.key)}
                onChange={(event) => handleReindexSelect(source.key, event.target.checked)}
                className="h-4 w-4 rounded border-border-light text-primary focus:ring-primary dark:border-border-dark"
              />
              {source.name || source.key || `Source ${index + 1}`}
            </label>
          ))}
        </div>

        <label className="mt-3 flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          재색인 메모
          <input
            type="text"
            value={reindexState.note}
            onChange={(event) => setReindexState((prev) => ({ ...prev, note: event.target.value }))}
            placeholder="예: 신규 뉴스 소스 추가 확인"
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>

        {reindexState.feedback ? (
          <div className="mt-2 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2 text-xs text-emerald-700 dark:border-emerald-500/70 dark:bg-emerald-500/10 dark:text-emerald-200">
            <span>{reindexState.feedback}</span>
            {reindexState.lastTraceUrl ? (
              <button
                type="button"
                className="rounded-md border border-emerald-400 px-2 py-1 text-[11px] font-semibold text-emerald-700 transition hover:bg-emerald-100 dark:border-emerald-200/50 dark:text-emerald-200 dark:hover:bg-emerald-500/20"
                onClick={() => window.open(reindexState.lastTraceUrl ?? undefined, "_blank", "noopener,noreferrer")}
              >
                Langfuse trace 열기
              </button>
            ) : null}
          </div>
        ) : null}

        <div className="mt-3 flex flex-wrap items-center justify-end gap-3">
          <button
            type="button"
            onClick={handleReindex}
            disabled={triggerReindex.isPending}
            className={clsx(
              "inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
              triggerReindex.isPending && "cursor-not-allowed opacity-60",
            )}
          >
            {triggerReindex.isPending ? "요청 중…" : "재색인 실행"}
          </button>
        </div>

        <div className="mt-6 space-y-3 rounded-lg border border-border-light/60 bg-background-cardLight/50 p-4 text-xs text-text-secondaryLight dark:border-border-dark/60 dark:bg-background-cardDark/40 dark:text-text-secondaryDark">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h4 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">재색인 재시도 큐</h4>
              <p className="mt-1 text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                실패한 작업을 다시 실행하거나 큐에서 정리할 수 있어요.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {QUEUE_STATUS_FILTERS.map((option) => {
                const isActive = queueStatusFilter.has(option.value);
                return (
                  <button
                    key={`queue-filter-${option.value}`}
                    type="button"
                    onClick={() => toggleQueueStatus(option.value)}
                    className={clsx(
                      "inline-flex items-center rounded-full border px-3 py-1 text-[11px] font-semibold transition",
                      isActive
                        ? "border-primary bg-primary text-white dark:border-primary.dark dark:bg-primary.dark"
                        : "border-border-light text-text-secondaryLight hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark",
                    )}
                  >
                    {option.label}
                  </button>
                );
              })}
              {queueStatusFilter.size > 0 || queueSearch.trim().length > 0 ? (
                <button
                  type="button"
                  onClick={() => {
                    setQueueStatusFilter(new Set(["queued", "failed"]));
                    setQueueSearch("");
                  }}
                  className="inline-flex items-center rounded-full border border-border-light px-3 py-1 text-[11px] font-semibold text-text-tertiaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-tertiaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
                >
                  초기화
                </button>
              ) : null}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <label className="flex-1 min-w-[200px] text-[11px] font-semibold text-text-secondaryLight dark:text-text-secondaryDark">
              검색어
              <input
                type="text"
                value={queueSearch}
                onChange={(event) => setQueueSearch(event.target.value)}
                placeholder="actor, 메모, 오류, 큐 ID"
                className="mt-1 w-full rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
              />
            </label>
            <button
              type="button"
              onClick={() => refetchReindexQueue()}
              disabled={isQueueLoading}
              className="inline-flex items-center rounded-lg border border-border-light px-3 py-2 text-[11px] font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
            >
              대기열 새로고침
            </button>
          </div>

          {isQueueLoading ? (
            <p className="text-text-tertiaryLight dark:text-text-tertiaryDark">재시도 대기열을 불러오는 중이에요…</p>
          ) : queueEntries.length ? (
            <div className="space-y-3">
              {queueEntries.map((entry) => {
                const badge = resolveReindexBadge(entry.status);
                const maxAttempts = entry.maxAttempts ?? 3;
                const retryMode = entry.retryMode ?? "auto";
                const isAutoMode = retryMode === "auto";
                const cooldownDate = entry.cooldownUntil ? new Date(entry.cooldownUntil) : null;
                const isCoolingDown = Boolean(isAutoMode && cooldownDate && cooldownDate.getTime() > Date.now());
                const hasExhaustedAuto = Boolean(isAutoMode && entry.attempts >= maxAttempts);
                const cooldownLabel = cooldownDate ? formatHistoryTimestamp(entry.cooldownUntil) : null;

                return (
                  <article
                    key={entry.queueId}
                    className="rounded-lg border border-border-light bg-background-base p-4 transition hover:border-primary/60 dark:border-border-dark dark:bg-background-cardDark"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">큐 ID {entry.queueId}</p>
                        <p className="text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">원본 작업 {entry.originalTaskId}</p>
                        <p className="text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                          최근 업데이트 {formatHistoryTimestamp(entry.updatedAt || entry.createdAt)}
                        </p>
                        <div className="mt-1 flex flex-wrap items-center gap-2">
                          <span
                            className={clsx(
                              "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                              isAutoMode
                                ? "bg-primary/10 text-primary dark:bg-primary/20 dark:text-primary"
                                : "bg-amber-100 text-amber-700 dark:bg-amber-400/20 dark:text-amber-200",
                            )}
                          >
                            {isAutoMode ? "자동 재시도" : "수동 재시도"}
                          </span>
                          <span className="rounded-full bg-border-light px-2 py-0.5 text-[10px] font-semibold text-text-tertiaryLight dark:bg-border-dark dark:text-text-tertiaryDark">
                            시도 {entry.attempts}/{maxAttempts}
                          </span>
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <span
                          className={clsx(
                            "rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide",
                            badge.className,
                          )}
                        >
                          {badge.label}
                        </span>
                        {isAutoMode ? (
                          <span
                            className={clsx(
                              "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                              hasExhaustedAuto
                                ? "bg-amber-100 text-amber-700 dark:bg-amber-400/20 dark:text-amber-200"
                                : isCoolingDown
                                ? "bg-sky-100 text-sky-700 dark:bg-sky-400/20 dark:text-sky-200"
                                : "bg-emerald-100 text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-200",
                            )}
                          >
                            {hasExhaustedAuto ? "자동 재시도 종료" : isCoolingDown ? "쿨다운 진행 중" : "즉시 재시도 가능"}
                          </span>
                        ) : null}
                      </div>
                    </div>
                    <dl className="mt-3 grid gap-3 text-[11px] text-text-secondaryLight dark:text-text-secondaryDark md:grid-cols-2">
                      <div>
                        <dt className="font-semibold">재시도 횟수</dt>
                        <dd>
                          {entry.attempts}/{maxAttempts}
                        </dd>
                      </div>
                      <div>
                        <dt className="font-semibold">최근 시도 시각</dt>
                        <dd>{formatHistoryTimestamp(entry.lastAttemptAt)}</dd>
                      </div>
                      <div>
                        <dt className="font-semibold">자동 재시도 안내</dt>
                        <dd>
                          {isAutoMode
                            ? hasExhaustedAuto
                              ? "자동 재시도 횟수를 모두 사용했어요. 수동으로 다시 실행해 주세요."
                              : isCoolingDown
                              ? `${cooldownLabel ?? "잠시 후"}에 다시 달려볼게요.`
                              : "지금 바로 자동 재시도를 다시 걸 수 있어요."
                            : "운영자가 직접 재시도 버튼을 눌러야 해요."}
                        </dd>
                      </div>
                      <div>
                        <dt className="font-semibold">Langfuse trace</dt>
                        <dd className="flex flex-wrap items-center gap-2">
                          {entry.langfuseTraceUrl ? (
                            <a href={entry.langfuseTraceUrl} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                              trace 열기
                            </a>
                          ) : (
                            <span className="text-text-tertiaryLight dark:text-text-tertiaryDark">Langfuse trace 링크가 아직 생성되지 않았어요.</span>
                          )}
                          {entry.langfuseTraceId ? (
                            <>
                              <span className="rounded bg-border-light px-2 py-0.5 font-mono text-[10px] text-text-tertiaryLight dark:bg-border-dark dark:text-text-tertiaryDark">
                                {entry.langfuseTraceId}
                              </span>
                              <button
                                type="button"
                                onClick={() => handleCopyTraceId(entry.langfuseTraceId ?? "")}
                                className="inline-flex items-center rounded border border-border-light px-2 py-0.5 text-[10px] font-semibold text-text-secondaryLight transition hover:bg-border-light/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/60 dark:focus-visible:outline-border-dark"
                              >
                                복사
                              </button>
                            </>
                          ) : null}
                          {entry.langfuseSpanId ? (
                            <>
                              <span className="rounded bg-border-light px-2 py-0.5 font-mono text-[10px] text-text-tertiaryLight dark:bg-border-dark dark:text-text-tertiaryDark">
                                {entry.langfuseSpanId}
                              </span>
                              <button
                                type="button"
                                onClick={() => handleCopyTraceId(entry.langfuseSpanId ?? "")}
                                className="inline-flex items-center rounded border border-border-light px-2 py-0.5 text-[10px] font-semibold text-text-secondaryLight transition hover:bg-border-light/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/60 dark:focus-visible:outline-border-dark"
                              >
                                Span 복사
                              </button>
                            </>
                          ) : null}
                        </dd>
                      </div>
                      {entry.lastError ? (
                        <div>
                          <dt className="font-semibold">마지막 오류</dt>
                          <dd className="text-accent-negative">{entry.lastError}</dd>
                        </div>
                      ) : null}
                      {entry.note ? (
                        <div className="md:col-span-2">
                          <dt className="font-semibold">메모</dt>
                          <dd className="whitespace-pre-wrap text-text-primaryLight dark:text-text-primaryDark">{entry.note}</dd>
                        </div>
                      ) : null}
                    </dl>
                    <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => handleRemoveQueueEntry(entry.queueId)}
                        disabled={removingQueueId === entry.queueId}
                        className={clsx(
                          "inline-flex items-center rounded-lg border border-border-light px-3 py-1.5 text-[11px] font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark",
                          removingQueueId === entry.queueId && "cursor-not-allowed opacity-60",
                        )}
                      >
                        제거
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRetryQueueEntry(entry)}
                        disabled={retryingQueueId === entry.queueId}
                        className={clsx(
                          "inline-flex items-center rounded-lg bg-primary px-4 py-1.5 text-[11px] font-semibold text-white transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
                          retryingQueueId === entry.queueId && "cursor-not-allowed opacity-60",
                        )}
                      >
                        재시도 실행
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <p className="text-text-tertiaryLight dark:text-text-tertiaryDark">재시도 대기열이 비어 있어요.</p>
          )}
        </div>

        <div className="mt-6 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
              최근 실행 이력
            </h4>
            <div className="flex flex-wrap items-center gap-2">
              <label className="flex items-center gap-2 rounded-lg border border-border-light bg-background-base px-2 py-1 text-[11px] font-semibold text-text-secondaryLight dark:border-border-dark dark:bg-background-cardDark dark:text-text-secondaryDark">
                검색
                <input
                  type="text"
                  value={historySearch}
                  onChange={(event) => setHistorySearch(event.target.value)}
                  placeholder="actor, 소스, 오류 코드"
                  className="rounded-md border border-transparent bg-transparent px-2 py-1 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:text-text-primaryDark"
                />
              </label>
              <button
                type="button"
                onClick={() => refetchReindexHistory()}
                disabled={isHistoryLoading}
                className="inline-flex items-center rounded-lg border border-border-light px-3 py-1 text-[11px] font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
              >
                새로고침
              </button>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {REINDEX_STATUS_FILTERS.map((option) => {
              const isActive = historyStatusFilter.has(option.value);
              return (
                <button
                  key={`history-filter-${option.value}`}
                  type="button"
                  onClick={() => toggleHistoryStatus(option.value)}
                  className={clsx(
                    "inline-flex items-center rounded-full border px-3 py-1 text-[11px] font-semibold transition",
                    isActive
                      ? "border-primary bg-primary text-white dark:border-primary.dark dark:bg-primary.dark"
                      : "border-border-light text-text-secondaryLight hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark",
                  )}
                >
                  {option.label}
                </button>
              );
            })}
            {historyStatusFilter.size > 0 || historySearch.trim().length > 0 ? (
              <button
                type="button"
                onClick={() => {
                  setHistoryStatusFilter(new Set());
                  setHistorySearch("");
                }}
                className="inline-flex items-center rounded-full border border-border-light px-3 py-1 text-[11px] font-semibold text-text-tertiaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-tertiaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
              >
                필터 초기화
              </button>
            ) : null}
          </div>
</div>

          {isHistoryLoading ? (
            <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">재색인 이력을 불러오는 중이에요…</p>
          ) : historyGroups.length ? (
            <>
              <div className="overflow-x-auto rounded-lg border border-border-light dark:border-border-dark">
                <table className="min-w-full divide-y divide-border-light text-xs dark:divide-border-dark">
                  <thead className="bg-background-subtle dark:bg-background-cardDark">
                    <tr className="text-left text-[11px] font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
                      <th className="px-3 py-2">상태</th>
                      <th className="px-3 py-2">대상 소스</th>
                      <th className="px-3 py-2">요청자</th>
                      <th className="px-3 py-2">시작</th>
                      <th className="px-3 py-2 text-right">소요 시간</th>
                      <th className="px-3 py-2 text-right">Langfuse</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-light/60 dark:divide-border-dark/60">
                    {historyGroups.map((group) => {
                      const { latest } = group;
                      const badge = resolveReindexBadge(latest.status);
                      const isActive = selectedHistoryTaskId === latest.taskId;
                      const startedLabel = latest.startedAt || latest.timestamp;
                      return (
                        <tr
                          key={latest.taskId}
                          onClick={() => setSelectedHistoryTaskId(latest.taskId)}
                          className={clsx(
                            "cursor-pointer bg-background-base transition hover:bg-border-light/30 dark:bg-background-cardDark dark:hover:bg-border-dark/40",
                            isActive && "bg-border-light/50 dark:bg-border-dark/60",
                          )}
                        >
                          <td className="px-3 py-2">
                            <span
                              className={clsx(
                                "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
                                badge.className,
                              )}
                            >
                              {badge.label}
                            </span>
                          </td>
                          <td className="px-3 py-2 font-medium text-text-primaryLight dark:text-text-primaryDark">
                          {latest.scopeDetail?.length ? latest.scopeDetail.join(", ") : formatScopeLabel(latest.scope)}
                          </td>
                          <td className="px-3 py-2 text-text-secondaryLight dark:text-text-secondaryDark">{latest.actor || "—"}</td>
                          <td className="px-3 py-2 text-text-secondaryLight dark:text-text-secondaryDark">
                            {formatHistoryTimestamp(startedLabel)}
                          </td>
                          <td className="px-3 py-2 text-right text-text-secondaryLight dark:text-text-secondaryDark">
                            {formatDuration(latest.durationMs)}
                          </td>
                          <td className="px-3 py-2 text-right">
                            {latest.langfuseTraceUrl ? (
                              <a
                                href={latest.langfuseTraceUrl}
                                target="_blank"
                                rel="noreferrer"
                                onClick={(event) => event.stopPropagation()}
                                className="text-primary hover:underline"
                              >
                                열기
                              </a>
                            ) : (
                              <span className="text-text-tertiaryLight dark:text-text-tertiaryDark">—</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {selectedHistoryGroup
                ? (() => {
                    const latestRecord = selectedHistoryGroup.latest;
                    const scopeSummary = latestRecord.scopeDetail?.length
                      ? latestRecord.scopeDetail.join(", ")
                      : formatScopeLabel(latestRecord.scope);
                    const retryModeLabel = latestRecord.retryMode === "manual" ? "수동 재시도" : "자동 재시도";
                    const isAutoMode = (latestRecord.retryMode ?? "auto") === "auto";
                    const evidenceDiff = latestRecord.evidenceDiff ?? null;
                    const hasEvidenceChanges = Boolean(evidenceDiff && evidenceDiff.totalChanges > 0);

                    return (
                      <div className="mt-4 space-y-4 rounded-lg border border-border-light bg-background-cardLight p-4 text-sm text-text-primaryLight dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
                              작업 ID {latestRecord.taskId}
                            </p>
                            <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                              {scopeSummary} · {latestRecord.actor || "—"}
                            </p>
                            <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                              <span
                                className={clsx(
                                  "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                                  isAutoMode
                                    ? "bg-primary/10 text-primary dark:bg-primary/20 dark:text-primary"
                                    : "bg-amber-100 text-amber-700 dark:bg-amber-400/20 dark:text-amber-200",
                                )}
                              >
                                {retryModeLabel}
                              </span>
                              {latestRecord.queueId ? (
                                <span className="rounded-full bg-border-light px-2 py-0.5 text-[10px] text-text-tertiaryLight dark:bg-border-dark dark:text-text-tertiaryDark">
                                  큐 {latestRecord.queueId}
                                </span>
                              ) : null}
                            </div>
                            <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
                              기록 생성: {formatHistoryTimestamp(latestRecord.timestamp)}
                            </p>
                          </div>
                          <span
                            className={clsx(
                              "rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide",
                              resolveReindexBadge(latestRecord.status).className,
                            )}
                          >
                            {resolveReindexBadge(latestRecord.status).label}
                          </span>
                        </div>

                        <dl className="grid gap-3 text-xs text-text-secondaryLight dark:text-text-secondaryDark sm:grid-cols-2">
                          <div>
                            <dt className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">시작</dt>
                            <dd>{formatHistoryTimestamp(latestRecord.startedAt || latestRecord.timestamp)}</dd>
                          </div>
                          <div>
                            <dt className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">종료</dt>
                            <dd>{formatHistoryTimestamp(latestRecord.finishedAt)}</dd>
                          </div>
                          <div>
                            <dt className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">소요 시간</dt>
                            <dd>{formatDuration(latestRecord.durationMs)}</dd>
                          </div>
                          <div>
                            <dt className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">자동 재시도 안내</dt>
                            <dd>{isAutoMode ? "자동 재시도 흐름으로 처리된 작업이에요." : "운영자가 직접 실행한 작업이에요."}</dd>
                          </div>
                          <div>
                            <dt className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">Judge &amp; RAG 모드</dt>
                            <dd>{formatRagModeLabel(latestRecord.ragMode)} · {retryModeLabel}</dd>
                          </div>
                          <div>
                            <dt className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">Langfuse trace</dt>
                            <dd className="flex flex-wrap items-center gap-2">
                              {latestRecord.langfuseTraceUrl ? (
                                <a href={latestRecord.langfuseTraceUrl} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                                  새 탭에서 열기
                                </a>
                              ) : (
                                <span className="text-text-tertiaryLight dark:text-text-tertiaryDark">링크가 아직 준비되지 않았어요.</span>
                              )}
                              {latestRecord.langfuseTraceId ? (
                                <>
                                  <span className="rounded bg-border-light px-2 py-0.5 font-mono text-[11px] text-text-tertiaryLight dark:bg-border-dark dark:text-text-tertiaryDark">
                                    {latestRecord.langfuseTraceId}
                                  </span>
                                  <button
                                    type="button"
                                    onClick={() => handleCopyTraceId(latestRecord.langfuseTraceId ?? "")}
                                    className="inline-flex items-center rounded border border-border-light px-2 py-0.5 text-[10px] font-semibold text-text-secondaryLight transition hover:bg-border-light/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/60 dark:focus-visible:outline-border-dark"
                                  >
                                    복사
                                  </button>
                                </>
                              ) : null}
                              {latestRecord.langfuseSpanId ? (
                                <>
                                  <span className="rounded bg-border-light px-2 py-0.5 font-mono text-[10px] text-text-tertiaryLight dark:bg-border-dark dark:text-text-tertiaryDark">
                                    {latestRecord.langfuseSpanId}
                                  </span>
                                  <button
                                    type="button"
                                    onClick={() => handleCopyTraceId(latestRecord.langfuseSpanId ?? "")}
                                    className="inline-flex items-center rounded border border-border-light px-2 py-0.5 text-[10px] font-semibold text-text-secondaryLight transition hover:bg-border-light/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/60 dark:focus-visible:outline-border-dark"
                                  >
                                    Span 복사
                                  </button>
                                </>
                              ) : null}
                            </dd>
                          </div>
                          {latestRecord.note ? (
                            <div className="sm:col-span-2">
                              <dt className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">메모</dt>
                              <dd className="whitespace-pre-line text-text-primaryLight dark:text-text-primaryDark">{latestRecord.note}</dd>
                            </div>
                          ) : null}
                        </dl>

                        <div className="space-y-2 rounded-lg border border-border-light/60 bg-background-base p-3 text-xs text-text-secondaryLight dark:border-border-dark/60 dark:bg-background-cardDark dark:text-text-secondaryDark">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <h4 className="text-[11px] font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">Evidence 변화</h4>
                            {hasEvidenceChanges ? (
                              <div className="flex flex-wrap items-center gap-2 text-[10px] font-semibold">
                                <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-200">
                                  신규 {evidenceDiff?.created ?? 0}
                                </span>
                                <span className="rounded-full bg-sky-100 px-2 py-0.5 text-sky-700 dark:bg-sky-400/20 dark:text-sky-200">
                                  갱신 {evidenceDiff?.updated ?? 0}
                                </span>
                                {evidenceDiff?.removed ? (
                                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-700 dark:bg-amber-400/20 dark:text-amber-200">
                                    제거 {evidenceDiff.removed}
                                  </span>
                                ) : null}
                              </div>
                            ) : null}
                          </div>
                          {!hasEvidenceChanges ? (
                            <p className="text-text-tertiaryLight dark:text-text-tertiaryDark">재색인 이후 변화가 아직 기록되지 않았어요.</p>
                          ) : (
                            <ul className="space-y-2">
                              {evidenceDiff?.samples.map((item, index) => {
                                const sampleKey = item.urnId || item.chunkId || `diff-${index}`;
                                const badge = resolveEvidenceDiffBadge(item.diffType);
                                return (
                                  <li
                                    key={sampleKey}
                                    className="rounded-lg border border-border-light/50 bg-background-cardLight/60 p-3 dark:border-border-dark/50 dark:bg-background-cardDark/60"
                                  >
                                    <div className="flex flex-wrap items-start justify-between gap-2">
                                      <div className="space-y-1">
                                        <p className="text-[11px] font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
                                          {item.source || "소스 미지정"}
                                        </p>
                                        {item.section ? (
                                          <p className="text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">{item.section}</p>
                                        ) : null}
                                        {item.quote ? (
                                          <p className="text-sm text-text-primaryLight dark:text-text-primaryDark">{item.quote}</p>
                                        ) : null}
                                      </div>
                                      <span
                                        className={clsx(
                                          "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                                          badge.className,
                                        )}
                                      >
                                        {badge.label}
                                      </span>
                                    </div>
                                    <div className="mt-2 flex flex-wrap items-center gap-3 text-[10px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                                      {item.urnId ? <span>URN: {item.urnId}</span> : null}
                                      {item.chunkId ? <span>청크: {item.chunkId}</span> : null}
                                      {item.updatedAt ? <span>{formatHistoryTimestamp(item.updatedAt)}</span> : null}
                                    </div>
                                  </li>
                                );
                              })}
                            </ul>
                          )}
                        </div>

                      </div>
                    );
                  })()
                : null}

                    {selectedHistoryGroup?.latest?.queueId ? (
                      <div>
                        <dt className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">큐 ID</dt>
                        <dd>{selectedHistoryGroup.latest.queueId}</dd>
                      </div>
                    ) : null}
                    {selectedHistoryGroup?.latest?.note ? (
                      <div className="sm:col-span-2">
                        <dt className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">메모</dt>
                        <dd className="whitespace-pre-line text-text-primaryLight dark:text-text-primaryDark">
                          {selectedHistoryGroup.latest.note}
                        </dd>
                      </div>
                    ) : null}
                    {selectedHistoryGroup?.latest?.errorCode ? (
                      <div className="sm:col-span-2">
                        <dt className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">에러 코드</dt>
                        <dd className="text-accent-negative">{selectedHistoryGroup.latest.errorCode}</dd>
                      </div>
                    ) : null}
                  {(selectedHistoryGroup?.events?.length ?? 0) > 1 ? (
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
                        상태 타임라인
                      </p>
                      <ol className="mt-2 space-y-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                        {[...(selectedHistoryGroup?.events ?? [])].reverse().map((event, index) => {
                          const eventBadge = resolveReindexBadge(event.status);
                          const eventKey = `${event.taskId ?? event.queueId ?? event.timestamp ?? "event"}-${index}`;
                          return (
                            <li
                              key={eventKey}
                              className="flex items-start justify-between gap-3 rounded-lg border border-border-light px-3 py-2 dark:border-border-dark"
                            >
                              <div className="space-y-1 text-left">
                                <span className="font-medium text-text-primaryLight dark:text-text-primaryDark">
                                  {eventBadge.label}
                                </span>
                                <p>{formatHistoryTimestamp(event.timestamp)}</p>
                                {event.note ? (
                                  <p className="text-text-tertiaryLight dark:text-text-tertiaryDark">메모: {event.note}</p>
                                ) : null}
                              </div>
                              <span
                                className={clsx(
                                  "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
                                  eventBadge.className,
                                )}
                              >
                                {event.status ? event.status.toUpperCase() : "UNKNOWN"}
                              </span>
                            </li>
                          );
                        })}
                      </ol>
                    </div>
                  ) : null}
            </>
          ) : (
            <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">재색인 기록이 아직 없어요.</p>
          )}
        </div>
    </section>
  );
}

