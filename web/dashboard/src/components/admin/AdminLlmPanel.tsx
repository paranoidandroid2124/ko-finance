"use client";

import { useAdminSession } from "@/hooks/useAdminSession";
import { resolveApiBase } from "@/lib/apiBase";
import { useToastStore } from "@/store/toastStore";

import { AdminLlmProfilesSection } from "./AdminLlmProfilesSection";
import { AdminSystemPromptsSection } from "./AdminSystemPromptsSection";

export function AdminLlmPanel() {
  const toast = useToastStore((state) => state.show);
  const {
    data: adminSession,
    isLoading: isAdminSessionLoading,
    isUnauthorized,
    refetch: refetchAdminSession,
  } = useAdminSession();

  if (isAdminSessionLoading) {
    return (
      <section className="rounded-xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">관리자 세션을 확인하는 중이에요…</p>
      </section>
    );
  }

  if (isUnauthorized) {
    return (
      <section className="rounded-xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          LLM 설정을 보려면 관리자 토큰 로그인이 필요해요.
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

  const auditDownloadUrl = `${resolveApiBase()}/api/v1/admin/llm/audit/logs`;
  const actorPlaceholder = adminSession.actor ?? "";

  return (
    <section className="space-y-4 rounded-xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <header className="space-y-1 border-b border-border-light pb-3 dark:border-border-dark">
        <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">LLM & 프롬프트 설정</h2>
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          LiteLLM 프로필과 시스템 프롬프트를 직접 조정하고, 감사 로그를 내려받아 변경 이력을 살펴볼 수 있어요.
        </p>
        <a
          href={auditDownloadUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs font-semibold text-primary hover:underline dark:text-primary.dark"
        >
          감사 로그 다운로드 (llm_audit.jsonl)
        </a>
      </header>

      <div className="space-y-4">
        <AdminLlmProfilesSection adminActor={adminSession.actor} actorPlaceholder={actorPlaceholder} toast={toast} />
        <AdminSystemPromptsSection adminActor={adminSession.actor} actorPlaceholder={actorPlaceholder} toast={toast} />
      </div>
    </section>
  );
}
