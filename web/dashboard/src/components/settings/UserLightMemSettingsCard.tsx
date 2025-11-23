"use client";

import { useCallback, useMemo } from "react";
import { AlertCircle, Loader2, Shield } from "lucide-react";

import { useUserLightMemSettings, useSaveUserLightMemSettings } from "@/hooks/useUserLightMemSettings";
import { type LightMemSettingsPayload } from "@/lib/userSettingsApi";
import { usePlanStore } from "@/store/planStore";
import { useToastStore } from "@/store/toastStore";

type ToggleProps = {
  label: string;
  helper: string;
  checked: boolean;
  disabled?: boolean;
  ariaLabel?: string;
  onChange: (next: boolean) => void;
};

const ToggleRow = ({ label, helper, checked, disabled, ariaLabel, onChange }: ToggleProps) => (
  <div className="flex items-center justify-between gap-3 rounded-lg border border-border-light bg-background-base p-4 dark:border-border-dark dark:bg-background-baseDark">
    <div className="min-w-0">
      <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">{label}</p>
      <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{helper}</p>
    </div>
    <label className="relative inline-flex cursor-pointer items-center">
      <input
        type="checkbox"
        className="peer sr-only"
        checked={checked}
        disabled={disabled}
        aria-label={ariaLabel ?? label}
        onChange={(event) => onChange(event.target.checked)}
      />
      <div className="peer h-6 w-11 rounded-full bg-slate-300 after:absolute after:left-[4px] after:top-[4px] after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all peer-checked:bg-primary peer-checked:after:translate-x-5 peer-disabled:cursor-not-allowed peer-disabled:opacity-50 dark:bg-slate-600 dark:peer-checked:bg-primary.dark" />
    </label>
  </div>
);

const UserLightMemSettingsCard = () => {
  const { memoryFlags } = usePlanStore((state) => ({ memoryFlags: state.memoryFlags }));
  const toast = useToastStore((state) => state.show);
  const { data, isLoading, isError, refetch } = useUserLightMemSettings();
  const saveMutation = useSaveUserLightMemSettings();

  const planAllowsChat = Boolean(memoryFlags.chat);
  const planAllowsAny = planAllowsChat;

  const settings = data?.lightmem;

  const busy = isLoading || saveMutation.isPending;

  const updateSettings = useCallback(
    (next: Partial<LightMemSettingsPayload>) => {
      if (!settings) return;
      const payload: LightMemSettingsPayload = { ...settings, ...next };
      saveMutation.mutate(payload, {
        onError: (error) => {
          toast({
            id: `lightmem-save-${Date.now()}`,
            intent: "error",
            title: "LightMem 설정을 저장하지 못했어요",
            message: error instanceof Error ? error.message : undefined,
          });
        },
      });
    },
    [saveMutation, settings, toast],
  );

  const planBlockedMessage = useMemo(() => {
    if (planAllowsAny) return null;
    return "현재 플랜에서는 LightMem 개인화를 사용할 수 없어요. 업그레이드 후 다시 시도해주세요.";
  }, [planAllowsAny]);

  const loadingState = (
    <div className="flex items-center gap-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
      <Loader2 className="h-4 w-4 animate-spin" />
      <span>설정을 불러오는 중…</span>
    </div>
  );

  const errorState = (
    <div className="flex items-start gap-2 rounded-lg border border-amber-300/60 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-300/30 dark:bg-amber-500/10 dark:text-amber-100">
      <AlertCircle className="h-4 w-4 shrink-0" />
      <div className="flex-1">
        <p className="font-semibold">LightMem 설정을 불러오지 못했어요</p>
        <button
          type="button"
          onClick={() => refetch()}
          className="mt-1 text-xs font-semibold text-primary underline-offset-2 hover:underline dark:text-primary.dark"
        >
          다시 시도
        </button>
      </div>
    </div>
  );

  return (
    <section className="rounded-xl border border-border-light bg-background-base p-5 shadow-sm dark:border-border-dark dark:bg-background-baseDark">
      <header className="mb-4 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-primary dark:text-primary.dark">LightMem</p>
          <h3 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">개인화 제어</h3>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            Chat 답변에 과거 맥락을 주입할지 선택하세요.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-border-light px-3 py-1.5 text-[11px] font-semibold text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
          <Shield className="h-4 w-4" aria-hidden />
          <span>기억 렌즈</span>
        </div>
      </header>

      {isLoading ? loadingState : null}
      {isError ? errorState : null}
      {!isLoading && !isError && settings ? (
        <div className="space-y-3">
          <ToggleRow
            label="LightMem 활성화"
            helper="개인 맞춤 기억을 전체적으로 켜거나 끕니다."
            checked={settings.enabled}
            disabled={busy || !planAllowsAny}
            onChange={(next) =>
              updateSettings({
                enabled: next,
                chat: next ? settings.chat : settings.chat,
              })
            }
          />
          <ToggleRow
            label="Chat 세션 메모리"
            helper="챗봇 답변에 직전 대화와 장기 기억을 연결합니다."
            checked={settings.chat}
            disabled={busy || !settings.enabled || !planAllowsChat}
            onChange={(next) => updateSettings({ chat: next })}
          />

          {planBlockedMessage ? (
            <div className="flex items-start gap-2 rounded-lg border border-dashed border-border-light bg-background-base px-3 py-3 text-xs text-text-secondaryLight dark:border-border-dark dark:bg-background-baseDark dark:text-text-secondaryDark">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" aria-hidden />
              <div>{planBlockedMessage}</div>
            </div>
          ) : null}
          {saveMutation.isError ? (
            <div className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-3 text-xs text-rose-800 dark:border-rose-300/40 dark:bg-rose-500/10 dark:text-rose-100">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <div>LightMem 설정 저장 중 오류가 발생했습니다. 다시 시도해 주세요.</div>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
};

export default UserLightMemSettingsCard;
export { UserLightMemSettingsCard };
