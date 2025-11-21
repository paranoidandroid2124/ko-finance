"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "nuvien_onboarding_seen";

type StepId = "welcome" | "input" | "chart" | "export";

const PROMPT_PRESETS = [
  { label: "🍎 애플(AAPL) 실적 분석", value: "애플(AAPL) 최근 실적과 리스크를 분석해줘" },
  { label: "🇰🇷 삼성전자 전망", value: "삼성전자 향후 1년 전망과 경쟁사 대비 포지션 알려줘" },
  { label: "🚗 테슬라 vs 현대차", value: "테슬라와 현대차를 EV 지표 기준으로 비교해줘" },
];

type TargetRect = { top: number; left: number; width: number; height: number } | null;

export default function OnboardingGuide() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<StepId>("welcome");
  const [targetRect, setTargetRect] = useState<TargetRect>(null);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const hasSeen = localStorage.getItem(STORAGE_KEY);
    if (!hasSeen) {
      setOpen(true);
    }
  }, []);

  const focusElement = useCallback((selector: string) => {
    if (typeof window === "undefined") {
      return null;
    }
    const element = document.querySelector<HTMLElement>(selector);
    if (!element) {
      setTargetRect(null);
      return null;
    }
    const rect = element.getBoundingClientRect();
    setTargetRect({
      top: rect.top + window.scrollY,
      left: rect.left + window.scrollX,
      width: rect.width,
      height: rect.height,
    });
    return element;
  }, []);

  useEffect(() => {
    if (!open) return;
    if (step === "input") {
      focusElement('[data-onboarding-id="chat-input"]');
    } else if (step === "chart") {
      focusElement('[data-onboarding-id="report-chart"]');
    } else if (step === "export") {
      focusElement('[data-onboarding-id="export-report-button"]');
    } else {
      setTargetRect(null);
    }
  }, [open, step, focusElement]);

  const handleClose = useCallback(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, "true");
    }
    setOpen(false);
  }, []);

  const handlePrefill = (value: string) => {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("onboarding:prefill", { detail: { value } }));
    }
    setStep("input");
  };

  const tooltipContent = useMemo(() => {
    if (step === "input") {
      return {
        title: "여기에 궁금한 기업을 입력하세요",
        body: "프롬프트를 입력하고 Enter를 누르면 AI가 데이터를 수집합니다.",
      };
    }
    if (step === "chart") {
      return {
        title: "차트로 시각화된 인사이트",
        body: "주가 추이와 비교 지표가 자동으로 생성됩니다.",
      };
    }
    if (step === "export") {
      return {
        title: "PDF/Word로 즉시 내보내기",
        body: "완성된 리포트는 버튼 한 번으로 저장하고 공유할 수 있습니다.",
      };
    }
    return null;
  }, [step]);

  if (!open) {
    return null;
  }

  if (step === "welcome") {
    return (
      <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 backdrop-blur">
        <div className="w-full max-w-lg rounded-3xl bg-white p-8 text-center shadow-2xl dark:bg-slate-900">
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Nuvien에 오신 것을 환영합니다! 🎉</h2>
          <p className="mt-4 text-slate-600 dark:text-slate-300">
            AI와 함께하는 첫 번째 리포트를 만들어볼까요? 아래 예시를 눌러 바로 시작할 수 있습니다.
          </p>
          <div className="mt-6 flex flex-col gap-3">
            {PROMPT_PRESETS.map((preset) => (
              <button
                key={preset.value}
                type="button"
                onClick={() => handlePrefill(preset.value)}
                className="rounded-2xl bg-blue-50 px-4 py-3 text-left text-sm font-semibold text-blue-700 transition hover:bg-blue-100"
              >
                {preset.label}
                <span className="mt-1 block text-xs font-normal text-blue-500">{preset.value}</span>
              </button>
            ))}
          </div>
          <div className="mt-8 flex items-center justify-center gap-4 text-sm">
            <button
              type="button"
              onClick={() => setStep("input")}
              className="rounded-full bg-blue-600 px-5 py-2 font-semibold text-white shadow-lg shadow-blue-600/40"
            >
              튜토리얼 시작하기
            </button>
            <button type="button" onClick={handleClose} className="text-slate-400 hover:text-slate-600">
              다음에 하기
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="pointer-events-none fixed inset-0 z-[70]">
      <div className="absolute inset-0 bg-black/60 backdrop-blur" />
      {targetRect && tooltipContent ? (
        <>
          <div
            className="pointer-events-auto absolute rounded-2xl border-2 border-blue-400 bg-transparent shadow-[0_0_0_9999px_rgba(0,0,0,0.55)]"
            style={{
              top: targetRect.top - 8,
              left: targetRect.left - 8,
              width: targetRect.width + 16,
              height: targetRect.height + 16,
            }}
          />
          <div
            className="pointer-events-auto absolute max-w-xs rounded-2xl bg-white p-4 text-slate-900 shadow-xl dark:bg-slate-800 dark:text-white"
            style={{
              top: targetRect.top + targetRect.height + 16,
              left: Math.min(targetRect.left, window.innerWidth - 320),
            }}
          >
            <h3 className="text-base font-semibold">{tooltipContent.title}</h3>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{tooltipContent.body}</p>
            <div className="mt-4 flex items-center justify-end gap-3 text-sm">
              {step !== "export" && (
                <button
                  type="button"
                  onClick={() =>
                    setStep(step === "input" ? "chart" : step === "chart" ? "export" : "export")
                  }
                  className="text-slate-400 hover:text-slate-600"
                >
                  다음
                </button>
              )}
              <button
                type="button"
                onClick={handleClose}
                className="rounded-full bg-blue-600 px-4 py-1.5 text-white shadow-lg shadow-blue-600/40"
              >
                완료
              </button>
            </div>
          </div>
        </>
      ) : (
        <div className="pointer-events-auto absolute inset-0 flex items-center justify-center">
          <div className="max-w-md rounded-2xl bg-white p-6 text-center text-slate-800 shadow-2xl dark:bg-slate-900 dark:text-white">
            <h3 className="text-lg font-semibold">먼저 리포트를 생성해 주세요</h3>
            <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
              차트와 내보내기 버튼은 리포트가 생성된 후에 나타납니다. 프롬프트를 전송해보세요!
            </p>
            <button
              type="button"
              onClick={handleClose}
              className="mt-5 rounded-full bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow"
            >
              닫기
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
