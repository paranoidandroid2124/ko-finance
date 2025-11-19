"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Command, FlaskConical, FileText, MessageSquare, Filter } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";

const COMMANDER_TOOLS = [
  {
    title: "이벤트 스터디",
    description: "실적발표·IR 이후의 CAR/CAAR 패턴을 바로 계산합니다.",
    example: '예: "삼성전자 이벤트 스터디 -2~5일 구간 보여줘"',
    icon: FlaskConical,
  },
  {
    title: "지능형 공시 뷰어",
    description: "AI가 중요 문단을 찾아주고 관련 하이라이트를 오버레이합니다.",
    example: '예: "LG화학 최근 공시에서 CAPEX 강조된 부분 열어줘"',
    icon: FileText,
  },
  {
    title: "퀀트 스크리너",
    description: "자연어 조건으로 저평가 종목, 마진 개선 종목 등을 필터링합니다.",
    example: '예: "영업이익률 20% 이상 바이오 종목 중 저평가를 보여줘"',
    icon: Filter,
  },
];

const DIRECT_WORKSPACES = [
  {
    title: "Event Study Workspace",
    description: "파라미터를 조정하며 직접 패턴을 비교하고 PDF를 추출할 수 있습니다.",
    href: "/event-study",
    icon: FlaskConical,
  },
  {
    title: "Evidence Workspace",
    description: "공시·리서치 전문을 탐색하며 하이라이트 구간을 직접 확인합니다.",
    href: "/evidence",
    icon: FileText,
  },
  {
    title: "Labs · Research Tools",
    description: "실험적 기능과 데이터 파이프라인을 테스트하는 공간입니다.",
    href: "/labs",
    icon: Command,
  },
];

export default function CommanderHomePage() {
  const router = useRouter();

  return (
    <AppShell>
      <div className="space-y-8">
        <section className="rounded-3xl border border-border-light bg-background-cardLight px-8 py-10 shadow-sm dark:border-border-dark dark:bg-background-cardDark">
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div className="space-y-4">
              <p className="text-sm font-semibold uppercase tracking-wide text-primary dark:text-primary.dark">
                Chat as a Commander
              </p>
              <h1 className="text-3xl font-semibold text-text-primaryLight dark:text-text-primaryDark md:text-4xl">
                말하면 차트와 도구가 바로 열리는 새로운 홈
              </h1>
              <p className="text-base text-text-secondaryLight dark:text-text-secondaryDark">
                복잡한 GNB 대신, 챗 세션이 모든 Deep Tool을 자동으로 호출합니다. 판단은 AI가, 검증은 UI로 진행하세요.
              </p>
            </div>
            <div className="flex flex-col gap-3 rounded-2xl border border-dashed border-border-light p-5 dark:border-border-dark">
              <p className="text-sm font-medium text-text-secondaryLight dark:text-text-secondaryDark">
                Commander가 열어줄 수 있는 주요 흐름
              </p>
              <ul className="space-y-2 text-sm text-text-primaryLight dark:text-text-primaryDark">
                <li>• 이벤트 스터디, 공시 뷰어, 퀀트 스크리너 등 Deep Tool</li>
                <li>• Paywall Teaser & LightMem 컨텍스트</li>
                <li>• 규제 필터 및 출처 강제 표기</li>
              </ul>
              <button
                onClick={() => router.push("/chat")}
                className="inline-flex items-center justify-center rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-primary/90 dark:bg-primary.dark dark:hover:bg-primary.dark/90"
              >
                Commander 열기
                <MessageSquare className="ml-2 h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark">Commander 호출 예시</h2>
              <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                자연어 프롬프트만으로 분석 UI가 사용자를 향해 펼쳐집니다.
              </p>
            </div>
            <button
              onClick={() => router.push("/chat")}
              className="hidden items-center gap-1 rounded-full border border-border-light px-4 py-1.5 text-sm font-medium text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark md:inline-flex"
            >
              새 챗 시작
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {COMMANDER_TOOLS.map(({ title, description, example, icon: Icon }) => (
              <div
                key={title}
                className="rounded-2xl border border-border-light bg-background-cardLight p-5 shadow-sm transition hover:border-primary/50 hover:shadow-md dark:border-border-dark dark:bg-background-cardDark"
              >
                <div className="mb-4 flex items-center gap-2 text-primary dark:text-primary.dark">
                  <Icon className="h-5 w-5" aria-hidden="true" />
                  <span className="text-sm font-semibold uppercase tracking-wide">{title}</span>
                </div>
                <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">{description}</p>
                <p className="mt-4 rounded-xl bg-background px-4 py-3 text-sm font-medium text-text-primaryLight dark:bg-background-dark dark:text-text-primaryDark">
                  {example}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="space-y-4">
          <div>
            <h2 className="text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark">직접 탐색 가능한 Workspaces</h2>
            <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
              반복 탐색이 필요한 핵심 툴은 여전히 독립 화면으로 접근할 수 있습니다.
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {DIRECT_WORKSPACES.map(({ title, description, href, icon: Icon }) => (
              <Link
                key={title}
                href={href}
                className="group rounded-2xl border border-border-light bg-background-cardLight p-5 shadow-sm transition hover:border-primary hover:shadow-md dark:border-border-dark dark:bg-background-cardDark"
              >
                <div className="flex items-center gap-2 text-primary dark:text-primary.dark">
                  <Icon className="h-5 w-5" aria-hidden="true" />
                  <span className="text-sm font-semibold uppercase tracking-wide">{title}</span>
                </div>
                <p className="mt-3 text-sm text-text-secondaryLight dark:text-text-secondaryDark">{description}</p>
                <span className="mt-6 inline-flex items-center text-sm font-semibold text-primary transition group-hover:gap-2 dark:text-primary.dark">
                  바로 가기
                  <ArrowRight className="ml-1 h-4 w-4" />
                </span>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
