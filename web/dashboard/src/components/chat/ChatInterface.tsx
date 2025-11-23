'use client';

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FileText, Loader2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { nanoid } from "nanoid";

import { ChatPageShell } from "@/components/chat/ChatPageShell";
import { GuestUpsellModal } from "@/components/chat/GuestUpsellModal";
import OnboardingGuide from "@/components/onboarding/OnboardingGuide";
import { useGenerateReport } from "@/hooks/useGenerateReport";
import { useChatController } from "@/hooks/useChatController";
import { useGuestPass } from "@/hooks/useGuestPass";
import { extractEventStudyKeyStats } from "@/lib/reportExport";
import { useReportStore } from "@/stores/useReportStore";
import { useAuth } from "@/lib/authContext";
import { useChatStore, type ChatMessage } from "@/store/chatStore";
import { createMessage } from "@/lib/chatApi";

export function ChatInterface() {
  return (
    <Suspense
      fallback={
        <div className="flex h-full items-center justify-center gap-2 text-slate-300">
          <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
          <span>Loading chat...</span>
        </div>
      }
    >
      <ChatInterfaceContent />
    </Suspense>
  );
}

function ChatInterfaceContent() {
  const { session, loading: authLoading } = useAuth();
  const searchParams = useSearchParams();
  const controller = useChatController();
  const isAuthenticated = Boolean(session);
  const guestPass = useGuestPass(isAuthenticated);
  const generateReport = useGenerateReport();
  const messages = controller.stream.messages;
  const setKeyStats = useReportStore((state) => state.setKeyStats);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [guestModalOpen, setGuestModalOpen] = useState(false);
  const [tickerInput, setTickerInput] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const lastStatsRef = useRef<string | null>(null);
  const prefillHandledRef = useRef(false);
  const isAuthReady = !authLoading;
  const miniImportHandledRef = useRef(false);

  useEffect(() => {
    const stats = extractEventStudyKeyStats(messages);
    if (!stats) {
      return;
    }
    const serialized = JSON.stringify(stats);
    if (serialized === lastStatsRef.current) {
      return;
    }
    lastStatsRef.current = serialized;
    setKeyStats(stats);
  }, [messages, setKeyStats]);

  const normalizedTicker = useMemo(() => tickerInput.trim().toUpperCase(), [tickerInput]);

  const handleDialogClose = useCallback(() => {
    setDialogOpen(false);
    setInputError(null);
  }, []);

  const handleSubmit = useCallback(
    (event?: React.FormEvent<HTMLFormElement>) => {
      event?.preventDefault();
      const normalized = normalizedTicker;
      if (!normalized) {
        setInputError("Enter a ticker symbol");
        return;
      }
      generateReport.mutate({ ticker: normalized });
      setDialogOpen(false);
      setTickerInput("");
      setInputError(null);
    },
    [generateReport, normalizedTicker]
  );

  useEffect(() => {
    if (!guestPass.isGuest) {
      setGuestModalOpen(false);
    }
  }, [guestPass.isGuest]);

  const handleGuestSend = useCallback(
    async (rawInput: string) => {
      const trimmed = rawInput.trim();
      if (!trimmed) {
        return;
      }
      if (!guestPass.isGuest) {
        await controller.stream.onSend(trimmed);
        return;
      }
      if (!guestPass.ready) {
        return;
      }
      if (guestPass.remaining <= 0) {
        setGuestModalOpen(true);
        return;
      }
      const allowed = guestPass.consume();
      if (!allowed) {
        setGuestModalOpen(true);
        return;
      }
      await controller.stream.onSend(trimmed);
    },
    [controller.stream, guestPass]
  );

  const guestAwareController = useMemo(
    () => ({
      ...controller,
      stream: {
        ...controller.stream,
        onSend: handleGuestSend,
      },
    }),
    [controller, handleGuestSend]
  );

  useEffect(() => {
    if (prefillHandledRef.current) {
      return;
    }
    const prefillValue = searchParams?.get("prefill");
    if (!prefillValue || !guestPass.ready || !isAuthReady) {
      return;
    }
    const trimmed = prefillValue.trim();
    if (!trimmed) {
      return;
    }
    // Fill the chat input and auto-send once.
    window.dispatchEvent(new CustomEvent("onboarding:prefill", { detail: { value: trimmed } }));
    prefillHandledRef.current = true;
    void handleGuestSend(trimmed);
  }, [guestPass.ready, handleGuestSend, isAuthReady, searchParams]);

  useEffect(() => {
    if (miniImportHandledRef.current) {
      return;
    }
    if (!guestPass.ready || !isAuthReady) {
      return;
    }
    const flag = searchParams?.get("importMini");
    const stored = sessionStorage.getItem("miniChatImport");
    if (!flag || !stored) {
      return;
    }
    miniImportHandledRef.current = true;
    sessionStorage.removeItem("miniChatImport");
    const run = async () => {
      try {
        const payload = JSON.parse(stored) as {
          prompt?: string;
          context?: string | null;
          turns?: Array<{ role: "user" | "assistant"; content: string }>;
          contextIds?: Record<string, string | null | undefined>;
        };
        const activeSessionId = controller.history.selectedId;
        if (!activeSessionId) {
          return;
        }
        const addMessage = useChatStore.getState().addMessage;
        const turns =
          payload.turns?.length && payload.turns.length > 0
            ? payload.turns
            : payload.prompt
              ? [{ role: "user", content: payload.prompt }]
              : [];
        if (!turns.length) return;

        const contextText = payload.context?.trim() || "";
        const contextIds = payload.contextIds ?? null;
        let lastMessageId: string | null = null;
        const turnId = nanoid();
        for (const turn of turns) {
          const contentWithContext = contextText
            ? `${turn.content}\n\n[컨텍스트]\n${contextText}`
            : turn.content;
          let savedId = nanoid();
          let savedTimestamp = new Date().toISOString();
          try {
            const saved = await createMessage({
              session_id: activeSessionId,
              role: turn.role,
              content: contentWithContext,
              turn_id: turnId,
              reply_to_message_id: lastMessageId ?? undefined,
              state: "ready",
              meta: { imported: true, context: contextText || undefined, contextIds: contextIds ?? undefined },
              context_ids: contextIds,
            });
            savedId = saved.id ?? savedId;
            savedTimestamp = (saved as any)?.created_at ?? savedTimestamp;
          } catch (error) {
            console.warn("Mini chat import save failed (using local only):", error);
          }

          const message: ChatMessage = {
            id: savedId,
            role: turn.role,
            content: contentWithContext,
            meta: { status: "ready", imported: true, context: contextText || undefined, contextIds: contextIds ?? undefined },
            timestamp: savedTimestamp,
          };
          addMessage(activeSessionId, message);
          lastMessageId = savedId;
        }
      } catch (error) {
        console.warn("Mini chat import parse failed:", error);
      }
    };
    void run();
  }, [controller.history.selectedId, guestPass.ready, isAuthReady, searchParams]);

  const hasUserMessage = useMemo(() => messages.some((msg) => msg.role === "user"), [messages]);
  const hasAssistantAnswer = useMemo(
    () =>
      messages.some((msg) => {
        if (msg.role !== "assistant" || msg.meta?.status !== "ready") {
          return false;
        }
        const hasQuestion =
          (typeof msg.meta?.question === "string" && msg.meta.question.trim().length > 0) ||
          (typeof msg.meta?.userMessageId === "string" && msg.meta.userMessageId.trim().length > 0);
        return hasQuestion;
      }),
    [messages],
  );
  const reportDisabled = !hasUserMessage || !hasAssistantAnswer || generateReport.isPending;

  const handleReportClick = useCallback(() => {
    if (reportDisabled) return;
    setDialogOpen(true);
  }, [reportDisabled]);

  return (
    <div className="relative h-full">
      <ChatPageShell
        controller={guestAwareController}
        reportAction={{
          onOpen: handleReportClick,
          disabled: reportDisabled,
          loading: generateReport.isPending,
        }}
        guestBadge={
          guestPass.isGuest ? (
            <div className="rounded-full border border-white/15 bg-white/10 px-4 py-2 text-xs font-semibold text-white shadow-lg backdrop-blur">
              게스트 체험{" "}
              {guestPass.remaining > 0 ? `남은 질문 ${Math.max(guestPass.remaining, 0)}회` : "소진 · 가입 후 계속"}
            </div>
          ) : null
        }
      />
      <OnboardingGuide />
      <GuestUpsellModal open={guestModalOpen && guestPass.isGuest} onClose={() => setGuestModalOpen(false)} />

      {dialogOpen && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4">
          <form
            className="w-full max-w-md rounded-3xl border border-border-dark bg-surface p-6 text-slate-100 shadow-2xl"
            onSubmit={handleSubmit}
          >
            <div className="flex items-center gap-3 text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">
              <FileText className="h-4 w-4 text-primary" />
              New Report
            </div>
            <h2 className="mt-3 text-2xl font-semibold text-white">Which ticker do you want to analyze?</h2>
            <p className="mt-2 text-sm text-slate-400">
              Examples: <span className="font-semibold text-slate-200">AAPL</span>,{" "}
              <span className="font-semibold text-slate-200">005930</span>,{" "}
              <span className="font-semibold text-slate-200">TSLA</span>
            </p>
            <div className="mt-6 space-y-2">
              <label htmlFor="report-ticker" className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Ticker
              </label>
              <input
                id="report-ticker"
                name="ticker"
                autoFocus
                value={tickerInput}
                onChange={(event) => setTickerInput(event.target.value)}
                className="w-full rounded-2xl border border-border-dark bg-background-dark px-4 py-3 text-base font-semibold uppercase tracking-wide text-white placeholder:text-slate-500 focus:border-primary focus:outline-none"
                placeholder="e.g. AAPL"
              />
              {inputError && <p className="text-xs text-rose-400">{inputError}</p>}
            </div>
            <div className="mt-6 flex items-center justify-end gap-3">
              <button
                type="button"
                className="rounded-full px-4 py-2 text-sm font-semibold text-slate-400 hover:text-slate-200"
                onClick={handleDialogClose}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-primary/40 disabled:cursor-not-allowed disabled:bg-primary/40"
                disabled={generateReport.isPending}
              >
                {generateReport.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Create report
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

export default ChatInterface;
