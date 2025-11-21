"use client";

import { useMemo } from "react";

import { useAdminSession } from "@/hooks/useAdminSession";
import { resolveApiBase } from "@/lib/apiBase";
import { useToastStore } from "@/store/toastStore";

import { AdminNewsPipelinePanel } from "./AdminOpsNewsPanel";
import { AdminOpsIntegrationsPanel } from "./AdminOpsIntegrationsPanel";
import { AdminOpsSchedulesPanel } from "./AdminOpsSchedulesPanel";

type OpsSection = "schedules" | "news" | "integrations";

export interface AdminOpsPanelProps {
  sections?: OpsSection[];
}

const DEFAULT_SECTIONS: OpsSection[] = ["schedules", "news", "integrations"];

const SECTION_COPY: Record<OpsSection, { title: string; description: string }> = {
  schedules: {
    title: "스케줄 & 작업",
    description: "Celery 스케줄을 확인하고 필요한 작업을 즉시 실행해요.",
  },
  news: {
    title: "뉴스·섹터 파이프라인",
    description: "RSS 피드, 섹터 매핑, 감성 임계값을 한눈에 관리해요.",
  },
  integrations: {
    title: "운영 & 접근 제어",
    description: "Langfuse 토큰과 외부 API 키를 최신 상태로 유지해요.",
  },
};

const normalizeSections = (sections?: OpsSection[]): OpsSection[] => {
  if (!sections || sections.length === 0) {
    return DEFAULT_SECTIONS;
  }
  const unique: OpsSection[] = [];
  for (const section of sections) {
    if (!DEFAULT_SECTIONS.includes(section)) {
      continue;
    }
    if (!unique.includes(section)) {
      unique.push(section);
    }
  }
  return unique.length ? unique : DEFAULT_SECTIONS;
};

export function AdminOpsPanel({ sections }: AdminOpsPanelProps) {
  const toast = useToastStore((state) => state.show);
  const {
    data: adminSession,
    isLoading: isAdminSessionLoading,
    isUnauthorized,
    refetch: refetchAdminSession,
  } = useAdminSession();

  const normalizedSections = useMemo(() => normalizeSections(sections), [sections]);
  const hasSingleSection = normalizedSections.length === 1;
  const primarySection = hasSingleSection ? normalizedSections[0] : null;

  const headerTitle = primarySection ? SECTION_COPY[primarySection].title : "운영 파이프라인";
  const headerDescription = primarySection
    ? SECTION_COPY[primarySection].description
    : "Celery 스케줄, 뉴스 파이프라인, API 키를 한 곳에서 관리할 수 있어요.";

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
          운영 설정을 보려면 관리자 토큰 로그인이 필요해요.
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

  const auditDownloadUrl = `${resolveApiBase()}/api/v1/admin/ops/audit/logs`;

  return (
    <section className="space-y-4 rounded-xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <header className="space-y-1 border-b border-border-light pb-3 dark:border-border-dark">
        <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">{headerTitle}</h2>
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">{headerDescription}</p>
        <a
          href={auditDownloadUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs font-semibold text-primary hover:underline dark:text-primary.dark"
        >
          감사 로그 다운로드 (ops_audit.jsonl)
        </a>
      </header>

      <div className="space-y-4">
        {normalizedSections.includes("schedules") ? (
          <AdminOpsSchedulesPanel adminActor={adminSession.actor} toast={toast} />
        ) : null}
        {normalizedSections.includes("news") ? (
          <AdminNewsPipelinePanel adminActor={adminSession.actor} toast={toast} />
        ) : null}
        {normalizedSections.includes("integrations") ? (
          <AdminOpsIntegrationsPanel adminActor={adminSession.actor} toast={toast} />
        ) : null}
      </div>
    </section>
  );
}
