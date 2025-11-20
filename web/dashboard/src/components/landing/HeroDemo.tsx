"use client";

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowDownToLine, FileSpreadsheet, Loader2 } from "lucide-react";

const DEMO_SCENARIO = {
  prompt: "H사 3분기 실적 요약하고, 경영권 분쟁 시점 주가 영향(CAR) 분석해줘",
  response: (
    <div className="space-y-3 text-sm leading-relaxed">
      <div className="flex items-start gap-2">
        <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-indigo-400" />
        <span className="text-slate-300">
          매출 <strong className="text-white">5,379억 원</strong>
          <span className="ml-1 text-xs font-semibold text-rose-400">(-1.8% YoY)</span>, 영업이익{" "}
          <strong className="text-white">727억 원</strong>
          <span className="ml-1 text-xs font-semibold text-rose-400">(-12.5% YoY)</span>.
        </span>
      </div>
      <div className="flex items-start gap-2">
        <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-indigo-400" />
        <span className="text-slate-300">
          분쟁 발생일(4/22) 후 <strong className="text-white">5일간 CAR</strong>
          <span className="ml-1 font-semibold text-rose-400">-12.4%</span> 기록. 동기간 엔터 3사 평균 대비{" "}
          <span className="font-semibold text-rose-300">-8.2%p</span> 추가 하락.
        </span>
      </div>
      <div className="flex items-start gap-2 text-xs text-slate-400">
        <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-indigo-400" />
        <span className="flex flex-wrap gap-2">
          <span className="rounded border border-slate-700 bg-slate-900/60 px-2 py-0.5">[1] 분기보고서 2024.05</span>
          <span className="rounded border border-slate-700 bg-slate-900/60 px-2 py-0.5">[2] 주요 뉴스 종합</span>
        </span>
      </div>
    </div>
  ),
};
const EXPORT_STATUS = ["Excel 내보내기 준비 중...", "Excel 파일 링크 생성됨."];

const CursorIcon = () => (
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M3 3L10.07 19.97L12.58 12.58L19.97 10.07L3 3Z" fill="#070B13" stroke="#F7F9FC" strokeWidth="2" />
  </svg>
);

type DemoStage = 0 | 1 | 2;

export function HeroDemo() {
  const [stage, setStage] = useState<DemoStage>(0);
  const [typed, setTyped] = useState("");
  const [exportPhase, setExportPhase] = useState(0);
  const [showToast, setShowToast] = useState(false);
  const [cursorHover, setCursorHover] = useState(false);

  useEffect(() => {
    const durations = [4600, 2800, 3800];
    const timer = setTimeout(() => {
      setStage((prev) => ((prev + 1) % 3) as DemoStage);
    }, durations[stage]);
    return () => clearTimeout(timer);
  }, [stage]);

  useEffect(() => {
    if (stage !== 0) {
      setTyped(DEMO_SCENARIO.prompt);
      return;
    }
    setTyped("");
    let index = 0;
    const interval = setInterval(() => {
      index += 1;
      setTyped(DEMO_SCENARIO.prompt.slice(0, index));
      if (index >= DEMO_SCENARIO.prompt.length) {
        clearInterval(interval);
      }
    }, 60);
    return () => clearInterval(interval);
  }, [stage]);

  useEffect(() => {
    if (stage !== 2) {
      setExportPhase(0);
      setShowToast(false);
      setCursorHover(false);
      return;
    }
    const phaseTimer = setTimeout(() => setExportPhase(1), 1200);
    const toastTimer = setTimeout(() => setShowToast(true), 2100);
    const hideTimer = setTimeout(() => setShowToast(false), 3300);
    const hoverTimer = setTimeout(() => setCursorHover(true), 1300);
    const hoverRelease = setTimeout(() => setCursorHover(false), 2600);
    return () => {
      clearTimeout(phaseTimer);
      clearTimeout(toastTimer);
      clearTimeout(hideTimer);
      clearTimeout(hoverTimer);
      clearTimeout(hoverRelease);
    };
  }, [stage]);

  const caretVisible = useMemo(() => {
    const targetLength = DEMO_SCENARIO.prompt.length;
    return stage === 0 && typed.length < targetLength ? "visible" : "hidden";
  }, [stage, typed]);

  return (
    <div className="relative rounded-[32px] border border-border-subtle bg-surface-muted/90 p-6 shadow-card">
      <AnimatePresence>
        {stage === 2 && (
          <motion.div
            key="cursor"
            initial={{ opacity: 0, x: 60, y: 80 }}
            animate={{
              opacity: 1,
              x: 250,
              y: 440,
              transition: { delay: 1.3, duration: 0.9, ease: "easeInOut" },
            }}
            exit={{ opacity: 0 }}
            className="pointer-events-none absolute z-50"
          >
            <motion.div
              animate={{ scale: exportPhase === 1 ? 0.82 : 1 }}
              transition={{ delay: 2, duration: 0.12 }}
            >
              <CursorIcon />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      <div className="rounded-2xl border border-border-subtle bg-background-cardDark p-4">
        <div className="mb-3 flex items-center justify-between text-xs uppercase tracking-[0.3em] text-text-secondaryDark">
          <span>Live demo</span>
          <span>{stage === 0 ? "Search" : stage === 1 ? "Analyze" : "Export"}</span>
        </div>
        <div className="space-y-4">
          <div className="flex items-start gap-3 rounded-2xl border border-border-subtle bg-surface p-4">
            <div className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-full bg-primary-muted font-semibold text-primary">U</div>
            <div className="flex-1">
              <div className="text-[11px] font-semibold uppercase tracking-[0.4em] text-text-secondaryDark">You</div>
              <p className="mt-1 text-base font-medium text-text-primaryDark">
                {typed}
                <span
                  className="ml-0.5 inline-block w-[2px] bg-primary animate-pulse"
                  style={{ visibility: caretVisible }}
                >
                  &nbsp;
                </span>
              </p>
            </div>
          </div>

          <motion.div
            className="flex items-start gap-3 rounded-2xl border border-border-subtle bg-surface p-4"
            animate={{ opacity: stage >= 1 ? 1 : 0.4, y: stage >= 1 ? 0 : 8 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
          >
            <div className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-full bg-white/10 font-semibold text-white">AI</div>
            <div className="flex-1">
              <div className="text-[11px] font-semibold uppercase tracking-[0.4em] text-text-secondaryDark">Analysis</div>
              <div className="mt-3 space-y-3 text-sm text-text-secondaryDark">
              <AnimatePresence mode="wait">
                {stage === 0 && (
                  <motion.div
                    key="placeholder"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 0.4 }}
                    exit={{ opacity: 0 }}
                    className="space-y-2"
                  >
                    {[1, 2, 3].map((line) => (
                      <div key={line} className="h-3 w-full rounded bg-border-subtle/40" />
                    ))}
                  </motion.div>
                )}
                {stage === 1 && (
                  <motion.div
                    key="skeleton"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="space-y-2"
                  >
                    {[1, 2, 3].map((line) => (
                      <div key={line} className="h-3 w-full animate-pulse rounded bg-border-subtle/60" />
                    ))}
                  </motion.div>
                )}
                {stage === 2 && (
                  <motion.div
                    key="summary"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    className="space-y-2"
                  >
                    {DEMO_SCENARIO.response}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
            </div>
          </motion.div>

          <motion.div
            className="rounded-2xl border border-border-subtle bg-surface p-4"
            animate={{ opacity: stage === 2 ? 1 : 0.45, y: stage === 2 ? 0 : 6 }}
            transition={{ duration: 0.5 }}
          >
            <p className="text-[11px] font-semibold uppercase tracking-[0.4em] text-text-secondaryDark">Export</p>
            <div className="mt-3 flex flex-col gap-3">
              <motion.button
                type="button"
                className="inline-flex items-center justify-center gap-2 rounded-full bg-primary/90 px-4 py-2 text-sm font-semibold text-white shadow-primary/30"
                animate={{
                  scale: exportPhase === 1 ? 0.94 : stage === 2 ? (cursorHover ? 1.03 : 1) : 0.98,
                  opacity: stage === 2 ? 1 : 0.7,
                  y: cursorHover ? -2 : 0,
                  boxShadow: cursorHover
                    ? "0 12px 30px rgba(59, 130, 246, 0.45)"
                    : "0 6px 20px rgba(59, 130, 246, 0.25)",
                }}
                transition={{ duration: 0.25 }}
              >
                <FileSpreadsheet className="h-4 w-4" />
                Excel 내보내기
              </motion.button>
              <div className="relative h-12 overflow-hidden rounded-xl border border-border-subtle bg-background-cardDark px-3 py-2 text-xs text-text-secondaryDark">
                <motion.div
                  key={exportPhase}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4 }}
                  className="absolute inset-0 flex items-center gap-2 px-3"
                >
                  {exportPhase === 0 ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                  ) : (
                    <ArrowDownToLine className="h-4 w-4 text-emerald-400" />
                  )}
                  <span className="text-sm text-text-primaryDark">{EXPORT_STATUS[exportPhase]}</span>
                </motion.div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
      <AnimatePresence>
        {showToast && (
          <motion.div
            key="toast"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            transition={{ duration: 0.25 }}
            className="pointer-events-none absolute bottom-4 left-1/2 w-60 -translate-x-1/2 rounded-2xl border border-border-subtle bg-background-cardDark/95 px-4 py-3 text-sm text-text-primaryDark shadow-subtle"
          >
            Excel 파일이 생성되었습니다.
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default HeroDemo;
