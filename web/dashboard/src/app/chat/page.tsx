"use client";

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { Route } from 'next';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { nanoid } from 'nanoid';
import { AppShell } from '@/components/layout/AppShell';
import { ChatHistoryList } from '@/components/chat/ChatHistoryList';
import { ChatMessageBubble } from '@/components/chat/ChatMessage';
import { ChatInput } from '@/components/chat/ChatInput';
import { ChatContextPanel } from '@/components/chat/ChatContextPanel';
import { EmptyState } from '@/components/ui/EmptyState';
import { PlanLock } from '@/components/ui/PlanLock';
import {
  createMessage as createChatMessageApi,
  ApiError,
  postRagQuery,
  streamRagQuery,
  type RagQueryRequestPayload
} from '@/lib/chatApi';
import {
  useChatStore,
  selectActiveSession,
  selectIsHydrated,
  selectStoreLoading,
  selectPersistenceError,
  type RagEvidenceItem,
  type EvidenceHighlight,
  type GuardrailTelemetry,
  type MetricsTelemetry,
  type ChatMessageMeta
} from '@/store/chatStore';
import { usePlanTier, usePlanStore } from '@/store/planStore';
import { useToastStore } from '@/store/toastStore';

type RagApiContext = {
  chunk_id?: string;
  id?: string;
  content?: string;
  section?: string;
  type?: string;
  page_number?: number;
  score?: number;
  metadata?: Record<string, unknown>;
  source?: string;
  source_url?: string;
  viewer_url?: string;
  download_url?: string;
  diff_type?: string;
  previous_quote?: string;
  previous_section?: string;
  previous_page_number?: number;
  previous_anchor?: Record<string, unknown>;
  previous_source_reliability?: string;
  previous_self_check?: Record<string, unknown>;
  diff_changed_fields?: string[];
};

type RagApiHighlight = {
  chunk_id?: string;
  id?: string;
  page_number?: number;
  section?: string;
  type?: string;
  metadata?: Record<string, unknown>;
};

type RagApiResponse = {
  answer?: string;
  context?: RagApiContext[];
  citations?: Record<string, string[]>;
  warnings?: string[];
  highlights?: RagApiHighlight[];
  error?: string | null;
  original_answer?: string | null;
  model_used?: string | null;
  trace_id?: string | null;
  judge_decision?: string | null;
  judge_reason?: string | null;
  rag_mode?: string | null;
  meta?: Record<string, unknown>;
};

type ChatQuotaNotice = {
  message: string;
  planTier?: string;
  limit?: number | null;
  remaining?: number | null;
  resetAt?: string | null;
};

type QuotaErrorContext = {
  sessionId: string;
  assistantMessageId: string;
  question: string;
  userMessageId: string;
  documentTitle?: string | null;
  documentUrl?: string | null;
};

const ASSISTANT_LOADING_RESPONSE = '답변을 준비하고 있어요. 잠시만 기다려주세요.';
const ASSISTANT_ERROR_RESPONSE =
  '답변을 생성하는 중 문제가 발생했습니다. 잠시 후 다시 시도하거나 질문을 다시 작성해주세요.';

const CITATION_LABELS: Record<string, string> = {
  page: '페이지',
  table: '표',
  footnote: '각주'
};

const translateCitationKey = (rawKey: string): string => {
  const normalized = rawKey.trim().toLowerCase();
  if (!normalized) {
    return rawKey;
  }
  return CITATION_LABELS[normalized] ?? rawKey;
};

const PLAN_TIER_LABELS: Record<string, string> = {
  free: 'Free',
  pro: 'Pro',
  enterprise: 'Enterprise'
};

const clampPercent = (value: number) => Math.min(100, Math.max(0, value));

const parseNumeric = (candidate: unknown): number | null => {
  if (typeof candidate === 'number' && Number.isFinite(candidate)) {
    return candidate;
  }
  const parsed = Number(candidate);
  return Number.isFinite(parsed) ? parsed : null;
};

const pickNumericField = (metadata: Record<string, unknown>, ...keys: string[]): number | null => {
  for (const key of keys) {
    const value = parseNumeric(metadata[key]);
    if (value !== null) {
      return value;
    }
  }
  return null;
};

const derivePercentRange = (
  metadata: Record<string, unknown>,
  axis: 'x' | 'y',
  fallbackStart: number,
  fallbackLength: number
): { start: number; end: number } => {
  const startKeys = axis === 'y' ? ['y_start_pct', 'yStartPct'] : ['x_start_pct', 'xStartPct'];
  const endKeys = axis === 'y' ? ['y_end_pct', 'yEndPct'] : ['x_end_pct', 'xEndPct'];
  const dimensionKeys = axis === 'y' ? ['page_height', 'pageHeight'] : ['page_width', 'pageWidth'];
  const bboxIndex = axis === 'y' ? { start: 1, end: 3 } : { start: 0, end: 2 };

  const startDirect = pickNumericField(metadata, ...startKeys);
  const endDirect = pickNumericField(metadata, ...endKeys);
  if (startDirect !== null && endDirect !== null) {
    const start = clampPercent(startDirect);
    const end = clampPercent(endDirect);
    if (end > start) {
      return { start, end };
    }
    return { start, end: clampPercent(start + fallbackLength) };
  }

  const bbox = Array.isArray(metadata.bbox) ? metadata.bbox : null;
  const dimension = pickNumericField(metadata, ...dimensionKeys);
  if (bbox && bbox.length >= 4 && dimension && dimension > 0) {
    const startRaw = parseNumeric(bbox[bboxIndex.start]);
    const endRaw = parseNumeric(bbox[bboxIndex.end]);
    if (startRaw !== null && endRaw !== null) {
      const start = clampPercent((startRaw / dimension) * 100);
      const end = clampPercent((endRaw / dimension) * 100);
      if (end > start) {
        return { start, end };
      }
      return { start, end: clampPercent(start + fallbackLength) };
    }
  }

  const safeStart = clampPercent(fallbackStart);
  return {
    start: safeStart,
    end: clampPercent(safeStart + fallbackLength)
  };
};

const buildHighlights = (highlights: RagApiHighlight[]): Map<string, EvidenceHighlight> => {
  const map = new Map<string, EvidenceHighlight>();

  highlights.forEach((highlight) => {
    const keys = [highlight.chunk_id, highlight.id].filter(
      (candidate): candidate is string => typeof candidate === 'string' && candidate.trim().length > 0
    );
    if (!keys.length) {
      return;
    }

    const metadata = highlight.metadata ?? {};
    const yRange = derivePercentRange(metadata, 'y', 10, 30);
    const xRange = derivePercentRange(metadata, 'x', 0, 100);
    const pageNumber = typeof highlight.page_number === 'number' ? highlight.page_number : 0;

    const entry: EvidenceHighlight = {
      id: highlight.id ?? keys[0],
      page: pageNumber,
      yStartPct: yRange.start,
      yEndPct: yRange.end,
      xStartPct: xRange.start,
      xEndPct: xRange.end
    };

    keys.forEach((key) => map.set(key, entry));
  });

  return map;
};

const buildEvidenceItems = (
  context: RagApiContext[],
  highlightMap: Map<string, EvidenceHighlight>,
  fallbackUrl?: string
): RagEvidenceItem[] =>
  context.reduce<RagEvidenceItem[]>((acc, entry, index) => {
    const baseId = entry.chunk_id ?? entry.id ?? `context-${index}`;
    const snippet = typeof entry.content === 'string' ? entry.content.trim() : '';
    if (!baseId || !snippet) {
      return acc;
    }

    const highlightKey = entry.chunk_id ?? entry.id ?? '';
    const pageNumber = typeof entry.page_number === 'number' ? entry.page_number : undefined;
    const score = typeof entry.score === 'number' ? entry.score : undefined;

    acc.push({
      id: baseId,
      title: entry.section ?? `근거 ${index + 1}`,
      snippet,
      sourceUrl: entry.source_url ?? entry.viewer_url ?? entry.download_url ?? fallbackUrl,
      page: pageNumber,
      score,
      chunkType: entry.type,
      metadata: entry.metadata ?? undefined,
      highlightRange: highlightKey ? highlightMap.get(highlightKey) : undefined
    });

    return acc;
  }, []);

const buildCitationText = (citations: Record<string, string[]> | undefined) => {
  if (!citations) return '';
  const segments = Object.entries(citations)
    .filter(([, values]) => values && values.length)
    .map(([key, values]) => {
      const label = CITATION_LABELS[key] ?? key;
      return `${label}: ${Array.from(new Set(values)).join(', ')}`;
    });
  return segments.length ? `출처: ${segments.join(' | ')}` : '';
};

const toGuardrailMessage = (code: string, judgeReason?: string): string => {
  if (!code) {
    return '';
  }
  if (code.startsWith('intent_filter')) {
    return '';
  }
  if (code.startsWith('missing_citations')) {
    const parts = code.split(':')[1];
    if (!parts) {
      return '필수 인용 정보가 일부 누락되었습니다.';
    }
    const labels = parts
      .split(',')
      .map((part) => translateCitationKey(part.trim()))
      .filter(Boolean);
    return `필수 인용 정보가 누락되었습니다 (${labels.join(', ')}).`;
  }
  if (code.startsWith('guardrail_violation_judge')) {
    const reasonFromCode = code.split(':').slice(1).join(':').trim();
    const reason = reasonFromCode || judgeReason;
    if (reason) {
      return `규제 준수를 위해 일부 답변이 숨겨졌습니다: ${reason}`;
    }
    return '규제 준수상 위험 요소가 감지되어 일부 답변이 숨겨졌습니다.';
  }
  if (code.startsWith('guardrail_violation')) {
    return '투자자 보호 규칙에 따라 답변을 안전하게 정제했습니다.';
  }
  if (code.startsWith('judge_block')) {
    if (judgeReason && judgeReason.trim().length > 0) {
      return `규제 준수를 위해 답변이 숨겨졌습니다: ${judgeReason}`;
    }
    const reason = code.split(':').slice(1).join(':').trim();
    return reason
      ? `규제 준수를 위해 답변이 숨겨졌습니다: ${reason}`
      : '규제 준수상 위험 요소가 감지되어 답변이 숨겨졌습니다.';
  }
  if (code === 'judge_evaluation_failed') {
    return '규제 검수 모델 평가에 실패했습니다. 잠시 후 다시 시도해 주세요.';
  }
  return code;
};

const deriveGuardrailTelemetry = (
  warnings: string[] | undefined,
  error: string | null | undefined,
  judgeReason?: string
): GuardrailTelemetry => {
  const rawWarnings = warnings ?? [];
  const hasIntentWarning = rawWarnings.some((warning) => warning.startsWith('intent_filter'));
  const warningMessages = rawWarnings
    .filter((warning) => !warning.startsWith('intent_filter'))
    .map((warning) => toGuardrailMessage(warning, judgeReason))
    .filter((message) => Boolean(message));

  if (error && error.startsWith('intent_filter')) {
    return { status: 'ready', level: 'pass', message: '' };
  }

  if (!error && hasIntentWarning) {
    return { status: 'ready', level: 'pass', message: '' };
  }

  if (error) {
    if (error.startsWith('missing_citations')) {
      const combined = [toGuardrailMessage(error, judgeReason), ...warningMessages];
      return {
        status: 'ready',
        level: 'warn',
        message: combined.filter(Boolean).join('\n')
      };
    }
    if (error.startsWith('guardrail_violation_judge')) {
      const combined = [toGuardrailMessage(error, judgeReason), ...warningMessages];
      return {
        status: 'ready',
        level: 'fail',
        message: combined.filter(Boolean).join('\n')
      };
    }
    if (error.startsWith('guardrail_violation')) {
      const combined = [toGuardrailMessage(error, judgeReason), ...warningMessages];
      return {
        status: 'ready',
        level: 'fail',
        message: combined.filter(Boolean).join('\n')
      };
    }
    if (error.startsWith('judge_block')) {
      return {
        status: 'ready',
        level: 'fail',
        message: judgeReason || toGuardrailMessage(error, judgeReason)
      };
    }
    return {
      status: 'error',
      errorMessage: toGuardrailMessage(error, judgeReason) || `알 수 없는 오류가 발생했습니다: ${error}`
    };
  }

  if (warningMessages.length > 0) {
    return {
      status: 'ready',
      level: 'warn',
      message: warningMessages.join('\n')
    };
  }

  return {
    status: 'ready',
    level: 'pass',
    message: ''
  };
};

const idleMetricsTelemetry: MetricsTelemetry = { status: 'idle', items: [] };

const formatTimestamp = () =>
  new Date().toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit'
  });

const deriveSessionTitleFromQuestion = (question: string) => {
  const normalized = question.replace(/\s+/g, ' ').trim();
  if (!normalized) {
    return '새 대화';
  }
  const firstSegment = normalized.split(/[.!?\n]/)[0]?.trim() ?? normalized;
  if (!firstSegment) {
    return '새 대화';
  }
  return firstSegment.length > 40 ? `${firstSegment.slice(0, 40)}…` : firstSegment;
};

export default function ChatPage() {
  const searchParams = useSearchParams();
  const searchParamsString = searchParams?.toString() ?? "";
  const router = useRouter();
  const pathname = usePathname();
  const querySessionId = searchParams?.get('session') ?? null;
  const planTier = usePlanTier();
  const { planInitialized, planLoading, ragEnabled, planError, chatDailyLimit } = usePlanStore((state) => ({
    planInitialized: state.initialized,
    planLoading: state.loading,
    ragEnabled: state.featureFlags.ragCore,
    planError: state.error,
    chatDailyLimit: state.quota.chatRequestsPerDay
  }));
  const [chatQuotaNotice, setChatQuotaNotice] = useState<ChatQuotaNotice | null>(null);
  const quotaNoticeLimit = chatQuotaNotice?.limit ?? chatDailyLimit ?? null;
  const quotaPlanLabel = useMemo(() => {
    const key = (chatQuotaNotice?.planTier ?? planTier) ?? 'free';
    return PLAN_TIER_LABELS[key] ?? PLAN_TIER_LABELS.free;
  }, [chatQuotaNotice, planTier]);
  const quotaResetText = useMemo(() => {
    if (!chatQuotaNotice?.resetAt) {
      return '자정이 지나면 자동으로 초기화돼요.';
    }
    const resetDate = new Date(chatQuotaNotice.resetAt);
    if (Number.isNaN(resetDate.getTime())) {
      return '곧 다시 이용하실 수 있어요.';
    }
    return `${new Intl.DateTimeFormat('ko-KR', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: 'numeric'
    }).format(resetDate)}에 초기화돼요.`;
  }, [chatQuotaNotice]);
  const handlePlanRedirect = useCallback(() => {
    router.push('/settings?panel=plan');
  }, [router]);
  const dismissQuotaNotice = useCallback(() => setChatQuotaNotice(null), []);

  const sessions = useChatStore((state) => state.sessions);
  const activeSessionId = useChatStore((state) => state.activeSessionId);
  const hydrateSessions = useChatStore((state) => state.hydrateSessions);
  const setActiveSession = useChatStore((state) => state.setActiveSession);
  const addMessage = useChatStore((state) => state.addMessage);
  const updateMessage = useChatStore((state) => state.updateMessage);
  const createSession = useChatStore((state) => state.createSession);
  const removeSession = useChatStore((state) => state.removeSession);
  const clearSessions = useChatStore((state) => state.clearSessions);
  const renameSession = useChatStore((state) => state.renameSession);
  const setSessionEvidence = useChatStore((state) => state.setSessionEvidence);
  const setSessionTelemetry = useChatStore((state) => state.setSessionTelemetry);
  const showToast = useToastStore((state) => state.show);
  const handleChatQuotaExceeded = useCallback(
    (error: ApiError, context?: QuotaErrorContext) => {
      if (error.code !== 'plan.chat_quota_exceeded') {
        return false;
      }
      const detail = (error.detail ?? {}) as Record<string, unknown>;
      const quotaDetail = (detail?.quota ?? {}) as Record<string, unknown>;
      const limit =
        typeof quotaDetail.chatRequestsPerDay === 'number'
          ? quotaDetail.chatRequestsPerDay
          : chatDailyLimit ?? null;
      const remaining =
        typeof quotaDetail.remaining === 'number' ? quotaDetail.remaining : null;
      const resetAt = typeof quotaDetail.resetAt === 'string' ? quotaDetail.resetAt : null;
      const message =
        typeof detail?.message === 'string'
          ? (detail.message as string)
          : '오늘 사용할 수 있는 AI 대화 횟수를 모두 사용했습니다.';

      setChatQuotaNotice({
        message,
        planTier: typeof detail?.planTier === 'string' ? (detail.planTier as string) : planTier,
        limit,
        remaining,
        resetAt
      });

      if (context) {
        updateMessage(context.sessionId, context.assistantMessageId, {
          content: message,
          meta: {
            status: 'error',
            retryable: false,
            errorMessage: message,
            question: context.question,
            userMessageId: context.userMessageId
          }
        });
        setSessionEvidence(context.sessionId, {
          status: 'error',
          items: [],
          activeId: undefined,
          confidence: undefined,
          errorMessage: message,
          documentTitle: context.documentTitle,
          documentUrl: context.documentUrl
        });
        setSessionTelemetry(context.sessionId, {
          guardrail: { status: 'error', message },
          metrics: idleMetricsTelemetry
        });
      }

      showToast({
        intent: 'warning',
        title: '오늘 할당량을 모두 사용했어요',
        message: 'Pro 플랜으로 업그레이드하면 더 여유롭게 대화할 수 있어요.'
      });
      return true;
    },
    [chatDailyLimit, planTier, setSessionEvidence, setSessionTelemetry, showToast, updateMessage]
  );
  const focusEvidence = useChatStore((state) => state.focus_evidence_item);
  const activeSession = useChatStore(selectActiveSession);
  const persistenceError = useChatStore(selectPersistenceError);
  const isHydrated = useChatStore(selectIsHydrated);
  const isLoading = useChatStore(selectStoreLoading);
  const resetStoreError = useChatStore((state) => state.resetError);

  const contextSummary = activeSession?.context?.summary;
  const isFilingContext = activeSession?.context?.type === 'filing';
  const filingReferenceId =
    activeSession?.context?.type === 'filing' ? activeSession.context.referenceId : undefined;

  const navigateToSession = useCallback(
    (sessionId: string) => {
      const nextQuery = new URLSearchParams(searchParamsString);
      nextQuery.set('session', sessionId);
      const target = `${pathname}?${nextQuery.toString()}` as Route;
      router.push(target);
    },
    [pathname, router, searchParamsString]
  );

  useEffect(() => {
    if (!isHydrated) {
      void hydrateSessions();
    }
  }, [hydrateSessions, isHydrated]);

  useEffect(() => {
    if (!isHydrated) {
      return;
    }
    if (querySessionId) {
      const exists = sessions.some((session) => session.id === querySessionId);
      if (exists) {
        if (activeSessionId !== querySessionId) {
          void setActiveSession(querySessionId);
        }
      } else {
        router.replace(pathname as Route);
      }
    } else if (activeSessionId) {
      void setActiveSession(null);
    }
  }, [querySessionId, sessions, activeSessionId, setActiveSession, router, pathname, isHydrated]);

  useEffect(() => {
    if (persistenceError) {
      showToast({
        intent: 'warning',
        title: '저장 실패',
        message: persistenceError
      });
      resetStoreError();
    }
  }, [persistenceError, resetStoreError, showToast]);

  const handleSelectSession = useCallback(
    (sessionId: string) => {
      void (async () => {
        await setActiveSession(sessionId);
        navigateToSession(sessionId);
      })();
    },
    [navigateToSession, setActiveSession]
  );

  const handleCreateSession = useCallback(() => {
    void (async () => {
      try {
        const newSessionId = await createSession({ context: { type: 'custom' } });
        await setActiveSession(newSessionId);
        navigateToSession(newSessionId);
      } catch (error) {
        const message = error instanceof Error ? error.message : '새 세션을 생성하지 못했습니다.';
        showToast({
          intent: 'error',
          title: '세션 생성 실패',
          message
        });
      }
    })();
  }, [createSession, navigateToSession, setActiveSession, showToast]);

  const handleDeleteSession = useCallback(
    (sessionId: string) => {
      void (async () => {
        const stateBefore = useChatStore.getState();
        const wasActive = stateBefore.activeSessionId === sessionId;
        await removeSession(sessionId);
        const nextState = useChatStore.getState();
        if (wasActive) {
          if (nextState.activeSessionId) {
            navigateToSession(nextState.activeSessionId);
          } else {
            router.replace(pathname as Route);
          }
        }
      })();
    },
    [navigateToSession, pathname, removeSession, router]
  );

  const handleClearSessions = useCallback(() => {
    void (async () => {
      await clearSessions();
      router.replace(pathname as Route);
    })();
  }, [clearSessions, pathname, router]);

  const handleOpenFiling = useCallback(() => {
    if (!isFilingContext) return;
    if (filingReferenceId) {
      const filingsRoute = `/filings?filingId=${filingReferenceId}` as Route;
      router.push(filingsRoute);
    } else {
      router.push('/filings' as Route);
    }
  }, [filingReferenceId, isFilingContext, router]);
  const runQuery = useCallback(
    async ({
      question,
      sessionId,
      assistantMessageId,
      userMessageId,
      turnId,
      retryOfMessageId = null
    }: {
      question: string;
      sessionId: string;
      assistantMessageId: string;
      userMessageId: string;
      turnId: string;
      retryOfMessageId?: string | null;
    }) => {
      const sessionState = useChatStore.getState().sessions.find((session) => session.id === sessionId);
      const referenceId =
        sessionState?.context?.type === 'filing' ? sessionState.context.referenceId : undefined;
      const documentTitle = sessionState?.evidence?.documentTitle ?? sessionState?.title ?? '대화';
      const documentUrl = sessionState?.evidence?.documentUrl;
      const quotaContext: QuotaErrorContext = {
        sessionId,
        assistantMessageId,
        question,
        userMessageId,
        documentTitle,
        documentUrl
      };

      updateMessage(sessionId, assistantMessageId, {
        meta: {
          status: 'pending',
          retryable: false,
          errorMessage: undefined,
          question,
          userMessageId
        }
      });

      setSessionEvidence(sessionId, {
        status: 'loading',
        items: [],
        activeId: undefined,
        confidence: undefined,
        documentTitle,
        documentUrl
      });

      setSessionTelemetry(sessionId, {
        guardrail: { status: 'loading', message: '답변을 생성하는 중입니다.' },
        metrics: idleMetricsTelemetry
      });

      const ragPayload: RagQueryRequestPayload = {
        question,
        session_id: sessionId,
        turn_id: turnId,
        user_message_id: userMessageId,
        assistant_message_id: assistantMessageId,
        retry_of_message_id: retryOfMessageId ?? null,
        idempotency_key: nanoid(),
        run_self_check: true,
        meta: {}
      };
      if (referenceId) {
        ragPayload.filing_id = referenceId;
      }

      let completed = false;
      let streamedAnswer = '';

      const finalizeResponse = (payload: RagApiResponse) => {
        setChatQuotaNotice(null);
        completed = true;
        const answerText =
          typeof payload.answer === 'string' && payload.answer.trim().length
            ? payload.answer
            : streamedAnswer || ASSISTANT_ERROR_RESPONSE;

        const rawCitations =
          payload.citations && typeof payload.citations === 'object' ? payload.citations : {};
        const sanitizedCitations: Record<string, string[]> = {};
        Object.entries(rawCitations as Record<string, unknown>).forEach(([key, value]) => {
          if (Array.isArray(value)) {
            sanitizedCitations[key] = value.filter((item): item is string => typeof item === 'string');
          }
        });

        const citationText = buildCitationText(sanitizedCitations);
        const combinedAnswer = citationText ? `${answerText}\n\n${citationText}` : answerText;

        const payloadWarnings =
          Array.isArray(payload.warnings)
            ? payload.warnings.filter((item): item is string => typeof item === 'string')
            : [];

        const judgeDecision = payload.judge_decision ?? undefined;
        const judgeReason = payload.judge_reason ?? undefined;
        const traceId = payload.trace_id ?? undefined;
        const payloadError = typeof payload.error === 'string' ? payload.error : null;

        const guardrailMessage = judgeDecision ? toGuardrailMessage(judgeDecision, judgeReason) : undefined;
        const isBlocked =
          (typeof judgeDecision === 'string' && judgeDecision.toLowerCase().includes('block')) ||
          (payloadError
            ? payloadError.startsWith('judge_block') || payloadError.startsWith('guardrail_violation')
            : false);

        const nextMeta: ChatMessageMeta = {
          status: isBlocked ? 'blocked' : 'ready',
          retryable: false,
          question,
          userMessageId,
          model: typeof payload.model_used === 'string' ? payload.model_used : undefined,
          warnings: payloadWarnings,
          citations: sanitizedCitations,
          judgeDecision,
          judgeReason,
          traceId
        };

        if (isBlocked) {
          nextMeta.errorMessage = guardrailMessage ?? '규제 준수를 위해 답변이 차단되었습니다.';
        }

        updateMessage(sessionId, assistantMessageId, {
          content: combinedAnswer,
          meta: nextMeta
        });

        const context = Array.isArray(payload.context) ? (payload.context as RagApiContext[]) : [];
        const highlights = Array.isArray(payload.highlights)
          ? (payload.highlights as RagApiHighlight[])
          : [];
        const highlightMap = buildHighlights(highlights);
        const evidenceItems = buildEvidenceItems(context, highlightMap, documentUrl);

        const evidenceState = evidenceItems.length
          ? {
              status: 'ready' as const,
              items: evidenceItems,
              activeId: evidenceItems[0]?.id,
              confidence: undefined,
              documentTitle,
              documentUrl
            }
          : {
              status: 'ready' as const,
              items: [],
              activeId: undefined,
              confidence: undefined,
              documentTitle,
              documentUrl
            };

        setSessionEvidence(sessionId, evidenceState);
        if (evidenceItems[0]?.id) {
          focusEvidence(evidenceItems[0].id);
        }

        const guardrail = deriveGuardrailTelemetry(payloadWarnings, payloadError, judgeReason);
        setSessionTelemetry(sessionId, {
          guardrail,
          metrics: idleMetricsTelemetry
        });

        if (guardrail.status === 'ready' && guardrail.message && guardrail.level && guardrail.level !== 'pass') {
          const intent = guardrail.level === 'fail' ? 'error' : 'warning';
          const title = guardrail.level === 'fail' ? '답변이 제한되었습니다' : '주의가 필요합니다';
          showToast({
            intent,
            title,
            message: guardrail.message
          });
        }

        const retrievalMeta = (payload.meta?.retrieval ?? {}) as Record<string, unknown>;
        const guardrailMeta = (payload.meta?.guardrail ?? {}) as Record<string, unknown>;
        const rawRagMode =
          (typeof payload.rag_mode === 'string' && payload.rag_mode) ||
          (typeof retrievalMeta.rag_mode === 'string' && String(retrievalMeta.rag_mode)) ||
          (typeof guardrailMeta.rag_mode === 'string' && String(guardrailMeta.rag_mode)) ||
          (typeof guardrailMeta.ragMode === 'string' && String(guardrailMeta.ragMode));
        const normalizedRagMode = rawRagMode ? rawRagMode.toLowerCase() : undefined;
        if (normalizedRagMode === 'optional') {
          showToast({
            intent: 'info',
            title: '문서 검색은 선택형으로 진행했어요',
            message: '필요하면 문서 근거를 더 찾아볼게요.'
          });
        } else if (normalizedRagMode === 'none') {
          showToast({
            intent: 'warning',
            title: '문서 검색 없이 답변했어요',
            message: '질문 특성상 직접 모델이 답변했어요.'
          });
        }
      };

      try {
        await streamRagQuery(ragPayload, {
          onEvent: (event) => {
            if (event.event === 'chunk') {
              streamedAnswer += event.delta;
              updateMessage(sessionId, assistantMessageId, {
                content: streamedAnswer || ASSISTANT_LOADING_RESPONSE,
                meta: {
                  status: 'streaming',
                  retryable: false,
                  question,
                  userMessageId,
                  turnId
                }
              });
            } else if (event.event === 'metadata') {
              updateMessage(sessionId, assistantMessageId, {
                meta: {
                  status: 'streaming',
                  retryable: false,
                  question,
                  userMessageId,
                  turnId,
                  ...event.meta
                }
              });
            } else if (event.event === 'done') {
              const payload = event.payload as RagApiResponse;
              if (!payload.answer && streamedAnswer) {
                payload.answer = streamedAnswer;
              }
              finalizeResponse(payload);
            } else if (event.event === 'error') {
              completed = true;
              const errorMessage = event.message || '스트리밍 중 오류가 발생했습니다.';
              updateMessage(sessionId, assistantMessageId, {
                meta: {
                  status: 'error',
                  retryable: true,
                  errorMessage,
                  question,
                  userMessageId
                }
              });
              setSessionTelemetry(sessionId, {
                guardrail: { status: 'error', message: errorMessage, errorMessage },
                metrics: idleMetricsTelemetry
              });
              showToast({
                intent: 'error',
                title: '스트리밍 오류',
                message: errorMessage
              });
            }
          }
        });
      } catch (error) {
        if (error instanceof ApiError && handleChatQuotaExceeded(error, quotaContext)) {
          completed = true;
          return;
        }
        console.warn('Streaming query failed', error);
      }

      if (completed) {
        return;
      }

      try {
        const payload = (await postRagQuery(ragPayload)) as RagApiResponse;
        if (!payload.answer && streamedAnswer) {
          payload.answer = streamedAnswer;
        }
        finalizeResponse(payload);
      } catch (error) {
        if (error instanceof ApiError && handleChatQuotaExceeded(error, quotaContext)) {
          return;
        }
        console.error('RAG query failed', error);
        const fallbackMessage = error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다.';
        updateMessage(sessionId, assistantMessageId, {
          content: ASSISTANT_ERROR_RESPONSE,
          meta: {
            status: 'error',
            retryable: true,
            errorMessage: fallbackMessage,
            question,
            userMessageId
          }
        });
        setSessionEvidence(sessionId, {
          status: 'error',
          items: [],
          errorMessage: fallbackMessage,
          activeId: undefined,
          confidence: undefined,
          documentTitle,
          documentUrl
        });
        setSessionTelemetry(sessionId, {
          guardrail: { status: 'error', message: fallbackMessage, errorMessage: fallbackMessage },
          metrics: idleMetricsTelemetry
        });
        showToast({
          intent: 'error',
          title: '분석 실패',
          message: fallbackMessage
        });
      }
    },
    [
      focusEvidence,
      handleChatQuotaExceeded,
      setSessionEvidence,
      setSessionTelemetry,
      showToast,
      updateMessage
    ]
  );

  const handleSend = useCallback(
    async (rawInput: string) => {
      const trimmed = rawInput.trim();
      if (!trimmed) return;

      try {
        let targetSessionId = activeSessionId;
        if (!targetSessionId) {
          targetSessionId = await createSession({ context: { type: 'custom' } });
          await setActiveSession(targetSessionId);
          navigateToSession(targetSessionId);
        } else {
          await setActiveSession(targetSessionId);
        }

        const turnId = nanoid();
        const userRecord = await createChatMessageApi({
          session_id: targetSessionId,
          role: 'user',
          content: trimmed,
          turn_id: turnId,
          state: 'ready',
          meta: { status: 'ready' }
        });

        addMessage(targetSessionId, {
          id: userRecord.id,
          role: 'user',
          content: userRecord.content ?? trimmed,
          timestamp: userRecord.created_at,
          meta: {
            ...(typeof userRecord.meta === 'object' ? (userRecord.meta as Record<string, unknown>) : {}),
            status: 'ready'
          }
        });

        const sessionAfterUser = useChatStore.getState().sessions.find((session) => session.id === targetSessionId);
        if (sessionAfterUser) {
          const userCount = sessionAfterUser.messages.filter((message) => message.role === 'user').length;
          if (userCount === 1) {
            try {
              await renameSession(targetSessionId, deriveSessionTitleFromQuestion(trimmed));
            } catch (renameError) {
              console.warn('Failed to rename session', renameError);
            }
          }
        }

        const assistantRecord = await createChatMessageApi({
          session_id: targetSessionId,
          role: 'assistant',
          content: ASSISTANT_LOADING_RESPONSE,
          turn_id: turnId,
          state: 'pending',
          meta: {
            status: 'pending',
            retryable: false,
            question: trimmed,
            userMessageId: userRecord.id,
            turnId
          }
        });

        addMessage(targetSessionId, {
          id: assistantRecord.id,
          role: 'assistant',
          content: assistantRecord.content ?? ASSISTANT_LOADING_RESPONSE,
          timestamp: assistantRecord.created_at,
          meta: {
            ...(typeof assistantRecord.meta === 'object' ? (assistantRecord.meta as Record<string, unknown>) : {}),
            status: 'pending',
            retryable: false,
            question: trimmed,
            userMessageId: userRecord.id,
            turnId
          }
        });

        await runQuery({
          question: trimmed,
          sessionId: targetSessionId,
          assistantMessageId: assistantRecord.id,
          userMessageId: userRecord.id,
          turnId
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : '메시지를 전송하지 못했습니다.';
        showToast({
          intent: 'error',
          title: '전송 실패',
          message
        });
      }
    },
    [
      activeSessionId,
      addMessage,
      createSession,
      navigateToSession,
      renameSession,
      runQuery,
      setActiveSession,
      showToast
    ]
  );

  const handleRetry = useCallback(
    async (messageId: string) => {
      const sessionId = activeSessionId;
      if (!sessionId) {
        showToast({
          intent: 'warning',
          title: '세션을 찾을 수 없습니다',
          message: '재시도하려면 먼저 세션을 선택해 주세요.'
        });
        return;
      }

      const sessionState = useChatStore.getState().sessions.find((session) => session.id === sessionId);
      const targetMessage = sessionState?.messages.find((message) => message.id === messageId);
      if (!targetMessage) {
        showToast({
          intent: 'warning',
          title: '메시지를 찾지 못했습니다',
          message: '다시 시도할 메시지가 존재하지 않습니다.'
        });
        return;
      }

      const question =
        typeof targetMessage.meta?.question === 'string' ? targetMessage.meta.question.trim() : '';
      const userMessageId =
        typeof targetMessage.meta?.userMessageId === 'string' ? targetMessage.meta.userMessageId : null;
      const previousTurnId =
        typeof targetMessage.meta?.turnId === 'string' ? targetMessage.meta.turnId : null;

      if (!question || !userMessageId) {
        showToast({
          intent: 'warning',
          title: '재시도 정보를 찾지 못했습니다',
          message: '같은 질문을 새로 입력해 주세요.'
        });
        return;
      }

      const turnId = previousTurnId ?? nanoid();
      const timestamp = formatTimestamp();
      updateMessage(sessionId, messageId, {
        content: ASSISTANT_LOADING_RESPONSE,
        timestamp,
        meta: {
          status: 'pending',
          retryable: false,
          errorMessage: undefined,
          question,
          userMessageId,
          turnId
        }
      });

      await runQuery({
        question,
        sessionId,
        assistantMessageId: messageId,
        userMessageId,
        turnId,
        retryOfMessageId: messageId
      });
    },
    [activeSessionId, runQuery, showToast, updateMessage]
  );

  const messages = activeSession?.messages ?? [];
  const sessionTitle = activeSession?.title ?? '새 세션';
  const showEmptyState = messages.length === 0;
  const hasContextBanner = useMemo(() => Boolean(contextSummary), [contextSummary]);
  const disclaimer = useMemo(
    () =>
      '본 서비스는 일반 정보 제공용입니다. 투자·법률·세무 자문이 아니며 전문 자문을 대체하지 않습니다. 제공 정보의 정확성·완전성·적시성은 보장되지 않습니다. 매수/매도·소송·계약 등 의사결정은 사용자 책임입니다.',
    [],
  );

  if (!planInitialized) {
    return (
      <AppShell>
        <div className='flex min-h-[60vh] items-center justify-center px-6'>
          <div className='w-full max-w-2xl rounded-xl border border-dashed border-border-light/80 bg-white/70 p-6 text-center text-sm text-text-secondaryLight shadow-card dark:border-border-dark/70 dark:bg-background-cardDark/60 dark:text-text-secondaryDark'>
            {planLoading ? '플랜 정보를 불러오는 중입니다…' : '플랜 정보를 초기화하는 중입니다.'}
          </div>
        </div>
      </AppShell>
    );
  }

  if (!ragEnabled) {
    return (
      <AppShell>
        <div className='flex min-h-[60vh] items-center justify-center px-6'>
          <div className='w-full max-w-3xl'>
            <PlanLock
              requiredTier='pro'
              currentTier={planTier}
              title='AI 애널리스트는 Pro 플랜에서 열립니다.'
              description='근거 기반 Q&A, 증거 Diff, LightMem 문맥 유지는 Pro 업그레이드 후 이용할 수 있어요.'
            >
              {planError ? (
                <p className='mt-3 text-xs text-text-tertiaryLight dark:text-text-tertiaryDark'>
                  플랜 정보를 불러오지 못했습니다. 새로 고침 후에도 문제가 지속되면 문의해주세요.
                </p>
              ) : null}
            </PlanLock>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      {chatQuotaNotice ? (
        <div className='mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 shadow-card dark:border-amber-400/60 dark:bg-amber-950/40 dark:text-amber-100'>
          <div className='flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between'>
            <div>
              <p className='font-semibold text-amber-900 dark:text-amber-50'>{chatQuotaNotice.message}</p>
              <p className='mt-1 text-xs text-amber-800 dark:text-amber-200'>
                {quotaNoticeLimit
                  ? `${quotaPlanLabel} 플랜 하루 ${quotaNoticeLimit.toLocaleString('ko-KR')}회 한도가 모두 사용되었어요.`
                  : `${quotaPlanLabel} 플랜 하루 한도가 모두 사용되었어요.`}{' '}
                {quotaResetText}
              </p>
            </div>
            <div className='flex flex-wrap gap-2'>
              <button
                type='button'
                className='rounded-lg border border-primary bg-primary px-4 py-2 text-xs font-semibold text-white transition hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary'
                onClick={handlePlanRedirect}
              >
                플랜 카드로 이동
              </button>
              <button
                type='button'
                className='rounded-lg border border-amber-300 px-4 py-2 text-xs font-semibold text-amber-900 transition hover:bg-amber-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-400 dark:border-amber-500 dark:text-amber-100 dark:hover:bg-amber-500/10'
                onClick={dismissQuotaNotice}
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      ) : null}
      <div className='flex flex-col gap-6 lg:flex-row'>
        <ChatHistoryList
          sessions={sessions}
          selectedId={activeSessionId ?? undefined}
          onSelect={handleSelectSession}
          onNewSession={handleCreateSession}
          onDeleteSession={handleDeleteSession}
          onClearAll={handleClearSessions}
          persistenceError={persistenceError ?? undefined}
          disabled={isLoading || !isHydrated}
        />
        <div className='flex min-h-[70vh] flex-1 flex-col gap-4 rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark'>
          <div className='h-12 rounded-lg border border-border-light px-4 py-2 text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark'>
            세션: {sessionTitle}
          </div>
          {hasContextBanner && (
            <div className='rounded-lg border border-border-light bg-white/70 px-4 py-3 text-sm dark:border-border-dark dark:bg-white/5'>
              <div className='flex items-start justify-between gap-3'>
                <div>
                  <p className='text-[11px] font-semibold uppercase text-primary'>컨텍스트 요약</p>
                  {isFilingContext && filingReferenceId && (
                    <p className='text-[11px] text-text-secondaryLight dark:text-text-secondaryDark'>참조 ID: {filingReferenceId}</p>
                  )}
                </div>
                {isFilingContext && (
                  <button
                    type='button'
                    onClick={handleOpenFiling}
                    className='rounded-md border border-border-light px-3 py-1 text-xs font-semibold text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark'
                  >
                    공시 화면으로 이동
                  </button>
                )}
              </div>
              <p className='mt-3 leading-relaxed text-text-secondaryLight dark:text-text-secondaryDark'>{contextSummary}</p>
            </div>
          )}
          <div className='rounded-lg border border-dashed border-border-light bg-white/60 px-4 py-3 text-[11px] leading-relaxed text-text-secondaryLight dark:border-border-dark dark:bg-white/5 dark:text-text-secondaryDark'>
            {disclaimer}
          </div>
          <div className='flex-1 space-y-4 overflow-y-auto pr-2'>
            {showEmptyState ? (
              <EmptyState
                title='메시지가 없습니다'
                description="새 세션을 시작하거나 궁금한 점을 바로 질문해보세요."
                className='rounded-lg border border-border-light px-4 py-6 text-xs dark:border-border-dark'
              />
            ) : (
              messages.map((message) => (
                <ChatMessageBubble
                  key={message.id}
                  {...message}
                  onRetry={
                    message.role === 'assistant' && message.meta?.retryable && message.meta.status !== 'ready'
                      ? () => handleRetry(message.id)
                      : undefined
                  }
                />
              ))
            )}
          </div>
          <ChatInput onSubmit={handleSend} disabled={!isHydrated || isLoading} />
        </div>
        <ChatContextPanel />
      </div>
    </AppShell>
  );
}
