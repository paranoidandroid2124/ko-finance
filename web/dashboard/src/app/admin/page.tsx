"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";

import { AdminGuardrailPanel } from "@/components/admin/AdminGuardrailPanel";
import { AdminLlmPanel } from "@/components/admin/AdminLlmPanel";
import { AdminOpsPanel } from "@/components/admin/AdminOpsPanel";
import { AdminRagPanel } from "@/components/admin/AdminRagPanel";
import { AdminReportsPanel } from "@/components/admin/AdminReportsPanel";
import { AdminUiUxPanel } from "@/components/admin/AdminUiUxPanel";
import { AdminTokenLoginCard } from "@/components/admin/AdminTokenLoginCard";
import { PlanQuickActionsPanel } from "@/components/admin/PlanQuickActionsPanel";
import { TossWebhookAuditPanel } from "@/components/admin/TossWebhookAuditPanel";
import { AdminShell } from "@/components/layout/AdminShell";
import { PlanAlertOverview } from "@/components/plan/PlanAlertOverview";
import { PlanSummaryCard } from "@/components/plan/PlanSummaryCard";
import { PlanTierPreview } from "@/components/plan/PlanTierPreview";
import { useAlertRules } from "@/hooks/useAlerts";
import { useAdminSession } from "@/hooks/useAdminSession";
import { useTriggerQuickAction } from "@/hooks/useAdminQuickActions";
import { useToastStore } from "@/store/toastStore";
import type { AdminQuickActionId } from "@/lib/adminApi";

type Section = {
  id: string;
  title: string;
  description: string;
  bullets: string[];
  actionLabel: string;
};

type QuickAction = {
  id: AdminQuickActionId;
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
    id: "reports",
    title: "리포트 & PDF",
    description: "데일리 브리프 PDF 생성 이력을 살피고 필요한 시점에 재생성해요.",
    bullets: ["생성 히스토리", "PDF·TeX 다운로드", "수동 재생성"],
    actionLabel: "리포트 관리",
  },
  {
    id: "operations",
    title: "운영 & 접근 제어",
    description: "Langfuse 토글과 외부 API 키를 최신 상태로 유지해요.",
    bullets: ["Langfuse 설정", "외부 API", "운영 모드"],
    actionLabel: "운영 설정 열기",
  },
  {
    id: "watchlist",
    title: "워치리스트 모니터링",
    description: "워치리스트 알림 전송 성공률과 실패 기록을 집중적으로 살펴봐요.",
    bullets: ["전송 실패 로그", "채널별 통계", "재전송 워크플로"],
    actionLabel: "워치리스트 살펴보기",
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
    label: "뉴스 피드 수집",
    description: "`m2.seed_news_feeds` 태스크를 실행해 최신 RSS 뉴스를 가져옵니다.",
  },
  {
    id: "aggregate-sentiment",
    label: "감성 집계 실행",
    description: "`m2.aggregate_news`와 섹터 집계 워크플로를 즉시 실행합니다.",
  },
  {
    id: "rebuild-rag",
    label: "RAG 인덱스 새로 고침",
    description: "공시·문서를 다시 읽어 인덱스를 최신 상태로 동기화합니다.",
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

function QuickActionCard({ action, actor }: { action: QuickAction; actor: string | null }) {
  const triggerQuickAction = useTriggerQuickAction();
  const showToast = useToastStore((state) => state.show);

  const handleClick = async () => {
    if (!actor) {
      showToast({
        intent: "warning",
        message: "운영 토큰 인증을 완료한 뒤에 실행할 수 있어요.",
      });
      return;
    }
    try {
      const result = await triggerQuickAction.mutateAsync({
        action: action.id,
        actor,
      });
      const successMessage =
        result.message ??
        (result.taskId ? `작업 ${result.taskId} (${result.status})` : `상태: ${result.status}`);
      showToast({
        id: `admin/quick-action/${action.id}/${Date.now()}`,
        intent: "success",
        title: `${action.label} 실행`,
        message: successMessage,
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "퀵 액션을 실행하지 못했어요. 잠시 후 다시 시도해 주세요.";
      showToast({
        id: `admin/quick-action/${action.id}/error/${Date.now()}`,
        intent: "error",
        title: `${action.label} 실행 실패`,
        message,
      });
    }
  };

  const isPending = triggerQuickAction.isPending;
  const isDisabled = isPending || !actor;
  const buttonClass =
    "inline-flex items-center gap-2 rounded-md border px-3 py-1 text-xs font-semibold uppercase tracking-wide transition";

  return (
    <div className="flex items-start justify-between rounded-xl border border-border-light bg-background-cardLight p-5 text-sm transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <div>
        <h4 className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{action.label}</h4>
        <p className="mt-1 text-text-secondaryLight dark:text-text-secondaryDark">{action.description}</p>
      </div>
      <button
        type="button"
        onClick={handleClick}
        disabled={isDisabled}
        className={`${buttonClass} ${
          isDisabled
            ? "cursor-not-allowed border-border-light text-text-secondaryLight opacity-60 dark:border-border-dark dark:text-text-secondaryDark"
            : "border-border-light text-primary hover:border-primary hover:text-primary dark:border-border-dark dark:text-primary.dark dark:hover:border-primary.dark dark:hover:text-primary.dark"
        }`}
      >
        {isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
        {isPending ? "실행 중…" : "바로 실행"}
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
  const { data: adminSession } = useAdminSession();
  const sessionActor = adminSession?.actor ?? null;

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
      case "watchlist":
        return <AdminOpsPanel sections={["watchlist"]} />;
      case "reports":
        return <AdminReportsPanel />;
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
      <div className="mb-6">
        <AdminTokenLoginCard />
      </div>

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
            운영 중 즉시 실행이 필요한 작업을 한 번에 처리할 수 있어요. 큐에 등록된 작업은 감사 로그와 실행 기록에 남습니다.
          </p>
        </header>
        <div className="space-y-3">
          {QUICK_ACTIONS.map((action) => (
            <QuickActionCard key={action.id} action={action} actor={sessionActor} />
          ))}
        </div>
      </section>
    </AdminShell>
  );
}
