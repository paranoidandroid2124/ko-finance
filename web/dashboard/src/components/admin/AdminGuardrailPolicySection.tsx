"use client";

import clsx from "classnames";
import { useEffect, useMemo, useState } from "react";

import { useGuardrailPolicy, useUpdateGuardrailPolicy } from "@/hooks/useAdminConfig";
import type { ToastInput } from "@/store/toastStore";

type GuardrailFormState = {
  intentRulesJson: string;
  blocklistText: string;
  fallbackCopy: string;
  blockedCopy: string;
  actor: string;
  note: string;
  error?: string | null;
};

const formatIntentRules = (value: unknown) => {
  try {
    return JSON.stringify(value ?? [], null, 2);
  } catch {
    return "[]";
  }
};

const toBlocklistText = (items?: string[]) => (items?.length ? items.join("\n") : "");

const parseBlocklist = (text: string) =>
  text
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

interface AdminGuardrailPolicySectionProps {
  adminActor?: string | null;
  actorPlaceholder?: string;
  auditDownloadUrl: string;
  toast: (toast: ToastInput) => string;
}

export function AdminGuardrailPolicySection({
  adminActor,
  actorPlaceholder = "",
  auditDownloadUrl,
  toast,
}: AdminGuardrailPolicySectionProps) {
  const {
    data: policyResponse,
    isLoading: isPolicyLoading,
    isError: isPolicyError,
    error: policyError,
    refetch: refetchPolicy,
  } = useGuardrailPolicy(true);

  const updatePolicy = useUpdateGuardrailPolicy();

  const [formState, setFormState] = useState<GuardrailFormState>({
    intentRulesJson: "[]",
    blocklistText: "",
    fallbackCopy: "",
    blockedCopy: "",
    actor: adminActor ?? actorPlaceholder ?? "",
    note: "",
  });

  useEffect(() => {
    if (!policyResponse?.policy) {
      setFormState((prev) => ({
        ...prev,
        actor: adminActor ?? actorPlaceholder ?? prev.actor,
      }));
      return;
    }
    setFormState((prev) => ({
      ...prev,
      intentRulesJson: formatIntentRules(policyResponse.policy.intentRules),
      blocklistText: toBlocklistText(policyResponse.policy.blocklist),
      fallbackCopy: policyResponse.policy.userFacingCopy?.fallback ?? "",
      blockedCopy: policyResponse.policy.userFacingCopy?.blocked ?? "",
      actor: adminActor ?? actorPlaceholder ?? prev.actor,
      note: "",
      error: undefined,
    }));
  }, [policyResponse, adminActor, actorPlaceholder]);

  const lastUpdated = useMemo(() => {
    if (!policyResponse?.updatedAt) {
      return null;
    }
    try {
      const date = new Date(policyResponse.updatedAt);
      if (Number.isNaN(date.getTime())) {
        return policyResponse.updatedAt;
      }
      return date.toLocaleString("ko-KR");
    } catch {
      return policyResponse.updatedAt;
    }
  }, [policyResponse?.updatedAt]);

  const handleFieldChange = (field: keyof GuardrailFormState, value: string) => {
    setFormState((prev) => ({ ...prev, [field]: value, error: field === "error" ? prev.error : undefined }));
  };

  const handleSubmit = async () => {
    let intentRules: unknown;
    try {
      intentRules = formState.intentRulesJson.trim() ? JSON.parse(formState.intentRulesJson) : [];
      if (!Array.isArray(intentRules)) {
        throw new Error();
      }
    } catch {
      setFormState((prev) => ({ ...prev, error: "의도 규칙 JSON 형식이 올바르지 않아요." }));
      return;
    }

    try {
      await updatePolicy.mutateAsync({
        intentRules: intentRules as Array<Record<string, unknown>>,
        blocklist: parseBlocklist(formState.blocklistText),
      userFacingCopy: {
        fallback: formState.fallbackCopy,
        blocked: formState.blockedCopy,
      },
      actor: formState.actor.trim() || adminActor || actorPlaceholder || "unknown-admin",
      note: formState.note.trim() || null,
      });
      toast({
        id: "admin/guardrail/policy/success",
        title: "Guardrail 정책이 저장됐어요",
        message: "의도 규칙과 안내 문구가 최신 상태예요.",
        intent: "success",
      });
      setFormState((prev) => ({ ...prev, error: undefined, note: "" }));
      await refetchPolicy();
    } catch (error) {
      const message = error instanceof Error ? error.message : "정책을 저장하지 못했어요.";
      toast({
        id: "admin/guardrail/policy/error",
        title: "정책 저장 실패",
        message,
        intent: "error",
      });
    }
  };

  if (isPolicyLoading && !policyResponse) {
    return (
      <section className="rounded-xl border border-border-light bg-background-cardLight p-6 text-sm text-text-secondaryLight shadow-card dark:border-border-dark dark:bg-background-cardDark">
        Guardrail 정책을 불러오는 중이에요…
      </section>
    );
  }

  const actorInputPlaceholder = adminActor || actorPlaceholder || "운영자 이름";

  return (
    <section className="space-y-4 rounded-xl border border-border-light bg-background-base p-4 dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
            정책 편집
          </h3>
          <div className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
            <span>최근 수정: {lastUpdated ?? "기록 없음"}</span>
            <span className="mx-2 text-border-light">|</span>
            <span>작성자: {policyResponse?.updatedBy ?? "—"}</span>
          </div>
        </div>
        <a
          href={auditDownloadUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs font-semibold text-primary hover:underline dark:text-primary.dark"
        >
          감사 로그 다운로드
        </a>
      </div>

      {isPolicyError ? (
        <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-700 dark:border-amber-500/70 dark:bg-amber-500/10 dark:text-amber-200">
          Guardrail 정책을 불러오지 못했어요.{" "}
          {policyError instanceof Error ? policyError.message : "잠시 후 다시 시도해 주세요."}
        </p>
      ) : null}

      <label className="flex flex-col gap-2 text-sm">
        <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">의도 규칙 (JSON 배열)</span>
        <textarea
          value={formState.intentRulesJson}
          onChange={(event) => handleFieldChange("intentRulesJson", event.target.value)}
          className="min-h-[200px] rounded-lg border border-border-light bg-background-base px-3 py-2 font-mono text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
        />
        <span className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
          {'예: [{"intent": "investment", "severity": "high"}, ...]'}
        </span>
      </label>

      <label className="flex flex-col gap-2 text-sm">
        <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">Blocklist (줄바꿈 구분)</span>
        <textarea
          value={formState.blocklistText}
          onChange={(event) => handleFieldChange("blocklistText", event.target.value)}
          className="min-h-[140px] rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
        />
      </label>

      <div className="grid gap-3 md:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          친근한 fallback 문구
          <textarea
            value={formState.fallbackCopy}
            onChange={(event) => handleFieldChange("fallbackCopy", event.target.value)}
            className="min-h-[120px] rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
            placeholder="필요한 경우에만 안내 문구를 보여주세요."
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          차단 시 안내 문구
          <textarea
            value={formState.blockedCopy}
            onChange={(event) => handleFieldChange("blockedCopy", event.target.value)}
            className="min-h-[120px] rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
            placeholder="차단 시 사용자가 이해하기 쉬운 안내 문구를 입력해 주세요."
          />
        </label>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          실행자(Actor)
          <input
            type="text"
            value={formState.actor}
            onChange={(event) => handleFieldChange("actor", event.target.value)}
            placeholder={actorInputPlaceholder}
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          변경 메모
          <input
            type="text"
            value={formState.note}
            onChange={(event) => handleFieldChange("note", event.target.value)}
            placeholder="예: Blocklist에 신규 키워드 추가"
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
      </div>

      {formState.error ? (
        <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-700 dark:border-amber-500/70 dark:bg-amber-500/10 dark:text-amber-200">
          {formState.error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center justify-end gap-3">
        <button
          type="button"
          onClick={() => refetchPolicy()}
          className="inline-flex items-center rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
          disabled={isPolicyLoading}
        >
          최신 상태 불러오기
        </button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={updatePolicy.isPending}
          className={clsx(
            "inline-flex items-center rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-white transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
            updatePolicy.isPending && "cursor-not-allowed opacity-60",
          )}
        >
          {updatePolicy.isPending ? "저장 중…" : "정책 저장"}
        </button>
      </div>
    </section>
  );
}
