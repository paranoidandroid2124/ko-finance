"use client";

import { useCallback, useEffect, useMemo } from 'react';
import type { Route } from 'next';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { nanoid } from 'nanoid';
import { AppShell } from '@/components/layout/AppShell';
import { ChatHistoryList } from '@/components/chat/ChatHistoryList';
import { ChatMessageBubble } from '@/components/chat/ChatMessage';
import { ChatInput } from '@/components/chat/ChatInput';
import { ChatContextPanel } from '@/components/chat/ChatContextPanel';
import { EmptyState } from '@/components/ui/EmptyState';
import {
  useChatStore,
  selectActiveSession,
  selectIsHydrated,
  selectPersistenceError,
  type RagEvidenceItem,
  type EvidenceHighlight,
  type GuardrailTelemetry,
  type MetricsTelemetry,
  type ChatMessageMeta
} from '@/store/chatStore';
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
};

type RagStreamFinalPayload = RagApiResponse & {
  trace_id?: string | null;
  question?: string;
  filing_id?: string;
};

type RagStreamTokenEvent = { type: 'token'; text?: string };
type RagStreamFinalEvent = { type: 'final'; payload: RagStreamFinalPayload };
type RagStreamErrorEvent = { type: 'error'; message?: string };
type RagStreamEvent = RagStreamTokenEvent | RagStreamFinalEvent | RagStreamErrorEvent;


const ASSISTANT_LOADING_RESPONSE = '답변을 준비하고 있어요. 잠시만 기다려주세요.';
const ASSISTANT_UNAVAILABLE_RESPONSE =
  '현재는 공시 기반 질문에 대해 답변합니다. 공시 상세 화면에서 "질문하기" 버튼을 사용해 새 세션을 시작해주세요.';
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
  const warningMessages = (warnings ?? [])
    .map((warning) => toGuardrailMessage(warning, judgeReason))
    .filter((message) => Boolean(message));

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
    message: 'guardrail 경고 없음'
  };
};

const idleMetricsTelemetry: MetricsTelemetry = { status: 'idle', items: [] };

const formatTimestamp = () =>
  new Date().toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit'
  });

const resolveApiBase = () => {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!base) {
    return '';
  }
  return base.endsWith('/') ? base.slice(0, -1) : base;
};

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
  const router = useRouter();
  const pathname = usePathname();
  const querySessionId = searchParams?.get('session') ?? null;

  const sessions = useChatStore((state) => state.sessions);
  const activeSessionId = useChatStore((state) => state.activeSessionId);
  const setActiveSession = useChatStore((state) => state.setActiveSession);
  const addMessage = useChatStore((state) => state.addMessage);
  const updateMessage = useChatStore((state) => state.updateMessage);
  const createSession = useChatStore((state) => state.createSession);
  const removeSession = useChatStore((state) => state.removeSession);
  const clearSessions = useChatStore((state) => state.clearSessions);
  const renameSession = useChatStore((state) => state.renameSession);
  const setSessionEvidence = useChatStore((state) => state.setSessionEvidence);
  const setSessionTelemetry = useChatStore((state) => state.setSessionTelemetry);
  const focusEvidence = useChatStore((state) => state.focus_evidence_item);
  const activeSession = useChatStore(selectActiveSession);
  const persistenceError = useChatStore(selectPersistenceError);
  const isHydrated = useChatStore(selectIsHydrated);
  const showToast = useToastStore((state) => state.show);

  const contextSummary = activeSession?.context?.summary;
  const isFilingContext = activeSession?.context?.type === 'filing';
  const filingReferenceId = activeSession?.context?.referenceId;

  const navigateToSession = useCallback(
    (sessionId: string) => {
      const nextQuery = new URLSearchParams(searchParams.toString());
      nextQuery.set('session', sessionId);
      const target = `${pathname}?${nextQuery.toString()}` as Route;
      router.push(target);
    },
    [pathname, router, searchParams]
  );

  useEffect(() => {
    if (querySessionId) {
      const exists = sessions.some((session) => session.id === querySessionId);
      if (exists) {
        if (activeSessionId !== querySessionId) {
          setActiveSession(querySessionId);
        }
      } else {
        router.replace(pathname as Route);
      }
    } else if (activeSessionId) {
      setActiveSession(null);
    }
  }, [querySessionId, sessions, activeSessionId, setActiveSession, router, pathname]);

  useEffect(() => {
    if (persistenceError) {
      showToast({
        intent: 'warning',
        title: '저장 실패',
        message: persistenceError
      });
    }
  }, [persistenceError, showToast]);

  const handleSelectSession = useCallback(
    (sessionId: string) => {
      navigateToSession(sessionId);
    },
    [navigateToSession]
  );

  const handleCreateSession = useCallback(() => {
    const newSessionId = createSession();
    navigateToSession(newSessionId);
  }, [createSession, navigateToSession]);

  const handleDeleteSession = useCallback(
    (sessionId: string) => {
      const stateBefore = useChatStore.getState();
      const wasActive = stateBefore.activeSessionId === sessionId;
      removeSession(sessionId);
      const nextState = useChatStore.getState();
      if (wasActive) {
        if (nextState.activeSessionId) {
          navigateToSession(nextState.activeSessionId);
        } else {
          router.replace(pathname as Route);
        }
      }
    },
    [navigateToSession, pathname, removeSession, router]
  );

  const handleClearSessions = useCallback(() => {
    clearSessions();
    router.replace(pathname as Route);
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
      isRetry = false
    }: {
      question: string;
      sessionId: string;
      assistantMessageId: string;
      userMessageId: string;
      isRetry?: boolean;
    }) => {
      const sessionState = useChatStore.getState().sessions.find((session) => session.id === sessionId);
      const referenceId =
        sessionState?.context?.type === 'filing' ? sessionState.context.referenceId : undefined;
      const documentTitle = sessionState?.evidence?.documentTitle ?? sessionState?.title;
      const documentUrl = sessionState?.evidence?.documentUrl;

      if (!referenceId) {
        const warningMessage = '공시 세션이 필요합니다.';
        updateMessage(sessionId, assistantMessageId, {
          content: ASSISTANT_UNAVAILABLE_RESPONSE,
          meta: {
            status: 'error',
            errorMessage: warningMessage,
            retryable: false,
            question,
            userMessageId
          }
        });
        setSessionEvidence(sessionId, {
          status: 'error',
          items: [],
          errorMessage: 'Filing context is required for RAG queries.',
          activeId: undefined,
          confidence: undefined,
          documentTitle,
          documentUrl
        });
        setSessionTelemetry(sessionId, {
          guardrail: { status: 'ready', level: 'warn', message: warningMessage },
          metrics: idleMetricsTelemetry
        });
        showToast({
          intent: 'warning',
          title: '세션 정보를 찾을 수 없어요',
          message: warningMessage
        });
        return;
      }

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
        guardrail: { status: 'loading' },
        metrics: { status: 'loading', items: [] }
      });

      const finalizeResponse = (payload: RagStreamFinalPayload) => {
        const answerText =
          typeof payload.answer === 'string' && payload.answer.trim().length
            ? payload.answer
            : ASSISTANT_ERROR_RESPONSE;

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
          model: payload.model_used,
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
      };

      const fetchStandard = async () => {
        updateMessage(sessionId, assistantMessageId, {
          meta: { status: 'streaming', retryable: false }
        });

        const response = await fetch(`${resolveApiBase()}/api/v1/rag/query`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question,
            filing_id: referenceId,
            top_k: 5,
            run_self_check: true
          })
        });

        if (!response.ok) {
          const detail = await response.text();
          const message = detail || `RAG 호출에 실패했습니다. (HTTP ${response.status})`;
          throw new Error(message);
        }

        const payload = (await response.json()) as RagApiResponse;
        finalizeResponse(payload);
        return true;
      };

      const attemptStreaming = async () => {
        try {
          const response = await fetch(`${resolveApiBase()}/api/v1/rag/query/stream`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Accept: 'application/x-ndjson, text/event-stream'
            },
            body: JSON.stringify({
              question,
              filing_id: referenceId,
              top_k: 5,
              run_self_check: true
            })
          });

          if (!response.ok) {
            const detail = await response.text();
            throw new Error(detail || `Stream API returned ${response.status}`);
          }

          const contentType = response.headers.get('content-type') ?? '';
          if (!response.body) {
            if (contentType.includes('application/json')) {
              const payload = (await response.json()) as RagApiResponse;
              finalizeResponse(payload);
              return true;
            }
            return false;
          }

          let metaUpdated = false;
          const ensureStreamingMeta = () => {
            if (!metaUpdated) {
              metaUpdated = true;
              updateMessage(sessionId, assistantMessageId, {
                meta: { status: 'streaming', retryable: false }
              });
            }
          };

          const applyToken = (answer: string) => {
            ensureStreamingMeta();
            updateMessage(sessionId, assistantMessageId, {
              content: answer || ASSISTANT_LOADING_RESPONSE
            });
          };

          if (contentType.includes('application/x-ndjson')) {
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let streamedAnswer = '';
            let finalPayload: RagStreamFinalPayload | null = null;

            while (true) {
              const { value, done } = await reader.read();
              if (value) {
                buffer += decoder.decode(value, { stream: !done });
              }

              let newlineIndex = buffer.indexOf('\n');
              while (newlineIndex !== -1) {
                const rawLine = buffer.slice(0, newlineIndex).trim();
                buffer = buffer.slice(newlineIndex + 1);
                if (rawLine) {
                  try {
                    const event = JSON.parse(rawLine) as RagStreamEvent;
                    if (event.type === 'token') {
                      const token = event.text ?? '';
                      if (token) {
                        streamedAnswer += token;
                        applyToken(streamedAnswer);
                      }
                    } else if (event.type === 'final') {
                      finalPayload = (event.payload ?? {}) as RagStreamFinalPayload;
                    } else if (event.type === 'error') {
                      throw new Error(event.message ?? 'Streaming error');
                    }
                  } catch (parseError) {
                    console.warn('Failed to parse stream chunk', rawLine, parseError);
                  }
                }
                newlineIndex = buffer.indexOf('\n');
              }

              if (done) {
                break;
              }
            }

            if (!finalPayload && buffer.trim()) {
              try {
                const event = JSON.parse(buffer.trim()) as RagStreamEvent;
                if (event.type === 'final') {
                  finalPayload = (event.payload ?? {}) as RagStreamFinalPayload;
                } else if (event.type === 'error') {
                  throw new Error(event.message ?? 'Streaming error');
                }
              } catch (parseError) {
                console.warn('Failed to parse trailing stream chunk', buffer, parseError);
              }
            }

            try {
              await reader.cancel();
            } catch {
              // ignore cancellation errors
            }

            if (!finalPayload) {
              throw new Error('Streaming ended without final payload');
            }

            finalizeResponse(finalPayload);
            return true;
          }

          if (contentType.includes('text/event-stream')) {
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let streamedAnswer = '';
            let finalPayload: RagStreamFinalPayload | null = null;

            while (true) {
              const { value, done } = await reader.read();
              if (value) {
                buffer += decoder.decode(value, { stream: !done });
              }
              const events = buffer.split('\n\n');
              buffer = events.pop() ?? '';

              for (const rawEvent of events) {
                const trimmed = rawEvent.trim();
                if (!trimmed.startsWith('data:')) {
                  continue;
                }
                const payloadText = trimmed.slice(5).trim();
                if (!payloadText) {
                  continue;
                }
                const parsed = JSON.parse(payloadText) as RagStreamEvent;
                if (parsed.type === 'token') {
                  const token = parsed.text ?? '';
                  if (token) {
                    streamedAnswer += token;
                    applyToken(streamedAnswer);
                  }
                } else if (parsed.type === 'final') {
                  finalPayload = (parsed.payload ?? {}) as RagStreamFinalPayload;
                } else if (parsed.type === 'error') {
                  throw new Error(parsed.message ?? 'Streaming error');
                }
              }

              if (done) {
                break;
              }
            }

            if (!finalPayload && buffer.trim()) {
              try {
                const event = JSON.parse(buffer.trim()) as RagStreamEvent;
                if (event.type === 'final') {
                  finalPayload = (event.payload ?? {}) as RagStreamFinalPayload;
                } else if (event.type === 'error') {
                  throw new Error(event.message ?? 'Streaming error');
                }
              } catch (parseError) {
                console.warn('Failed to parse trailing stream chunk', buffer, parseError);
              }
            }

            try {
              await reader.cancel();
            } catch {
              // ignore cancellation errors
            }

            if (!finalPayload) {
              throw new Error('Streaming ended without final payload');
            }

            finalizeResponse(finalPayload);
            return true;
          }

          if (contentType.includes('application/json')) {
            const payload = (await response.json()) as RagApiResponse;
            finalizeResponse(payload);
            return true;
          }

          return false;
        } catch (streamError) {
          console.warn('Streaming query failed', streamError);
          return false;
        }
      };

      try {
        const streamingHandled = await attemptStreaming();
        if (!streamingHandled) {
          await fetchStandard();
        }
      } catch (error) {
        console.error('RAG query failed', error);
        const fallbackMessage =
          error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다.';
        updateMessage(sessionId, assistantMessageId, {
          content: ASSISTANT_ERROR_RESPONSE,
          meta: {
            status: 'error',
            errorMessage: fallbackMessage,
            retryable: true,
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
          guardrail: {
            status: 'error',
            errorMessage: fallbackMessage
          },
          metrics: idleMetricsTelemetry
        });
        showToast({
          intent: 'error',
          title: isRetry ? '재시도 중 오류가 발생했습니다' : '답변 생성에 실패했습니다',
          message: fallbackMessage
        });
      }
    },
    [focusEvidence, setSessionEvidence, setSessionTelemetry, showToast, updateMessage]
  );

  const handleSend = useCallback(
    async (rawInput: string) => {
      const trimmed = rawInput.trim();
      if (!trimmed) return;

      let targetSessionId = activeSessionId;
      if (!targetSessionId) {
        targetSessionId = createSession();
        navigateToSession(targetSessionId);
      }

      const timestamp = formatTimestamp();
      const userMessageId = nanoid();
      addMessage(targetSessionId, {
        id: userMessageId,
        role: 'user',
        content: trimmed,
        timestamp,
        meta: { status: 'ready' }
      });

      const sessionAfterUserMessage = useChatStore
        .getState()
        .sessions.find((session) => session.id === targetSessionId);
      if (sessionAfterUserMessage) {
        const userMessageCount = sessionAfterUserMessage.messages.filter((message) => message.role === 'user')
          .length;
        if (userMessageCount === 1) {
          renameSession(targetSessionId, deriveSessionTitleFromQuestion(trimmed));
        }
      }

      const assistantMessageId = nanoid();
      addMessage(targetSessionId, {
        id: assistantMessageId,
        role: 'assistant',
        content: ASSISTANT_LOADING_RESPONSE,
        timestamp,
        meta: {
          status: 'pending',
          retryable: false,
          question: trimmed,
          userMessageId
        }
      });

      await runQuery({
        question: trimmed,
        sessionId: targetSessionId,
        assistantMessageId,
        userMessageId
      });
    },
    [activeSessionId, addMessage, createSession, navigateToSession, renameSession, runQuery]
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

      if (!question || !userMessageId) {
        showToast({
          intent: 'warning',
          title: '재시도 정보를 찾지 못했습니다',
          message: '같은 질문을 새로 입력해 주세요.'
        });
        return;
      }

      const timestamp = formatTimestamp();
      updateMessage(sessionId, messageId, {
        content: ASSISTANT_LOADING_RESPONSE,
        timestamp,
        meta: {
          status: 'pending',
          retryable: false,
          errorMessage: undefined
        }
      });

      await runQuery({
        question,
        sessionId,
        assistantMessageId: messageId,
        userMessageId,
        isRetry: true
      });
    },
    [activeSessionId, runQuery, showToast, updateMessage]
  );

  const messages = activeSession?.messages ?? [];
  const sessionTitle = activeSession?.title ?? '새 세션';
  const showEmptyState = messages.length === 0;
  const hasContextBanner = useMemo(() => Boolean(contextSummary), [contextSummary]);

  return (
    <AppShell>
      <div className='flex flex-col gap-6 lg:flex-row'>
        <ChatHistoryList
          sessions={sessions}
          selectedId={activeSessionId ?? undefined}
          onSelect={handleSelectSession}
          onNewSession={handleCreateSession}
          onDeleteSession={handleDeleteSession}
          onClearAll={handleClearSessions}
          persistenceError={persistenceError ?? undefined}
          disabled={!isHydrated}
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
          <div className='flex-1 space-y-4 overflow-y-auto pr-2'>
            {showEmptyState ? (
              <EmptyState
                title='메시지가 없습니다'
                description="새 세션을 시작하거나 공시 상세에서 '질문하기' 버튼을 눌러 대화를 생성해보세요."
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
          <ChatInput onSubmit={handleSend} disabled={!isHydrated} />
        </div>
        <ChatContextPanel />
      </div>
    </AppShell>
  );
}
