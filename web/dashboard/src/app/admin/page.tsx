"use client";

import { useState } from "react";

import { AdminGuardrailPanel } from "@/components/admin/AdminGuardrailPanel";
import { AdminLlmPanel } from "@/components/admin/AdminLlmPanel";
import { AdminOpsPanel } from "@/components/admin/AdminOpsPanel";
import { AdminRagPanel } from "@/components/admin/AdminRagPanel";
import { AdminUiUxPanel } from "@/components/admin/AdminUiUxPanel";
import { AdminTokenLoginCard } from "@/components/admin/AdminTokenLoginCard";
import { PlanQuickActionsPanel } from "@/components/admin/PlanQuickActionsPanel";
import { TossWebhookAuditPanel } from "@/components/admin/TossWebhookAuditPanel";
import { AdminShell } from "@/components/layout/AdminShell";
import { PlanAlertOverview } from "@/components/plan/PlanAlertOverview";
import { PlanSummaryCard } from "@/components/plan/PlanSummaryCard";
import { PlanTierPreview } from "@/components/plan/PlanTierPreview";
import { useAlertRules } from "@/hooks/useAlerts";

type Section = {
  id: string;
  title: string;
  description: string;
  bullets: string[];
  actionLabel: string;
};

type QuickAction = {
  id: string;
  label: string;
  description: string;
};

const CONFIG_SECTIONS: Section[] = [
  {
    id: "llm",
    title: "LLM & 프롬프트",
    description: "상담·RAG 흐름에 사용하는 기본 프롬프트와 모델 라우팅을 다듬어요.",
    bullets: ["시스템 인스트럭션", "LiteLLM 프로필", "재시도·페일오버 정책"],
    actionLabel: "프롬프트 관리하기",
  },
  {
    id: "guardrails",
    title: "Guardrail 정책",
    description: "의도 필터, 금지어, 안내 문구를 조정해 안전망을 강화해요.",
    bullets: ["Intent rules", "Blocklist", "Friendly fallback"],
    actionLabel: "Guardrail 다듬기",
  },
  {
    id: "rag",
    title: "RAG 컨텍스트",
    description: "근거 패널에 사용할 데이터 소스와 임계값을 직접 관리해요.",
    bullets: ["데이터 소스", "필터 조건", "유사도 임계값"],
    actionLabel: "RAG 설정 열기",
  },
  {
    id: "ui",
    title: "UI & UX 설정",
    description: "대시보드 기본값과 친근한 안내 문구를 팀 컬러에 맞게 조정해요.",
    bullets: ["기본 기간 & 첫 화면", "브랜드 강조 컬러", "온보딩 배너 문구"],
    actionLabel: "인터페이스 조정",
  },
];

const OPERATIONS_SECTIONS: Section[] = [
  {
    id: "news-pipeline",
    title: "뉴스·섹터 파이프라인",
    description: "RSS 피드, 섹터 매핑, 감성 임계값을 한눈에 관리해요.",
    bullets: ["RSS 소스", "섹터 키워드", "감성 임계값"],
    actionLabel: "파이프라인 편집",
  },
  {
    id: "schedules",
    title: "스케줄 & 작업",
    description: "Celery 스케줄을 확인하고 필요한 작업을 즉시 실행해요.",
    bullets: ["주기 확인", "수동 실행", "실행 로그"],
    actionLabel: "스케줄 관리",
  },
  {
    id: "operations",
    title: "운영 & 접근 제어",
    description: "Langfuse 토글과 외부 API 키를 최신 상태로 유지해요.",
    bullets: ["Langfuse 설정", "외부 API", "운영 모드"],
    actionLabel: "운영 설정 열기",
  },
  {
    id: "alerts",
    title: "알림 채널",
    description: "텔레그램, 이메일, 웹훅 채널을 살펴보고 업데이트해요.",
    bullets: ["채널 구성", "메시지 템플릿", "에스컬레이션"],
    actionLabel: "알림 조정",
  },
];

const QUICK_ACTIONS: QuickAction[] = [
  {
    id: "seed-news",
    label: "Seed news feeds",
    description: "Queue the `m2.seed_news_feeds` task to fetch the latest RSS content.",
  },
  {
    id: "aggregate-sentiment",
    label: "Run sentiment aggregation",
    description: "Trigger `m2.aggregate_news` and sector aggregation warm-ups.",
  },
  {
    id: "rebuild-rag",
    label: "Refresh RAG index",
    description: "Launch the vector service backfill to sync filings and documents.",
  },
];

function SectionCard({
  section,
  onSelect,
  isActive,
}: {
  section: Section;
  onSelect: (id: string) => void;
  isActive: boolean;
}) {
  const { id, title, description, bullets, actionLabel } = section;
  const borderClass = isActive
    ? "border-primary shadow-lg shadow-primary/10 dark:border-primary.dark"
    : "border-border-light dark:border-border-dark";

  return (
    <article
      className={`flex h-full flex-col rounded-xl border bg-background-cardLight p-6 shadow-card transition-colors dark:bg-background-cardDark ${borderClass}`}
    >
      <header>
        <h3 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">{title}</h3>
        <p className="mt-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">{description}</p>
      </header>
      <ul className="mt-4 space-y-1 text-sm text-text-tertiaryLight dark:text-text-tertiaryDark">
        {bullets.map((item) => (
          <li key={`${id}-${item}`}>- {item}</li>
        ))}
      </ul>
      <button
        type="button"
        onClick={() => onSelect(id)}
        className="mt-auto inline-flex items-center justify-center rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-primaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-primaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
      >
        {actionLabel}
      </button>
    </article>
  );
}

function QuickActionCard({ action }: { action: QuickAction }) {
  return (
    <div className="flex items-start justify-between rounded-xl border border-border-light bg-background-cardLight p-5 text-sm transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <div>
        <h4 className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{action.label}</h4>
        <p className="mt-1 text-text-secondaryLight dark:text-text-secondaryDark">{action.description}</p>
      </div>
      <button
        type="button"
        disabled
        className="inline-flex cursor-not-allowed items-center rounded-md bg-border-light px-3 py-1 text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:bg-border-dark dark:text-text-secondaryDark"
      >
        coming soon
      </button>
    </div>
  );
}

export default function AdminPage() {
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const {
    data: alertRulesData,
    isLoading: isAlertPlanLoading,
    isError: isAlertPlanError,
  } = useAlertRules();

  const alertPlan = alertRulesData?.plan ?? null;
  const alertPlanErrorMessage = isAlertPlanError ? "알림 플랜 정보를 불러오지 못했어요." : undefined;

  const activePanel = (() => {
    switch (activeSection) {
      case "llm":
        return <AdminLlmPanel />;
      case "guardrails":
        return <AdminGuardrailPanel />;
      case "rag":
        return <AdminRagPanel />;
      case "news-pipeline":
        return <AdminOpsPanel sections={["news"]} />;
      case "schedules":
        return <AdminOpsPanel sections={["schedules"]} />;
      case "operations":
        return <AdminOpsPanel sections={["integrations"]} />;
      case "alerts":
        return <AdminOpsPanel sections={["alerts"]} />;
      case "ui":
        return <AdminUiUxPanel />;
      default:
        return null;
    }
  })();

  const activeSectionLabel =
    CONFIG_SECTIONS.concat(OPERATIONS_SECTIONS).find((section) => section.id === activeSection)?.title ?? "선택되지 않음";

  return (
    <AdminShell
      title="운영 센터"
      description="친근한 사회적 기업 톤으로 플랜·RAG·결제 파이프라인을 살피고 조정할 수 있는 관리자 공간이에요."
    >
      <AdminTokenLoginCard />

      <div className="grid gap-6 xl:grid-cols-[2fr,1fr]">
        <PlanQuickActionsPanel />
        <div className="space-y-6">
          <PlanSummaryCard />
          <PlanAlertOverview plan={alertPlan} loading={isAlertPlanLoading} error={alertPlanErrorMessage} />
          <TossWebhookAuditPanel />
        </div>
      </div>

      <PlanTierPreview className="xl:max-w-3xl" />

      <div className="rounded-xl border border-dashed border-border-light bg-background-cardLight p-6 text-sm text-text-secondaryLight shadow-card dark:border-border-dark dark:bg-background-cardDark dark:text-text-secondaryDark">
        <p>프롬프트, 가드레일, 데이터 파이프라인 설정을 단계별로 정리해 두었어요.</p>
        <p className="mt-2">
          현재 선택된 영역:&nbsp;
          <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{activeSectionLabel}</span>
        </p>
      </div>

      <section className="space-y-4">
        <header>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
            Configuration Domains
          </h2>
        </header>
        <div className="grid gap-4 md:grid-cols-2">
          {CONFIG_SECTIONS.map((section) => (
            <SectionCard
              key={section.id}
              section={section}
              onSelect={setActiveSection}
              isActive={activeSection === section.id}
            />
          ))}
        </div>
      </section>

      <section className="space-y-4">
        <header>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
            Pipeline & Operations
          </h2>
        </header>
        <div className="grid gap-4 md:grid-cols-2">
          {OPERATIONS_SECTIONS.map((section) => (
            <SectionCard
              key={section.id}
              section={section}
              onSelect={setActiveSection}
              isActive={activeSection === section.id}
            />
          ))}
        </div>
      </section>

      {activePanel ? (
        <section className="space-y-4">
          <header className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
              {activeSectionLabel}
            </h2>
            <button
              type="button"
              onClick={() => setActiveSection(null)}
              className="inline-flex items-center rounded-lg border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
            >
              선택 닫기
            </button>
          </header>
          {activePanel}
        </section>
      ) : null}

      <section className="space-y-4">
        <header>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
            Quick Actions
          </h2>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            운영용 API와 툴이 연결되면 이 자리에서 바로 실행할 수 있어요. 지금은 준비 중이라 미리보기 상태로 표시돼요.
          </p>
        </header>
        <div className="space-y-3">
          {QUICK_ACTIONS.map((action) => (
            <QuickActionCard key={action.id} action={action} />
          ))}
        </div>
      </section>
    </AdminShell>
  );
}
