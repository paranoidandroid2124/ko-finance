"use client";

import { useState } from "react";

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
    className="group relative rounded-3xl border border-white/5 bg-white/5 p-6 text-left transition-all duration-300 hover:-translate-y-1 hover:border-blue-500/30 hover:bg-white/10 hover:shadow-lg hover:shadow-blue-500/10"
  >
    <div className="mb-3 flex items-center gap-3">
      <div className="rounded-2xl bg-blue-500/20 px-3 py-1.5 text-xs text-blue-300 transition-all group-hover:bg-blue-500 group-hover:text-white">
        ●
      </div>
      <span className="font-semibold text-slate-200 group-hover:text-white">{title}…</span>
    </div>
    <p className="mb-1 text-sm font-medium text-slate-200 group-hover:text-white">{fullTitle}</p>
    <p className="text-xs text-slate-500 group-hover:text-slate-400">{desc}</p>
  </button>
);

export function NuvienHero() {
  const [inputValue, setInputValue] = useState(queryPresets[0].fullTitle);

  return (
    <section className="relative overflow-hidden bg-[#050A18] text-white">
      <div className="pointer-events-none absolute -top-[20%] -left-[10%] h-[60%] w-[60%] rounded-full bg-blue-600/20 blur-[150px]" />
      <div className="pointer-events-none absolute -bottom-[25%] right-[-5%] h-[70%] w-[70%] rounded-full bg-cyan-500/15 blur-[180px]" />

      <div className="relative z-10 mx-auto flex max-w-6xl flex-col gap-12 px-6 py-12 md:px-10">
        <header className="flex items-center justify-between">
          <div className="group flex cursor-pointer items-center gap-3">
            <div className="rounded-xl border border-white/10 bg-white/5 p-2 transition-colors group-hover:border-blue-500/50">
              <NuvienLogo className="h-6 w-6" />
            </div>
            <span className="bg-gradient-to-r from-white to-slate-400 bg-clip-text text-xl font-bold tracking-tight text-transparent">
              Nuvien
            </span>
          </div>
          <div className="flex items-center gap-4 text-sm font-medium text-slate-400">
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-cyan-400">v1.0 Demo</span>
            <div className="rounded-full bg-gradient-to-tr from-blue-500 to-cyan-500 p-[1px]">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#050A18] text-xs font-semibold text-white">NV</div>
            </div>
          </div>
        </header>

        <div className="space-y-6 text-center">
          <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-blue-500/20 bg-blue-500/10 px-4 py-2 text-sm text-blue-300">
            <span className="text-xs">✦</span>
            <span>Modern Finance를 위한 AI Analyst</span>
          </div>
          <h1 className="text-4xl font-bold tracking-tight text-white md:text-6xl">
            새로운 금융 흐름을
            <br />
            <span className="bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">Nuvien에서 탐색하세요</span>
          </h1>
          <p className="mx-auto max-w-3xl text-base text-slate-400 md:text-lg">
            공시·뉴스·차트를 한 번에 묶어 질문하세요. Nuvien은 딥데이터와 자동 이벤트 스터디를 연결해, 다음 의사결정을 위한 길을 그려줍니다.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {queryPresets.map((chip) => (
            <Chip key={chip.fullTitle} {...chip} onClick={setInputValue} />
          ))}
        </div>

        <div className="relative mx-auto w-full max-w-3xl">
          <div className="absolute inset-0 rounded-full bg-gradient-to-r from-blue-500 to-cyan-500 blur opacity-20 transition-opacity duration-500" />
          <div className="relative flex items-center rounded-full border border-white/10 bg-[#101a2d]/90 p-2 pl-5 shadow-2xl backdrop-blur-xl">
            <span className="mr-3 text-sm text-slate-500">⌕</span>
            <input
              type="text"
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              placeholder="Nuvien에게 궁금한 것을 입력하세요..."
              className="h-12 flex-1 border-none bg-transparent text-base text-white placeholder:text-slate-500 focus:outline-none"
            />
            <button
              type="button"
              className="mr-1 rounded-full bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-blue-500"
            >
              Send
            </button>
          </div>
          <p className="mt-4 text-center text-xs text-slate-500">Nuvien AI의 분석은 참고용이며 투자 조언이 아닙니다.</p>
        </div>
      </div>
    </section>
  );
}

export default NuvienHero;
