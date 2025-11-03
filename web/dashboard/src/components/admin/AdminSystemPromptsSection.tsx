"use client";

import clsx from "classnames";
import { useEffect, useState } from "react";

import { useSystemPrompts, useUpdateSystemPrompt } from "@/hooks/useAdminConfig";
import type { AdminSystemPromptList, PromptChannel } from "@/lib/adminApi";
import type { ToastInput } from "@/store/toastStore";

type AdminSystemPromptsSectionProps = {
  adminActor?: string | null;
  actorPlaceholder?: string;
  toast: (toast: ToastInput) => string;
};

type PromptDraft = {
  prompt: string;
  note: string;
};

const CHANNEL_LABEL: Record<PromptChannel, string> = {
  chat: "상담·대화 기본 프롬프트",
  rag: "RAG 요약 프롬프트",
  self_check: "Self-check 안전망 프롬프트",
};

const DEFAULT_PROMPT_STATE = (actor: string): Record<PromptChannel, PromptDraft> => ({
  chat: { prompt: "", note: actor ? `${actor} 수정` : "chat prompt 업데이트" },
  rag: { prompt: "", note: actor ? `${actor} 수정` : "rag prompt 업데이트" },
  self_check: { prompt: "", note: actor ? `${actor} 수정` : "self-check prompt 업데이트" },
});

function normalizePromptDrafts(data: AdminSystemPromptList | undefined, actor: string) {
  const base = DEFAULT_PROMPT_STATE(actor);
  if (!data?.items?.length) {
    return base;
  }
  const next: Record<PromptChannel, PromptDraft> = { ...base };
  for (const item of data.items) {
    next[item.channel] = {
      prompt: item.prompt ?? "",
      note: item.updatedBy ? `최근 업데이트: ${item.updatedBy}` : base[item.channel].note,
    };
  }
  return next;
}

export function AdminSystemPromptsSection({ adminActor, actorPlaceholder = "", toast }: AdminSystemPromptsSectionProps) {
  const {
    data: promptList,
    isLoading: isPromptLoading,
    isError: isPromptError,
    refetch: refetchPrompts,
  } = useSystemPrompts(undefined, true);
  const updatePrompt = useUpdateSystemPrompt();

  const [promptDrafts, setPromptDrafts] = useState<Record<PromptChannel, PromptDraft>>(() =>
    DEFAULT_PROMPT_STATE(actorPlaceholder),
  );
  const [savingChannel, setSavingChannel] = useState<PromptChannel | null>(null);

  useEffect(() => {
    setPromptDrafts(normalizePromptDrafts(promptList, actorPlaceholder));
  }, [promptList, actorPlaceholder]);

  const handlePromptChange = (channel: PromptChannel, value: string) => {
    setPromptDrafts((prev) => ({ ...prev, [channel]: { ...prev[channel], prompt: value } }));
  };

  const handleNoteChange = (channel: PromptChannel, value: string) => {
    setPromptDrafts((prev) => ({ ...prev, [channel]: { ...prev[channel], note: value } }));
  };

  const handlePromptSave = async (channel: PromptChannel) => {
    if (updatePrompt.isPending) {
      return;
    }
    setSavingChannel(channel);
    try {
      await updatePrompt.mutateAsync({
        channel,
        prompt: promptDrafts[channel].prompt,
        actor: adminActor ?? "unknown-admin",
        note: promptDrafts[channel].note.trim() || null,
      });
      toast({
        id: `admin/llm/prompt/${channel}-${Date.now()}`,
        title: "프롬프트가 저장됐어요",
        message: `${CHANNEL_LABEL[channel]}이 최신 상태예요.`,
        intent: "success",
      });
      await refetchPrompts();
    } catch (error) {
      const message = error instanceof Error ? error.message : "프롬프트 저장에 실패했어요.";
      toast({
        id: `admin/llm/prompt/${channel}/error-${Date.now()}`,
        title: "프롬프트 저장 실패",
        message,
        intent: "error",
      });
    } finally {
      setSavingChannel((prev) => (prev === channel ? null : prev));
    }
  };

  return (
    <section className="space-y-4 rounded-xl border border-border-light bg-background-base p-4 dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
          시스템 프롬프트
        </h3>
        <button
          type="button"
          onClick={() => refetchPrompts()}
          className="inline-flex items-center rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
          disabled={isPromptLoading}
        >
          최신 상태 불러오기
        </button>
      </div>

      {isPromptError ? (
        <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-700 dark:border-amber-500/70 dark:bg-amber-500/10 dark:text-amber-200">
          프롬프트를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.
        </p>
      ) : null}

      <div className="space-y-4">
        {(Object.keys(CHANNEL_LABEL) as PromptChannel[]).map((channel) => {
          const draft = promptDrafts[channel];
          const isSaving = savingChannel === channel && updatePrompt.isPending;
          return (
            <div
              key={channel}
              className="space-y-3 rounded-xl border border-border-light bg-background-cardLight p-4 text-sm text-text-primaryLight dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
            >
              <header className="flex items-center justify-between gap-3">
                <div>
                  <h4 className="font-semibold">{CHANNEL_LABEL[channel]}</h4>
                  <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
                    운영자가 정의한 친근한 톤과 가드레일 안내를 반영해 주세요.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => handlePromptSave(channel)}
                  disabled={isSaving}
                  className={clsx(
                    "inline-flex items-center rounded-lg bg-primary px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
                    isSaving && "cursor-not-allowed opacity-60",
                  )}
                >
                  {isSaving ? "저장 중…" : "저장"}
                </button>
              </header>

              <textarea
                value={draft?.prompt ?? ""}
                onChange={(event) => handlePromptChange(channel, event.target.value)}
                className="min-h-[160px] w-full rounded-lg border border-border-light bg-background-base px-3 py-2 font-mono text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                placeholder="시스템 프롬프트 내용을 입력해 주세요."
              />

              <label className="flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                변경 메모 (선택)
                <input
                  type="text"
                  value={draft?.note ?? ""}
                  onChange={(event) => handleNoteChange(channel, event.target.value)}
                  placeholder="예: chat 프롬프트에 compliance 문구 추가"
                  className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                />
              </label>
            </div>
          );
        })}
      </div>
    </section>
  );
}
