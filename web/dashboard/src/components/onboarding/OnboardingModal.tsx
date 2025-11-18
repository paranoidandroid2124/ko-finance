"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import type { Route } from "next";
import { CheckCircle2, Sparkles, X } from "lucide-react";

import { useOnboardingStore } from "@/store/onboardingStore";

export function OnboardingModal() {
  const router = useRouter();
  const pathname = usePathname();
  const needsOnboarding = useOnboardingStore((state) => state.needsOnboarding);
  const dismissed = useOnboardingStore((state) => state.dismissed);
  const content = useOnboardingStore((state) => state.content);
  const loading = useOnboardingStore((state) => state.loading);
  const fetchContent = useOnboardingStore((state) => state.fetchContent);
  const markDismissed = useOnboardingStore((state) => state.markDismissed);

  useEffect(() => {
    if (needsOnboarding && !content && !loading) {
      void fetchContent();
    }
  }, [needsOnboarding, content, fetchContent, loading]);

  const handleStartWizard = () => {
    router.push("/onboarding" as Route);
    markDismissed();
  };

  if (!needsOnboarding || dismissed || pathname?.startsWith("/onboarding")) {
    return null;
  }

  const hero = content?.hero;
  const sampleBoard = content?.sampleBoard;
  const checklist = content?.checklist ?? [];

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/70 px-4 py-6 backdrop-blur-sm">
      <div className="relative flex w-full max-w-5xl flex-col gap-6 rounded-2xl border border-white/10 bg-slate-900/95 p-6 text-white shadow-2xl">
        <button
          type="button"
          className="absolute right-4 top-4 text-white/70 transition hover:text-white"
          onClick={markDismissed}
          aria-label="튜토리얼 닫기"
        >
          <X className="h-5 w-5" />
        </button>
        <div className="flex flex-col gap-4 md:flex-row">
          <div className="flex-1 space-y-3">
            <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-300">
              <Sparkles className="h-4 w-4 text-amber-300" aria-hidden />
              Onboarding · 3분 루틴
            </p>
            <h2 className="text-2xl font-bold leading-snug text-white">{hero?.title ?? "K-Finance 온보딩"}</h2>
            <p className="text-base text-slate-300">{hero?.subtitle}</p>
            <ul className="space-y-2 text-sm text-slate-200">
              {(hero?.highlights ?? []).map((item) => (
                <li key={item} className="flex items-start gap-2">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-300" aria-hidden />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="flex-1 rounded-xl border border-white/10 bg-white/5 p-4">
            <p className="text-xs uppercase tracking-wide text-blue-200">체크리스트</p>
            <ul className="mt-3 space-y-3">
              {checklist.map((item) => (
                <li key={item.id} className="rounded-lg border border-white/10 bg-white/5 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">{item.title}</p>
                      <p className="text-xs text-slate-300">{item.description}</p>
                    </div>
                    {item.cta ? (
                      <a
                        href={item.cta.href}
                        className="rounded-md border border-white/20 px-3 py-1 text-xs font-semibold text-white transition hover:border-white"
                      >
                        {item.cta.label}
                      </a>
                    ) : null}
                  </div>
                  {item.tips.length ? (
                    <ul className="mt-2 space-y-1 text-[11px] text-slate-300">
                      {item.tips.map((tip) => (
                        <li key={tip}>• {tip}</li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        </div>
        <div className="rounded-xl border border-white/10 bg-slate-950/40 p-4">
          <p className="text-sm font-semibold text-white">{sampleBoard?.title ?? "샘플 워크보드"}</p>
          <div className="mt-3 grid gap-4 md:grid-cols-3">
            {(sampleBoard?.sections ?? []).map((section) => (
              <div key={section.id} className="flex flex-col rounded-lg border border-white/10 bg-white/5 p-3">
                <p className="text-sm font-semibold text-white">{section.title}</p>
                <div className="mt-2 space-y-2 text-xs text-slate-200">
                  {section.items.slice(0, 3).map((item, index) => (
                    <div key={`${section.id}-${index}`} className="rounded-md bg-slate-900/60 p-2">
                      {"headline" in item ? <p className="font-semibold">{String(item.headline)}</p> : null}
                      {"summary" in item ? <p className="text-[11px] text-slate-300">{String(item.summary)}</p> : null}
                      {"question" in item ? (
                        <p className="text-[11px] text-slate-300">{String(item.question)}</p>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-xs text-slate-300">샘플을 확인한 뒤에도 언제든지 좌측 사이드바에서 다시 열 수 있어요.</div>
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded-lg border border-white/30 px-4 py-2 text-sm font-semibold text-white transition hover:border-white"
              onClick={markDismissed}
            >
              나중에 보기
            </button>
            <button
              type="button"
              className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-slate-900 transition hover:bg-slate-100"
              onClick={handleStartWizard}
              disabled={!content}
            >
              온보딩 페이지 열기
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
