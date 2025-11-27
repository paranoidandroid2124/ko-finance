"use client";

import Link from "next/link";
import type { Route } from "next";
import { ArrowRight, Sparkles, ShieldCheck, Users } from "lucide-react";

type PlanId = "starter" | "pro" | "team";

type PlanFeature = {
  label: string;
  highlight?: boolean;
  tooltip?: string;
};

type Plan = {
  id: PlanId;
  name: string;
  price: string;
  subtitle: string;
  badge?: string;
  ctaLabel: string;
  ctaHref: Route;
  ctaSecondary?: { label: string; href: string; external?: boolean };
  tone: "default" | "primary";
  features: PlanFeature[];
};

const PLANS: Plan[] = [
  {
    id: "starter",
    name: "Starter",
    price: "무료",
    subtitle: "금융 분석의 시작",
    ctaLabel: "무료로 시작하기",
    ctaHref: "/auth/signup",
    tone: "default",
    features: [
      { label: "기본 Q&A (월 100회)" },
      { label: "최근 공시 요약 & 핵심 포인트" },
      { label: "기본 이벤트 임팩트 미리보기" },
    ],
  },
  {
    id: "pro",
    name: "Pro",
    price: "월 14,900원",
    subtitle: "가장 강력한 AI 애널리스트",
    badge: "Most Popular",
    ctaLabel: "14일 무료 체험 시작",
    ctaHref: "/auth/signup?plan=pro",
    tone: "primary",
    features: [
      { label: "Starter의 모든 기능" },
      { label: "무제한 심층 분석 질문", highlight: true },
      { label: "이벤트 임팩트 카드", tooltip: "주요 이벤트의 가격 영향 핵심 요약" },
      { label: "정정 레이더", tooltip: "정정/오류 가능성을 빠르게 감지" },
      { label: "희석 임팩트 카드", tooltip: "증자·전환 이벤트 희석 효과 추정" },
      { label: "프로액티브 인사이트 (일 5회)" },
      { label: "LightMem 요약 저장" },
    ],
  },
  {
    id: "team",
    name: "Team",
    price: "월 49,000원",
    subtitle: "팀 협업과 보안이 필요한 조직용",
    ctaLabel: "팀으로 시작하기",
    ctaHref: "/auth/signup?plan=enterprise",
    ctaSecondary: {
      label: "데모 보기",
      href: "mailto:sales@nuvien.ai?subject=Nuvien%20Team%20데모%20문의",
      external: true,
    },
    tone: "default",
    features: [
      { label: "Pro의 모든 기능" },
      { label: "이벤트 퀄리티 점수", tooltip: "이벤트 신뢰도·영향도 총점" },
      { label: "공시 위생 점수", tooltip: "공시 신뢰도·정합성 평가" },
      { label: "마켓 스크리너", tooltip: "섹터/팩터 기반 종목 발굴" },
      { label: "팀 워크스페이스 · 멤버 초대" },
      { label: "팀 채팅 · 공유 노트 · 권한 관리" },
      { label: "SSO 및 강화된 보안" },
    ],
  },
];

const ICONS: Record<PlanId, JSX.Element> = {
  starter: <Sparkles className="h-5 w-5 text-primary" />,
  pro: <ShieldCheck className="h-5 w-5 text-accent-amber" />,
  team: <Users className="h-5 w-5 text-accent-emerald" />,
};

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-canvas text-text-primary px-4 py-16">
      <div className="mx-auto max-w-6xl space-y-8">
        <div className="text-center space-y-3">
          <p className="text-sm font-semibold tracking-wide text-primary uppercase">Pricing</p>
          <h1 className="text-3xl md:text-4xl font-bold leading-tight text-text-primary">분석가와 팀을 위한 단순한 요금제</h1>
          <p className="text-text-secondary text-sm md:text-base">
            필요할 때 바로 업그레이드하고, 언제든지 다운그레이드할 수 있습니다.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-3">
          {PLANS.map((plan) => (
            <div
              key={plan.id}
              className={`relative flex flex-col rounded-2xl border p-6 shadow-card backdrop-blur-glass transition hover:-translate-y-1 hover:shadow-elevation-2 ${
                plan.tone === "primary"
                  ? "border-accent-amber/60 bg-gradient-to-b from-accent-amber/12 to-accent-amber/6"
                  : "border-border-hair/70 bg-surface-1/85"
              }`}
            >
              {plan.badge ? (
                <span className="absolute right-4 top-4 rounded-full bg-accent-amber/20 px-3 py-1 text-xs font-semibold text-text-primary">
                  {plan.badge}
                </span>
              ) : null}
              <div className="flex items-center gap-3">
                <div className="rounded-xl border border-border-hair/60 bg-surface-2/70 p-2">{ICONS[plan.id]}</div>
                <div>
                  <p className="text-lg font-semibold">{plan.name}</p>
                  <p className="text-xs text-text-secondary">{plan.subtitle}</p>
                </div>
              </div>

              <div className="mt-6">
                <p className="text-3xl font-bold">{plan.price}</p>
                <p className="text-xs text-text-muted">월 구독 · 언제든 해지 가능</p>
              </div>

              <div className="mt-5 space-y-2">
                <Link
                  href={plan.ctaHref}
                  className={`flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold transition ${
                    plan.tone === "primary"
                      ? "bg-accent-amber text-background-dark hover:bg-accent-amber/90"
                      : "bg-surface-2/90 text-text-primary hover:bg-surface-2"
                  }`}
                >
                  {plan.ctaLabel} <ArrowRight className="h-4 w-4" />
                </Link>
                {plan.ctaSecondary ? (
                  plan.ctaSecondary.external ? (
                    <a
                      href={plan.ctaSecondary.href}
                      className="flex items-center justify-center gap-2 rounded-xl border border-border-hair/70 px-4 py-3 text-xs font-semibold text-text-secondary transition hover:border-primary/60 hover:text-text-primary"
                    >
                      {plan.ctaSecondary.label}
                    </a>
                  ) : (
                    <Link
                      href={plan.ctaSecondary.href as Route}
                      className="flex items-center justify-center gap-2 rounded-xl border border-border-hair/70 px-4 py-3 text-xs font-semibold text-text-secondary transition hover:border-primary/60 hover:text-text-primary"
                    >
                      {plan.ctaSecondary.label}
                    </Link>
                  )
                ) : null}
              </div>

              <ul className="mt-6 space-y-3 text-sm text-text-secondary">
                {plan.features.map((feature, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="mt-1 inline-block h-1.5 w-1.5 rounded-full bg-accent-emerald" />
                    <span
                      className={`${feature.highlight ? "font-semibold text-text-primary" : ""}`}
                      title={feature.tooltip}
                    >
                      {feature.label}
                    </span>
                  </li>
                ))}
              </ul>

              <div className="mt-auto pt-6 text-[11px] text-text-muted">
                {plan.id === "pro"
                  ? "14일 무료 체험 후 매월 자동 결제됩니다."
                  : plan.id === "team"
                  ? "보안/통합 요건에 맞춰 커스텀 견적이 제공됩니다."
                  : "언제든 Pro로 업그레이드할 수 있습니다."}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
