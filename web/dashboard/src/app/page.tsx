"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Command, FlaskConical, FileText, MessageSquare, Filter } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import DeepTechLayout from "@/components/layout/DeepTechLayout";
import SpotlightCard from "@/components/ui/SpotlightCard";

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
      <DeepTechLayout className="px-4 pb-16 pt-12 md:px-12">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-14">
          <section className="flex flex-col gap-10 md:flex-row md:items-center md:justify-between">
            <div className="flex-1 space-y-6">
              <span className="text-xs font-semibold tracking-[0.45em] text-indigo-200">CHAT AS A COMMANDER</span>
              <h1 className="text-4xl font-semibold leading-tight text-white md:text-5xl">
                말하면 차트와 도구가 바로 열리는 새로운 홈
              </h1>
              <p className="text-base text-slate-300">
                복잡한 GNB 대신 챗 세션이 모든 Deep Tool을 호출합니다. 판단은 AI가, 검증은 UI가 진행하세요.
              </p>
              <div className="flex flex-wrap gap-3 text-xs uppercase tracking-wide text-slate-400">
                <span className="rounded-full border border-white/10 px-3 py-1">Bloomberg Depth</span>
                <span className="rounded-full border border-white/10 px-3 py-1">ChatGPT Usability</span>
                <span className="rounded-full border border-white/10 px-3 py-1">Compliance Guard</span>
              </div>
            </div>
            <SpotlightCard className="w-full max-w-sm self-stretch bg-white/[0.02] p-6 text-sm text-slate-100 shadow-[0_25px_55px_rgba(3,7,18,0.55)]">
              <p className="text-sm font-semibold text-white">Commander가 열어줄 수 있는 주요 흐름</p>
              <ul className="mt-4 space-y-2 text-[13px] text-slate-300">
                <li>• 이벤트 스터디, 공시 뷰어, 퀀트 스크리너</li>
                <li>• Paywall Teaser & LightMem 컨텍스트</li>
                <li>• 규제 필터 및 출처 강제 표기</li>
              </ul>
              <button
                onClick={() => router.push("/chat")}
                className="mt-6 inline-flex w-full items-center justify-center rounded-2xl bg-gradient-to-r from-[#6C63FF] via-[#7C4DFF] to-[#2DD4BF] px-4 py-2 text-sm font-semibold text-white shadow-[0_15px_45px_rgba(108,99,255,0.35)] transition hover:translate-y-[-1px]"
              >
                Commander 열기
                <MessageSquare className="ml-2 h-4 w-4" aria-hidden="true" />
              </button>
            </SpotlightCard>
          </section>

          <section className="space-y-5">
            <div className="flex flex-col gap-3 text-slate-200 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.4em] text-indigo-200">Commander Examples</p>
                <h2 className="mt-2 text-2xl font-semibold text-white">Commander 호출 예시</h2>
                <p className="text-sm text-slate-400">자연어 프롬프트만으로 분석 UI가 사용자 앞으로 펼쳐집니다.</p>
              </div>
              <button
                onClick={() => router.push("/chat")}
                className="inline-flex items-center gap-2 rounded-full border border-white/15 px-5 py-1.5 text-sm font-medium text-slate-200 transition hover:border-cyan-300 hover:text-white"
              >
                새 챗 시작
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
            <div className="grid gap-5 md:grid-cols-3">
              {COMMANDER_TOOLS.map(({ title, description, example, icon: Icon }) => (
                <SpotlightCard key={title} className="h-full bg-white/[0.02] p-5 text-slate-200">
                  <div className="mb-4 flex items-center gap-2 text-indigo-200">
                    <Icon className="h-5 w-5" aria-hidden="true" />
                    <span className="text-sm font-semibold uppercase tracking-wide">{title}</span>
                  </div>
                  <p className="text-sm text-slate-300">{description}</p>
                  <p className="mt-4 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-slate-100">
                    {example}
                  </p>
                </SpotlightCard>
              ))}
            </div>
          </section>

          <section className="space-y-5">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.4em] text-indigo-200">Workflow Ready</p>
              <h2 className="mt-2 text-2xl font-semibold text-white">직접 탐색 가능한 Workspaces</h2>
              <p className="text-sm text-slate-400">반복 탐색이 필요한 핵심 툴은 여전히 독립 화면으로 접근 가능합니다.</p>
            </div>
            <div className="grid gap-5 md:grid-cols-3">
              {DIRECT_WORKSPACES.map(({ title, description, href, icon: Icon }) => (
                <Link key={title} href={href} className="group block">
                  <SpotlightCard className="h-full bg-white/[0.02] p-5 text-slate-200 transition group-hover:-translate-y-1">
                    <div className="flex items-center gap-2 text-cyan-200">
                      <Icon className="h-5 w-5" aria-hidden="true" />
                      <span className="text-sm font-semibold uppercase tracking-wide">{title}</span>
                    </div>
                    <p className="mt-3 text-sm text-slate-300">{description}</p>
                    <span className="mt-6 inline-flex items-center text-sm font-semibold text-cyan-200 transition group-hover:text-white">
                      바로 가기
                      <ArrowRight className="ml-1 h-4 w-4" />
                    </span>
                  </SpotlightCard>
                </Link>
              ))}
            </div>
          </section>
        </div>
      </DeepTechLayout>
    </AppShell>
  );
}
