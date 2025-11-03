"use client";

import { useAdminSession } from "@/hooks/useAdminSession";
import { resolveApiBase } from "@/lib/apiBase";
import { useToastStore } from "@/store/toastStore";

import { AdminGuardrailPolicySection } from "./AdminGuardrailPolicySection";
import { AdminGuardrailEvaluateSection } from "./AdminGuardrailEvaluateSection";

export function AdminGuardrailPanel() {
  const toast = useToastStore((state) => state.show);
  const {
    data: adminSession,
    isLoading: isAdminSessionLoading,
    isUnauthorized,
    refetch: refetchAdminSession,
  } = useAdminSession();

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
          Guardrail 설정을 보려면 관리자 토큰 로그인이 필요해요.
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

  const auditDownloadUrl = `${resolveApiBase()}/api/v1/admin/llm/guardrails/audit/logs`;
  const actorPlaceholder = adminSession.actor ?? "";

  return (
    <section className="space-y-6 rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <header className="space-y-2 border-b border-border-light pb-4 dark:border-border-dark">
        <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">Guardrail 정책</h2>
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          의도 규칙과 금지어, 안내 문구를 조정해 안전망을 강화하고, 샘플 평가로 효과를 즉시 확인하세요.
        </p>
        <a
          href={auditDownloadUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs font-semibold text-primary hover:underline dark:text-primary.dark"
        >
          감사 로그 다운로드 (guardrail_audit.jsonl)
        </a>
      </header>

      <div className="space-y-6">
        <AdminGuardrailPolicySection
          adminActor={adminSession.actor}
          actorPlaceholder={actorPlaceholder}
          auditDownloadUrl={auditDownloadUrl}
          toast={toast}
        />
        <AdminGuardrailEvaluateSection adminActor={adminSession.actor} toast={toast} />
      </div>
    </section>
  );
}
