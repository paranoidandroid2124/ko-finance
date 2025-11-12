"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { InlinePdfViewer } from "@/components/evidence/InlinePdfViewer";
import { fetchRagDeeplink, type RagDeeplinkPayload } from "@/lib/chatApi";
import { useToastStore } from "@/store/toastStore";
import { logEvent } from "@/lib/telemetry";

type ViewerState =
  | { status: "loading" }
  | { status: "ready"; payload: RagDeeplinkPayload }
  | { status: "error"; message: string };

type ViewerPageProps = {
  params: { token: string };
};

export default function ViewerPage({ params }: ViewerPageProps) {
  const { token } = params;
  const [state, setState] = useState<ViewerState>({ status: "loading" });
  const router = useRouter();
  const showToast = useToastStore((store) => store.show);

  const loadDeeplink = useCallback(async () => {
    setState({ status: "loading" });
    try {
      const payload = await fetchRagDeeplink(token);
      setState({ status: "ready", payload });
      logEvent("rag.deeplink_viewer_ready", {
        token,
        pageNumber: payload.page_number,
        documentId: payload.document_id,
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "링크 정보를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.";
      setState({ status: "error", message });
      logEvent("rag.deeplink_viewer_error", { token, message });
    }
  }, [token]);

  useEffect(() => {
    loadDeeplink();
  }, [loadDeeplink]);

  const handleBackToChat = useCallback(() => {
    router.push("/chat");
  }, [router]);

  const handleOpenOriginal = useCallback(() => {
    if (state.status !== "ready") {
      return;
    }
    const target = state.payload.document_url;
    const opened = window.open(target, "_blank", "noopener,noreferrer");
    if (!opened) {
      showToast({
        intent: "warning",
        title: "팝업이 차단되었어요",
        message: "브라우저에서 새 창을 차단했습니다. 링크를 길게 눌러 새 탭에서 열어보세요.",
      });
      logEvent("rag.deeplink_viewer_original_failed", {
        token,
        documentId: state.payload.document_id,
        reason: "popup_blocked",
      });
      return;
    }
    logEvent("rag.deeplink_viewer_original_opened", {
      token,
      documentId: state.payload.document_id,
    });
  }, [showToast, state, token]);

  const metadata = useMemo(() => {
    if (state.status !== "ready") {
      return null;
    }
    return [
      { label: "페이지", value: `${state.payload.page_number}쪽` },
      state.payload.document_id ? { label: "Document ID", value: state.payload.document_id } : null,
      state.payload.chunk_id ? { label: "Chunk ID", value: state.payload.chunk_id } : null,
      state.payload.sentence_hash ? { label: "문장 해시", value: state.payload.sentence_hash } : null,
      state.payload.char_start !== undefined && state.payload.char_end !== undefined
        ? {
            label: "문자 오프셋",
            value: `${state.payload.char_start} ~ ${state.payload.char_end}`,
          }
        : null,
      { label: "만료 시각", value: new Date(state.payload.expires_at).toLocaleString() },
    ].filter(Boolean) as Array<{ label: string; value: string }>;
  }, [state]);

  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50 text-slate-900 dark:from-slate-900 dark:via-slate-950 dark:to-slate-900 dark:text-slate-100">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-primary/70">RAG Evidence Viewer</p>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">출처 세부정보</h1>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleBackToChat}
              className="rounded-md border border-border-light/80 px-4 py-2 text-sm font-semibold text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
            >
              채팅으로 돌아가기
            </button>
            {state.status === "ready" ? (
              <button
                type="button"
                onClick={handleOpenOriginal}
                className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
              >
                원문 문서 열기
              </button>
            ) : null}
          </div>
        </div>

        {state.status === "loading" ? (
          <div className="rounded-xl border border-border-light/80 bg-white/60 p-6 text-sm text-text-secondaryLight shadow-sm dark:border-border-dark/70 dark:bg-slate-900/70 dark:text-text-secondaryDark">
            링크 정보를 불러오는 중입니다…
          </div>
        ) : null}

        {state.status === "error" ? (
          <div className="rounded-xl border border-destructive/50 bg-destructive/10 p-6 text-sm text-destructive shadow-sm">
            <p className="font-semibold">링크 정보를 불러오지 못했습니다.</p>
            <p className="mt-2 text-xs opacity-80">{state.message}</p>
            <div className="mt-4 flex flex-wrap gap-2 text-xs">
              <button
                type="button"
                onClick={loadDeeplink}
                className="rounded-md border border-destructive/60 px-3 py-1 font-semibold text-destructive transition-colors hover:border-destructive hover:bg-destructive/10"
              >
                다시 시도하기
              </button>
              <button
                type="button"
                onClick={handleBackToChat}
                className="rounded-md border border-border-light px-3 py-1 font-semibold text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark"
              >
                채팅 목록으로 이동
              </button>
            </div>
          </div>
        ) : null}

        {state.status === "ready" ? (
          <>
            <div className="rounded-xl border border-border-light/80 bg-white/80 p-6 shadow-sm dark:border-border-dark/70 dark:bg-slate-900/70">
              <dl className="grid gap-4 sm:grid-cols-2">
                {metadata?.map((item) => (
                  <div key={item.label}>
                    <dt className="text-xs uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
                      {item.label}
                    </dt>
                    <dd className="mt-1 text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                      {item.value}
                    </dd>
                  </div>
                ))}
                {state.payload.excerpt ? (
                  <div className="sm:col-span-2">
                    <dt className="text-xs uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
                      인용된 문장
                    </dt>
                    <dd className="mt-2 rounded-lg bg-slate-100 p-3 text-sm text-text-secondaryLight dark:bg-slate-800 dark:text-text-secondaryDark">
                      “{state.payload.excerpt}”
                    </dd>
                  </div>
                ) : null}
              </dl>
            </div>
            <div className="rounded-xl border border-border-light/80 bg-white/80 p-4 shadow-sm dark:border-border-dark/70 dark:bg-slate-900/70">
              <InlinePdfViewer
                key={`${state.payload.document_url}-${state.payload.page_number}`}
                src={state.payload.document_url}
                page={state.payload.page_number}
                className="h-[70vh]"
              />
            </div>
          </>
        ) : null}
      </div>
    </main>
  );
}
