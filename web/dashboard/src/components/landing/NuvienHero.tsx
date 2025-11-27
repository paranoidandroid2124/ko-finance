"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const queryPresets = [
  {
    title: "H사",
    fullTitle: "H사 주가 이벤트 분석",
    desc: "경영권 분쟁과 주가 변동(CAR) 상관관계",
  },
  {
    title: "S사",
    fullTitle: "S사 최신 공시",
    desc: "3분기 사업보고서 핵심 지표 요약",
  },
  {
    title: "2차전지",
    fullTitle: "2차전지 섹터 리스크",
    desc: "미국 IRA 법안 변경에 따른 영향도",
  },
];

const NuvienLogo = ({ className = "w-8 h-8" }: { className?: string }) => (
  <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" className={className}>
    <defs>
      <linearGradient id="nuvienGradient" x1="0%" y1="100%" x2="100%" y2="0%">
        <stop offset="0%" stopColor="#3b82f6" />
        <stop offset="100%" stopColor="#06b6d4" />
      </linearGradient>
    </defs>
    <path
      d="M25 75 C 25 75, 25 45, 45 45 C 65 45, 60 75, 80 75 C 100 75, 100 25, 100 25"
      fill="none"
      stroke="url(#nuvienGradient)"
      strokeWidth="12"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

type ChipProps = {
  title: string;
  fullTitle: string;
  desc: string;
  onClick: (value: string) => void;
};

const Chip = ({ title, fullTitle, desc, onClick }: ChipProps) => (
  <button
    type="button"
    onClick={() => onClick(fullTitle)}
    className="group relative rounded-3xl border border-border-hair/60 bg-surface-1/80 p-6 text-left transition-all duration-300 hover:-translate-y-1 hover:border-primary/50 hover:bg-surface-1 hover:shadow-subtle"
  >
    <div className="mb-3 flex items-center gap-3">
      <div className="rounded-2xl bg-primary/15 px-3 py-1.5 text-xs text-primary transition-all group-hover:bg-primary group-hover:text-background-dark">
        ●
      </div>
      <span className="font-semibold text-text-secondary group-hover:text-text-primary">{title}…</span>
    </div>
    <p className="mb-1 text-sm font-medium text-text-primary">{fullTitle}</p>
    <p className="text-xs text-text-secondary">{desc}</p>
  </button>
);

export function NuvienHero() {
  const [inputValue, setInputValue] = useState(queryPresets[0].fullTitle);
  const router = useRouter();

  const handleSend = () => {
    const query = inputValue.trim();
    if (!query) {
      return;
    }
    const params = new URLSearchParams({ prefill: query, guest: "1" });
    router.push(`/dashboard?${params.toString()}`);
  };

  return (
    <section className="relative overflow-hidden bg-transparent text-white">
      <div className="pointer-events-none absolute -top-[20%] -left-[10%] h-[60%] w-[60%] rounded-full bg-accent-brand/20 blur-[150px]" />
      <div className="pointer-events-none absolute -bottom-[25%] right-[-5%] h-[70%] w-[70%] rounded-full bg-accent-glow/18 blur-[180px]" />

      <div className="relative z-10 mx-auto flex max-w-6xl flex-col gap-12 px-6 py-12 md:px-10">
        <header className="flex items-center justify-between">
          <div className="group flex cursor-pointer items-center gap-3">
            <div className="rounded-xl border border-border-hair/70 bg-surface-2/60 p-2 transition-colors group-hover:border-primary/60">
              <NuvienLogo className="h-6 w-6" />
            </div>
            <span className="bg-gradient-to-r from-text-primary to-text-secondary bg-clip-text text-xl font-bold tracking-tight text-transparent">
              Nuvien
            </span>
          </div>
          <div className="flex items-center gap-4 text-sm font-medium text-text-secondary">
            <span className="rounded-full border border-border-hair/60 bg-surface-2/60 px-3 py-1 text-xs text-primary">v1.0 Demo</span>
            <div className="rounded-full bg-gradient-to-tr from-primary to-accent-brand p-[1px]">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-canvas text-xs font-semibold text-text-primary">NV</div>
            </div>
          </div>
        </header>

        <div className="space-y-6 text-center">
          <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-primary/40 bg-primary/10 px-4 py-2 text-sm text-primary">
            <span className="text-xs">✦</span>
            <span>Modern Finance를 위한 AI Analyst</span>
          </div>
          <h1 className="text-4xl font-bold tracking-tight text-text-primary md:text-6xl">
            새로운 금융 흐름을
            <br />
            <span className="bg-gradient-to-r from-primary to-accent-brand bg-clip-text text-transparent">Nuvien에서 탐색하세요</span>
          </h1>
          <p className="mx-auto max-w-3xl text-base text-text-secondary md:text-lg">
            공시·뉴스·차트를 한 번에 묶어 질문하세요. Nuvien은 딥데이터와 자동 이벤트 스터디를 연결해, 다음 의사결정을 위한 길을 그려줍니다.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/dashboard"
              className="inline-flex items-center rounded-full bg-primary px-6 py-3 text-sm font-semibold text-background-dark shadow-glow-brand transition hover:-translate-y-[1px]"
            >
              채팅 시작하기
            </Link>
            <Link
              href="/dashboard?guest=1"
              className="inline-flex items-center rounded-full border border-border-hair/70 px-6 py-3 text-sm font-semibold text-text-primary transition hover:border-primary/60 hover:-translate-y-[1px]"
            >
              게스트 체험
            </Link>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {queryPresets.map((chip, idx) => (
            <div
              key={chip.fullTitle}
              className="transition-motion-medium"
              style={{ animation: `fadeUp 0.5s ease ${idx * 80}ms both` } as React.CSSProperties}
            >
              <Chip {...chip} onClick={setInputValue} />
            </div>
          ))}
        </div>

        <div className="relative mx-auto w-full max-w-3xl">
          <div className="absolute inset-0 rounded-full bg-gradient-to-r from-primary to-accent-glow blur opacity-20 transition-opacity duration-500" />
          <div className="relative flex items-center rounded-full border border-border-hair/70 bg-surface-2/90 p-2 pl-5 shadow-elevation-2 backdrop-blur-glass transition-motion-medium">
            <span className="mr-3 text-sm text-text-secondary">⌕</span>
            <input
              type="text"
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              placeholder="Nuvien에게 궁금한 것을 입력하세요..."
              className="h-12 flex-1 border-none bg-transparent text-base text-text-primary placeholder:text-text-muted focus:outline-none"
            />
            <button
              type="button"
              onClick={handleSend}
              className="mr-1 rounded-full bg-primary px-4 py-2 text-sm font-semibold text-background-dark transition-colors transition-motion-fast hover:bg-primary/90"
            >
              Send
            </button>
          </div>
          <p className="mt-4 text-center text-xs text-text-muted">Nuvien AI의 분석은 참고용이며 투자 조언이 아닙니다.</p>
        </div>
      </div>
    </section>
  );
}

// Inject fade-up keyframes once on the client
const ensureFadeUpKeyframes = () => {
  if (typeof document === "undefined") return;
  const existing = document.getElementById("nuvien-hero-fadeup");
  if (existing) return;
  const style = document.createElement("style");
  style.id = "nuvien-hero-fadeup";
  style.innerHTML = `
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
  }`;
  document.head.appendChild(style);
};

ensureFadeUpKeyframes();

export default NuvienHero;
