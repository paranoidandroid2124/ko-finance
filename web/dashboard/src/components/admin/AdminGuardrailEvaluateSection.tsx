"use client";

import clsx from "classnames";
import { useMemo, useState } from "react";

import { useEvaluateGuardrail, useGuardrailSamples, useUpdateGuardrailBookmark } from "@/hooks/useAdminConfig";
import { resolveApiBase } from "@/lib/apiBase";
import type { AdminGuardrailDiffLine, AdminGuardrailSample, PromptChannel } from "@/lib/adminApi";
import type { ToastInput } from "@/store/toastStore";

type AdminGuardrailEvaluateSectionProps = {
  adminActor?: string | null;
  toast: (toast: ToastInput) => string;
};

const CHANNEL_OPTIONS: Array<{ value: PromptChannel; label: string }> = [
  { value: "chat", label: "상담·대화" },
  { value: "rag", label: "RAG 요약" },
  { value: "self_check", label: "Self-check" },
];

type EvaluationState = {
  sample: string;
  selected: Record<PromptChannel, boolean>;
  error?: string | null;
};

const buildInitialState = (): EvaluationState => ({
  sample: "",
  selected: {
    chat: true,
    rag: false,
    self_check: false,
  },
});

export function AdminGuardrailEvaluateSection({ adminActor, toast }: AdminGuardrailEvaluateSectionProps) {
  const evaluateGuardrail = useEvaluateGuardrail();
  const [state, setState] = useState<EvaluationState>(() => buildInitialState());
  const [evaluatedAt, setEvaluatedAt] = useState<string | null>(null);
  const [resultText, setResultText] = useState<string | null>(null);
  const [detailsJson, setDetailsJson] = useState<string | null>(null);
  const [auditFileName, setAuditFileName] = useState<string | null>(null);
  const [lineDiff, setLineDiff] = useState<AdminGuardrailDiffLine[]>([]);
  const [sampleId, setSampleId] = useState<string | null>(null);
  const { data: sampleList, isLoading: samplesLoading } = useGuardrailSamples();
  const bookmarkMutation = useUpdateGuardrailBookmark();

  const selectedChannels = useMemo(
    () =>
      (Object.keys(state.selected) as PromptChannel[]).filter((channel) => state.selected[channel]),
    [state.selected],
  );
  const auditDownloadUrl = useMemo(() => `${resolveApiBase()}/api/v1/admin/llm/audit/logs`, []);

  const toggleChannel = (channel: PromptChannel) => {
    setState((prev) => ({
      ...prev,
      selected: {
        ...prev.selected,
        [channel]: !prev.selected[channel],
      },
      error: undefined,
    }));
  };

  const handleSampleChange = (value: string) => {
    setState((prev) => ({ ...prev, sample: value, error: undefined }));
  };

  const resetEvaluation = () => {
    setState(buildInitialState());
    setEvaluatedAt(null);
    setResultText(null);
    setDetailsJson(null);
    setAuditFileName(null);
    setLineDiff([]);
    setSampleId(null);
  };

  const handleEvaluate = async () => {
    if (!state.sample.trim()) {
      setState((prev) => ({ ...prev, error: "평가할 샘플 문장을 입력해 주세요." }));
      return;
    }

    const channels = selectedChannels;
    if (channels.length === 0) {
      setState((prev) => ({ ...prev, error: "최소 한 개 이상의 채널을 선택해 주세요." }));
      return;
    }

    try {
      const response = await evaluateGuardrail.mutateAsync({
        sample: state.sample.trim(),
        channels,
      });
      setResultText(response.result);
      setDetailsJson(JSON.stringify(response.details ?? {}, null, 2));
      setEvaluatedAt(response.loggedAt ?? null);
      setAuditFileName(response.auditFile ?? null);
      setLineDiff(response.lineDiff ?? []);
      setSampleId(response.sampleId ?? null);
      toast({
        id: `admin/guardrail/evaluate/${Date.now()}`,
        title: "샘플 평가를 완료했어요",
        message:
          channels.length > 1
            ? "선택한 채널의 반응을 모두 확인해 보세요. 감사 로그도 자동으로 기록됐어요."
            : "가드레일 반응을 확인해 보세요. 감사 로그도 자동으로 기록됐어요.",
        intent: "success",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "샘플 평가에 실패했어요.";
      toast({
        id: `admin/guardrail/evaluate/error-${Date.now()}`,
        title: "평가 실행에 실패했어요",
        message,
        intent: "error",
      });
    }
  };

  const handleFillExample = () => {
    const exampleActor = adminActor || "운영자";
    setState((prev) => ({
      ...prev,
      sample: `${exampleActor}님, 투자 조언이 필요한데 어떻게 해야 할까요?`,
      selected: { chat: true, rag: true, self_check: true },
      error: undefined,
    }));
  };


  const handleBookmarkToggle = (sample: AdminGuardrailSample, nextValue: boolean) => {
    bookmarkMutation.mutate({ sampleId: sample.sampleId, payload: { bookmarked: nextValue } });
  };

  const evaluatedChannelsLabel =
    selectedChannels.length > 0
      ? selectedChannels
          .map((channel) => CHANNEL_OPTIONS.find((item) => item.value === channel)?.label ?? channel)
          .join(", ")
      : "선택 없음";

  return (
    <section className="space-y-4 rounded-xl border border-border-light bg-background-base p-4 dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
            가드레일 샘플 평가
          </h3>
          <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
            정책 적용 결과를 빠르게 확인해 운영자 경험을 개선해 주세요.
          </p>
        </div>
        <button
          type="button"
          onClick={resetEvaluation}
          className="inline-flex items-center rounded-lg border border-border-light px-3 py-2 text-xs font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
        >
          입력 초기화
        </button>
      </div>

      <label className="flex flex-col gap-2 text-sm">
        <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">샘플 문장</span>
        <textarea
          value={state.sample}
          onChange={(event) => handleSampleChange(event.target.value)}
          className="min-h-[140px] rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          placeholder="안내가 필요한 문장을 입력해 주세요."
        />
      </label>

      <div className="space-y-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
          평가 채널
        </span>
        <div className="flex flex-wrap gap-2">
          {CHANNEL_OPTIONS.map((channel) => {
            const isActive = state.selected[channel.value];
            return (
              <button
                key={channel.value}
                type="button"
                onClick={() => toggleChannel(channel.value)}
                className={clsx(
                  "inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold transition",
                  isActive
                    ? "border-primary bg-primary/10 text-primary dark:border-primary.dark dark:bg-primary.dark/20 dark:text-primary.dark"
                    : "border-border-light text-text-secondaryLight hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark",
                )}
              >
                {channel.label}
              </button>
            );
          })}
        </div>
      </div>

      {state.error ? (
        <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-700 dark:border-amber-500/70 dark:bg-amber-500/10 dark:text-amber-200">
          {state.error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center justify-end gap-3">
        <button
          type="button"
          onClick={handleFillExample}
          className="inline-flex items-center rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
        >
          예시 채우기
        </button>
        <button
          type="button"
          onClick={handleEvaluate}
          disabled={evaluateGuardrail.isPending}
          className={clsx(
            "inline-flex items-center rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-white transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
            evaluateGuardrail.isPending && "cursor-not-allowed opacity-60",
          )}
        >
          {evaluateGuardrail.isPending ? "평가 중…" : "샘플 평가 실행"}
        </button>
      </div>

      {resultText ? (
        <div className="space-y-3 rounded-xl border border-border-light bg-background-cardLight p-4 text-sm text-text-primaryLight dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark">
          <header className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h4 className="font-semibold">평가 결과</h4>
              <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
                채널: {evaluatedChannelsLabel}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
              <span>평가 시각: {evaluatedAt ? new Date(evaluatedAt).toLocaleString("ko-KR") : "—"}</span>
              {sampleId ? (
                <span className="rounded bg-border-light px-2 py-0.5 font-mono text-[10px] text-text-tertiaryLight dark:bg-border-dark dark:text-text-tertiaryDark">
                  샘플 ID: {sampleId}
                </span>
              ) : null}
              <a
                href={auditDownloadUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center rounded border border-border-light px-2 py-0.5 text-[11px] font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
              >
                감사 로그 다운로드
              </a>
              {auditFileName ? (
                <span className="rounded bg-border-light px-2 py-0.5 font-mono text-[10px] text-text-tertiaryLight dark:bg-border-dark dark:text-text-tertiaryDark">
                  {auditFileName}
                </span>
              ) : null}
            </div>
          </header>

          <p className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm leading-relaxed dark:border-border-dark dark:bg-background-base/40">
            {resultText}
          </p>

          <div className="space-y-2 rounded-lg border border-dashed border-border-light bg-background-base/80 p-3 text-xs dark:border-border-dark dark:bg-background-base/30">
            <h5 className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">라인 diff 미리보기</h5>
            {lineDiff.length > 0 ? (
              <div className="space-y-1 font-mono">
                {lineDiff.map((line, index) => (
                  <p
                    key={`${line.kind}-${index}`}
                    className={clsx(
                      "whitespace-pre-wrap rounded px-2 py-1",
                      line.kind === "added"
                        ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-200"
                        : line.kind === "removed"
                        ? "bg-rose-100 text-rose-700 dark:bg-rose-400/20 dark:text-rose-200"
                        : "bg-border-light/40 text-text-secondaryLight dark:bg-border-dark/30 dark:text-text-secondaryDark",
                    )}
                  >
                    {line.kind === "added" ? "+ " : line.kind === "removed" ? "- " : "  "}
                    {line.text || "(빈 줄)"}
                  </p>
                ))}
              </div>
            ) : (
              <p className="rounded border border-border-light bg-background-base px-2 py-1 text-text-tertiaryLight dark:border-border-dark dark:bg-background-base/50 dark:text-text-tertiaryDark">
                입력과 정제된 문장이 크게 다르지 않아 따로 강조할 부분이 없었어요.
              </p>
            )}
          </div>

          <details className="rounded-lg border border-border-light bg-background-base dark:border-border-dark dark:bg-background-base/40">
            <summary className="cursor-pointer px-3 py-2 text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
              상세 로그 보기
            </summary>
            <pre className="overflow-x-auto px-3 py-2 text-xs leading-relaxed text-text-tertiaryLight dark:text-text-tertiaryDark">
              {detailsJson}
            </pre>
          </details>
        </div>
      ) : null}

      <div className="space-y-3 rounded-xl border border-border-light/60 bg-background-base p-4 text-sm dark:border-border-dark/60 dark:bg-background-cardDark">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h4 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">최근 평가 히스토리</h4>
            <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
              팀에서 확인한 문장을 다시 살펴보면서 안전 톤을 다듬을 수 있어요.
            </p>
          </div>
          {sampleId ? (
            <span className="rounded-full bg-primary/10 px-3 py-1 text-[11px] font-semibold text-primary dark:bg-primary.dark/20 dark:text-primary.dark">
              방금 저장됨
            </span>
          ) : null}
        </div>

        {samplesLoading ? (
          <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">샘플을 따뜻하게 불러오는 중이에요…</p>
        ) : (sampleList?.items.length ?? 0) === 0 ? (
          <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
            기록된 평가가 아직 없어요. 첫 번째 샘플을 남겨보시면 어떨까요?
          </p>
        ) : (
          <ul className="space-y-3">
            {sampleList?.items.map((sample) => (
              <li
                key={sample.sampleId}
                className="rounded-lg border border-border-light bg-background-cardLight/60 p-3 dark:border-border-dark dark:bg-background-cardDark/50"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1">
                    <p className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                      {sample.result.toUpperCase()} · {new Date(sample.evaluatedAt).toLocaleString("ko-KR")}
                    </p>
                    <p className="text-sm text-text-primaryLight dark:text-text-primaryDark line-clamp-2">{sample.sample}</p>
                    <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">채널: {sample.channels.join(", ")}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleBookmarkToggle(sample, !sample.bookmarked)}
                    className={clsx(
                      "inline-flex items-center rounded-full px-3 py-1 text-[11px] font-semibold transition",
                      sample.bookmarked
                        ? "bg-primary/10 text-primary dark:bg-primary.dark/20 dark:text-primary.dark"
                        : "bg-border-light text-text-secondaryLight hover:bg-border-light/60 dark:bg-border-dark dark:text-text-secondaryDark",
                    )}
                    disabled={bookmarkMutation.isPending}
                  >
                    {sample.bookmarked ? "북마크 취소" : "북마크"}
                  </button>
                </div>
                {sample.lineDiff.length > 0 ? (
                  <details className="mt-2 rounded border border-dashed border-border-light bg-background-base/70 dark:border-border-dark dark:bg-background-base/30">
                    <summary className="cursor-pointer px-3 py-2 text-xs font-semibold text-text-secondaryLight dark:text-text-secondaryDark">
                      라인 diff 열어보기
                    </summary>
                    <div className="space-y-1 px-3 py-2 font-mono text-[11px]">
                      {sample.lineDiff.map((line, index) => (
                        <p
                          key={`${sample.sampleId}-${index}`}
                          className={clsx(
                            "whitespace-pre-wrap rounded px-2 py-1",
                            line.kind === "added"
                              ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-200"
                              : line.kind === "removed"
                              ? "bg-rose-100 text-rose-700 dark:bg-rose-400/20 dark:text-rose-200"
                              : "bg-border-light/40 text-text-secondaryLight dark:bg-border-dark/30 dark:text-text-secondaryDark",
                          )}
                        >
                          {line.kind === "added" ? "+ " : line.kind === "removed" ? "- " : "  "}
                          {line.text || "(빈 줄)"}
                        </p>
                      ))}
                    </div>
                  </details>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>

    </section>
  );
}
