"use client";

import { useEffect, useMemo, useState } from "react";
import { useTheme } from "next-themes";

import { useToastStore } from "@/store/toastStore";

const LANG_STORAGE_KEY = "nuvien-lang";
const LANGUAGE_OPTIONS = [
  { value: "ko", label: "한국어" },
  { value: "en", label: "English" },
];

export function GeneralSettingsPanel({ onClose }: { onClose?: () => void }) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [language, setLanguage] = useState<string>("ko");
  const pushToast = useToastStore((state) => state.show);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    const saved = typeof window !== "undefined" ? window.localStorage.getItem(LANG_STORAGE_KEY) : null;
    if (saved && LANGUAGE_OPTIONS.some((opt) => opt.value === saved)) {
      setLanguage(saved);
    }
  }, []);

  const applyLanguage = (value: string) => {
    setLanguage(value);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(LANG_STORAGE_KEY, value);
    }
    pushToast({
      id: `lang-${Date.now()}`,
      intent: "success",
      title: "언어 설정이 저장되었습니다.",
      message: "i18n은 순차 적용 예정입니다.",
    });
  };

  const themeValue = useMemo(() => (mounted ? theme ?? "system" : "system"), [mounted, theme]);

  const themeOptions: Array<{ value: string; label: string }> = [
    { value: "system", label: "시스템 설정 따름" },
    { value: "light", label: "라이트" },
    { value: "dark", label: "다크" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">일반</h3>
          <p className="text-sm text-text-secondary">테마와 언어를 설정합니다.</p>
        </div>
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-border-subtle px-3 py-1 text-xs text-text-secondary transition hover:border-text-secondary hover:text-text-primary"
          >
            닫기
          </button>
        ) : null}
      </div>

      <div className="space-y-4 rounded-2xl border border-border-subtle bg-surface-2/50 p-4 shadow-lg">
        <p className="text-sm font-semibold text-text-primary">테마</p>
        <div className="grid gap-2 md:grid-cols-3">
          {themeOptions.map((option) => {
            const active = themeValue === option.value;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => setTheme(option.value)}
                className={`flex items-center justify-between rounded-xl border px-3 py-2 text-sm transition ${active
                    ? "border-primary bg-primary/10 text-primary shadow-sm"
                    : "border-border-subtle text-text-secondary hover:border-text-muted"
                  }`}
              >
                <span>{option.label}</span>
                {active ? <span className="text-[11px] text-primary font-medium">선택됨</span> : null}
              </button>
            );
          })}
        </div>
      </div>

      <div className="space-y-3 rounded-2xl border border-border-subtle bg-surface-2/50 p-4 shadow-lg">
        <p className="text-sm font-semibold text-text-primary">언어</p>
        <div className="flex flex-wrap gap-2">
          {LANGUAGE_OPTIONS.map((opt) => {
            const active = language === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => applyLanguage(opt.value)}
                className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${active ? "border-primary bg-primary/10 text-primary" : "border-border-subtle text-text-secondary hover:border-text-muted"
                  }`}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
        <p className="text-[11px] text-text-muted">UI 언어는 순차 적용 예정이며, 선택값은 저장됩니다.</p>
      </div>
    </div>
  );
}
