"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import clsx from "classnames";

import { useUserLightMemSettings, useSaveUserLightMemSettings } from "@/hooks/useUserLightMemSettings";
import type { LightMemSettingsPayload } from "@/lib/userSettingsApi";

const DEFAULT_SETTINGS: LightMemSettingsPayload = {
  enabled: false,
  watchlist: true,
  digest: true,
  chat: true,
};

const SECONDARY_OPTIONS: Array<{ key: keyof LightMemSettingsPayload; label: string }> = [
  { key: "watchlist", label: "워치리스트" },
  { key: "digest", label: "다이제스트" },
  { key: "chat", label: "Chat" },
];

export function UserLightMemSettingsCard() {
  const { data, isLoading, isFetching, error } = useUserLightMemSettings();
  const { mutateAsync, isPending } = useSaveUserLightMemSettings();
  const [form, setForm] = useState<LightMemSettingsPayload>(DEFAULT_SETTINGS);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (!data?.lightmem) {
      return;
    }
    setForm(data.lightmem);
    setDirty(false);
  }, [data]);

  const handleToggle =
    (field: keyof LightMemSettingsPayload) => (event: FormEvent<HTMLInputElement>) => {
      const checked = event.currentTarget.checked;
      setForm((prev) => {
        const next = { ...prev, [field]: checked };
        return next;
      });
      setDirty(true);
    };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await mutateAsync(form);
    setDirty(false);
  };

  const handleReset = () => {
    if (data?.lightmem) {
      setForm(data.lightmem);
      setDirty(false);
    } else {
      setForm(DEFAULT_SETTINGS);
      setDirty(false);
    }
  };

  const lastUpdatedLabel = useMemo(() => {
    if (!data?.updatedAt) {
      return "아직 저장된 기록이 없어요";
    }
    try {
      return new Intl.DateTimeFormat("ko-KR", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date(data.updatedAt));
    } catch {
      return data.updatedAt;
    }
  }, [data?.updatedAt]);

  const isBusy = isPending || isLoading;
  const secondaryDisabled = !form.enabled || isBusy;

  return (
    <section className="rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <header className="flex flex-col gap-1">
        <h2 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">LightMem 개인정보 보호</h2>
        <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          Watchlist·다이제스트·Chat에서 LightMem 개인화를 사용할지, 어떤 표면에 허용할지 선택할 수 있어요.
        </p>
      </header>

      {error ? (
        <p className="mt-4 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-200">
          {error.message.includes("user_required")
            ? "사용자 식별자가 없어 설정을 저장할 수 없어요. LIGHTMEM_DEFAULT_USER_ID 환경변수를 확인해 주세요."
            : error.message}
        </p>
      ) : null}

      <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
        <label className="flex items-center justify-between rounded-lg border border-border-light bg-white/60 p-3 text-sm font-medium text-text-primaryLight transition dark:border-border-dark dark:bg-background-base dark:text-text-primaryDark">
          <span>LightMem 전체 허용</span>
          <input
            type="checkbox"
            className="h-4 w-4 accent-primary"
            checked={form.enabled}
            disabled={isBusy}
            onChange={handleToggle("enabled")}
          />
        </label>

        <div className="grid gap-3 sm:grid-cols-3">
          {SECONDARY_OPTIONS.map((option) => (
            <label
              key={option.key}
              className={clsx(
                "flex items-center justify-between rounded-lg border px-3 py-2 text-sm",
                form[option.key]
                  ? "border-primary bg-primary/5 text-primary dark:border-primary dark:bg-primary/15"
                  : "border-border-light text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark",
                secondaryDisabled ? "opacity-60" : "transition hover:border-primary/70",
              )}
            >
              <span>{option.label}</span>
              <input
                type="checkbox"
                className="h-4 w-4 accent-primary"
                checked={form[option.key]}
                onChange={handleToggle(option.key)}
                disabled={secondaryDisabled}
              />
            </label>
          ))}
        </div>

        <div className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
          마지막 업데이트: <span className="font-semibold">{lastUpdatedLabel}</span>
        </div>

        <div className="flex flex-wrap gap-3">
          <button
            type="submit"
            className="inline-flex items-center rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-white shadow focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:opacity-70 dark:bg-primary.dark"
            disabled={isBusy || !dirty}
          >
            {isPending ? "저장 중..." : "개인화 설정 저장"}
          </button>
          <button
            type="button"
            onClick={handleReset}
            className="inline-flex items-center rounded-lg border border-border-light px-4 py-2 text-xs font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary disabled:opacity-60 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
            disabled={isBusy || (!dirty && !isFetching)}
          >
            변경 취소
          </button>
        </div>
      </form>
    </section>
  );
}
