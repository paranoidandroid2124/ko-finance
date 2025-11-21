"use client";

import Link from "next/link";
import { useState } from "react";
import { motion } from "framer-motion";
import { BarChart2, Brain, Zap, FileSpreadsheet } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { HeroDemo } from "@/components/landing/HeroDemo";
import { NuvienHero } from "@/components/landing/NuvienHero";
import { TermDefinition } from "@/components/ui/TermDefinition";

type FeaturePreviewType = "extract" | "chart" | "export";

type FeatureItem = {
  id: string;
  icon: LucideIcon;
  title: string;
  description: string;
  preview: FeaturePreviewType;
};

const features: FeatureItem[] = [
  {
    id: "extract",
    icon: Zap,
    title: "공시·뉴스 핵심 수치 추출",
    description: "KRX·NASDAQ 공시 PDF와 주요 뉴스에서 재무 지표와 가이던스 문장을 자동으로 구조화합니다.",
    preview: "extract",
  },
  {
    id: "chart",
    icon: BarChart2,
    title: "표준화된 차트와 비교 지표",
    description: "주가 추이, 동종업계 대비 수익성, 이벤트 이후 CAR 등을 동일한 포맷으로 제공합니다.",
    preview: "chart",
  },
  {
    id: "export",
    icon: Brain,
    title: "자동화된 리서치 메모",
    description: "요약 본문, 표, 인용 출처가 포함된 투자 메모를 바로 PDF·Word·Excel로 내보낼 수 있습니다.",
    preview: "export",
  },
];

const steps = [
  { title: "1. 질문 입력", detail: "분석하려는 티커나 이슈를 입력합니다. 예: “삼성전자 2023 실적 핵심 지표.”" },
  { title: "2. 데이터 처리", detail: "최근 공시, 뉴스, 가격 데이터를 불러와 표와 차트로 정리합니다." },
  { title: "3. 리포트 생성", detail: "본문·표·출처 링크가 포함된 리포트를 편집하거나 바로 내보냅니다." },
];

const logos = ["openai", "python", "nasdaq", "krx"];

function FeatureCard({ icon: Icon, title, description, preview }: FeatureItem) {
  const [hovered, setHovered] = useState(false);
  return (
    <motion.div
      onHoverStart={() => setHovered(true)}
      onHoverEnd={() => setHovered(false)}
      whileHover={{ y: -6 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="rounded-2xl border border-border-subtle bg-surface-muted/80 p-5 shadow-subtle"
    >
      <div className="flex items-center gap-3">
        <span className="rounded-full bg-primary-muted px-3 py-2">
          <Icon className="h-5 w-5 text-primary" />
        </span>
        <h3 className="text-lg font-semibold text-white">{title}</h3>
      </div>
      <p className="mt-3 text-sm text-text-secondaryDark">{description}</p>
      <FeaturePreview type={preview} active={hovered} />
    </motion.div>
  );
}

function FeaturePreview({ type, active }: { type: FeaturePreviewType; active: boolean }) {
  if (type === "extract") {
    const rows = [
      { label: "매출", value: "₩6,493억 (+12%)" },
      { label: "영업이익", value: "₩453억 (+9%)" },
      { label: "지분변동", value: "-1.2% (기관)" },
    ];
    return (
      <div className="mt-5 rounded-2xl border border-border-subtle bg-background-cardDark p-3">
        {rows.map((row, index) => (
          <motion.div
            key={row.label}
            className="flex items-center justify-between text-xs text-text-secondaryDark"
            animate={{ x: active ? 0 : -6, opacity: active ? 1 : 0.6 }}
            transition={{ duration: 0.35, delay: active ? index * 0.05 : 0 }}
          >
            <span>{row.label}</span>
            <span className="font-semibold text-text-primaryDark">{row.value}</span>
          </motion.div>
        ))}
      </div>
    );
  }

  if (type === "chart") {
    const pathD = "M5 50 L25 30 L45 38 L65 20 L85 32 L105 18";
    return (
      <div className="mt-5 rounded-2xl border border-border-subtle bg-background-cardDark/80 p-4">
        <svg viewBox="0 0 110 60" className="h-28 w-full">
          <line x1="0" y1="50" x2="110" y2="50" stroke="rgba(148,163,184,0.25)" strokeWidth="1" />
          <line x1="0" y1="30" x2="110" y2="30" stroke="rgba(148,163,184,0.15)" strokeWidth="1" />
          <motion.path
            d={pathD}
            fill="none"
            stroke="#60A5FA"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0.25 }}
            animate={{ pathLength: active ? 1 : 0.4 }}
            transition={{ duration: 1.1, ease: "easeInOut" }}
          />
        </svg>
        <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
          <div className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-white">
            <p className="text-xs font-semibold text-white/80">AAPL vs Peer</p>
            <p className="text-sm font-semibold text-emerald-300">+4.7% vs +2.1%</p>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-white">
            <p className="text-xs font-semibold text-white/80">CAR (5일)</p>
            <p className="text-sm font-semibold text-rose-300">-3.2% vs 시장 -0.8%</p>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-3">
          <TermDefinition term="AAPL" description="Apple Inc.의 나스닥 상장 티커입니다." />
          <TermDefinition term="Peer" description="동종 업계 대표 기업들의 평균치입니다." />
          <TermDefinition term="CAR" description="Cumulative Abnormal Return, 이벤트 이후 누적 초과 수익률입니다." />
        </div>
      </div>
    );
  }

  return (
    <div className="mt-5 rounded-2xl border border-border-subtle bg-background-cardDark/90 p-4 text-sm text-text-secondaryDark">
      <div className="flex items-center justify-between text-xs uppercase tracking-[0.2em] text-text-secondaryDark">
        <span>Export</span>
        <motion.div animate={{ y: active ? 6 : 0 }} transition={{ duration: 0.4, ease: "easeOut" }}>
          <FileSpreadsheet className="h-5 w-5 text-emerald-400" />
        </motion.div>
      </div>
      <motion.button
        type="button"
        className="mt-3 inline-flex items-center gap-2 rounded-full bg-primary/90 px-4 py-2 text-xs font-semibold text-white"
        animate={{ scale: active ? 1 : 0.98, boxShadow: active ? "0 8px 25px rgba(59,130,246,0.35)" : "none" }}
        transition={{ duration: 0.3 }}
      >
        Excel 내보내기
      </motion.button>
      <p className="mt-3 text-xs">
        {active ? "Excel 파일 링크가 생성되었습니다." : "내보내기 버튼을 누르면 Excel 파일을 만듭니다."}
      </p>
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <NuvienHero />
      <main className="mx-auto flex w-full max-w-6xl flex-col gap-16 px-6 py-16">
        <section className="rounded-[32px] border border-border-subtle bg-surface-muted/80 p-4 shadow-card">
          <HeroDemo />
        </section>

        <section className="space-y-6">
          <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Trusted Tech</p>
          <div className="flex flex-wrap items-center gap-6 text-slate-400">
            {logos.map((logo) => (
              <span key={logo} className="text-sm uppercase tracking-wide text-slate-500">
                {logo}
              </span>
            ))}
          </div>
        </section>

        <section className="space-y-8">
          <div>
            <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Capabilities</p>
            <h2 className="mt-2 text-3xl font-semibold">반복적인 리서치 작업을 정리합니다</h2>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            {features.map((feature) => (
              <FeatureCard key={feature.id} {...feature} />
            ))}
          </div>
        </section>

        <section className="space-y-8">
          <div>
            <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Workflow</p>
            <h2 className="mt-2 text-3xl font-semibold">문제 제기부터 리포트까지</h2>
          </div>
          <div className="grid gap-5 md:grid-cols-3">
            {steps.map(({ title, detail }) => (
              <div key={title} className="rounded-2xl border border-white/10 bg-slate-900/70 p-6">
                <span className="text-sm font-semibold uppercase tracking-[0.3em] text-blue-300">{title}</span>
                <p className="mt-2 text-sm text-slate-300">{detail}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="space-y-4 rounded-3xl border border-white/10 bg-gradient-to-br from-blue-600/30 to-slate-900/80 p-8 text-center">
          <p className="text-sm uppercase tracking-[0.4em] text-blue-200">Start today</p>
          <h2 className="text-3xl font-semibold text-white">지금 바로 사용해 보세요.</h2>
          <p className="text-slate-200">생성된 리포트는 참고용 자료이며, 모든 투자 판단과 책임은 이용자에게 있습니다.</p>
          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/chat?guest=1"
              className="inline-flex items-center rounded-full bg-white px-6 py-3 text-sm font-semibold text-slate-900 shadow-lg shadow-white/30"
            >
              무료 체험 시작
            </Link>
            <Link
              href="/pricing"
              className="inline-flex items-center rounded-full border border-white/30 px-6 py-3 text-sm font-semibold text-white transition hover:border-white/70"
            >
              요금제 살펴보기
            </Link>
          </div>
        </section>

        <footer className="flex flex-col gap-4 border-t border-white/10 pt-8 text-sm text-slate-500 md:flex-row md:items-center md:justify-between">
          <div>© 2025 Nuvien. All rights reserved.</div>
          <div className="flex flex-wrap items-center gap-4 text-xs uppercase tracking-wide">
            <Link href="/legal/terms" className="hover:text-white">
              이용약관
            </Link>
            <Link href="/legal/privacy" className="hover:text-white">
              개인정보처리방침
            </Link>
            <Link href="mailto:hello@nuvien.com" className="hover:text-white">
              문의하기
            </Link>
          </div>
        </footer>
      </main>
    </div>
  );
}
