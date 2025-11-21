"use client";

import { useEffect, useMemo, useState } from "react";
import { Check } from "lucide-react";

import { fetchWithAuth } from "@/lib/fetchWithAuth";
import { useToastStore } from "@/store/toastStore";

type ProactiveSettings = {
  enabled: boolean;
  channels: {
    widget: boolean;
    email: {
      enabled: boolean;
      schedule: "morning" | "evening";
    };
    slack?: boolean;
  };
};

const DEFAULT_SETTINGS: ProactiveSettings = {
  enabled: false,
  channels: {
    widget: true,
    email: { enabled: false, schedule: "morning" },
    slack: false,
  },
};

export function ProactiveSettingsPanel({ onClose }: { onClose?: () => void }) {
  const pushToast = useToastStore((state) => state.show);
  const [settings, setSettings] = useState<ProactiveSettings>(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const channels = useMemo(() => settings.channels, [settings.channels]);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      try {
        const res = await fetchWithAuth("/api/v1/profile/proactive");
        if (!res.ok) {
          throw new Error(`failed ${res.status}`);
        }
        const data = (await res.json()) as Partial<ProactiveSettings>;
        if (cancelled) return;
        setSettings({
          enabled: data.enabled ?? DEFAULT_SETTINGS.enabled,
          channels: {
            widget: data.channels?.widget ?? DEFAULT_SETTINGS.channels.widget,
            email: {
              enabled: data.channels?.email?.enabled ?? DEFAULT_SETTINGS.channels.email.enabled,
              schedule: data.channels?.email?.schedule ?? DEFAULT_SETTINGS.channels.email.schedule,
            },
            slack: data.channels?.slack ?? DEFAULT_SETTINGS.channels.slack,
          },
        });
      } catch (error) {
        if (!cancelled) {
          pushToast({
            id: `proactive/load/${Date.now()}`,
            intent: "error",
            title: "프로액티브 설정을 불러오지 못했습니다.",
            message: error instanceof Error ? error.message : undefined,
          });
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [pushToast]);

  const patchSettings = async (next: ProactiveSettings) => {
    setSaving(true);
    const prev = settings;
    setSettings(next);
    try {
      const res = await fetchWithAuth("/api/v1/profile/proactive", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(next),
      });
      if (!res.ok) {
        throw new Error(`failed ${res.status}`);
      }
    } catch (error) {
      setSettings(prev);
      pushToast({
        id: `proactive/save/${Date.now()}`,
        intent: "error",
        title: "저장 실패",
        message: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setSaving(false);
    };
  };

  const toggleEnabled = (value: boolean) => patchSettings({ ...settings, enabled: value });
  const toggleWidget = (value: boolean) => patchSettings({ ...settings, channels: { ...channels, widget: value } });
  const toggleEmail = (value: boolean) =>
    patchSettings({ ...settings, channels: { ...channels, email: { ...channels.email, enabled: value } } });
  const setEmailSchedule = (schedule: "morning" | "evening") =>
    patchSettings({ ...settings, channels: { ...channels, email: { ...channels.email, schedule } } });

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-white">프로액티브 인사이트</h3>
          <p className="text-sm text-slate-400">새 공시/뉴스를 관심사 기반으로 먼저 알려줍니다.</p>
        </div>
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300 transition hover:border-white/30 hover:text-white"
          >
            닫기
          </button>
        ) : null}
      </div>

      <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 shadow-lg">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-white">전체 활성화</p>
            <p className="text-xs text-slate-400">관심 키워드에 대한 알림을 받습니다.</p>
          </div>
          <label className="relative inline-flex cursor-pointer items-center">
            <input
              type="checkbox"
              className="peer sr-only"
              checked={settings.enabled}
              disabled={loading || saving}
              onChange={(event) => toggleEnabled(event.target.checked)}
            />
            <div className="peer h-6 w-11 rounded-full bg-slate-600 after:absolute after:left-[4px] after:top-[4px] after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all peer-checked:bg-blue-500 peer-checked:after:translate-x-5 peer-disabled:opacity-60" />
          </label>
        </div>
      </div>

      <div className="space-y-4 rounded-2xl border border-white/10 bg-white/[0.04] p-4 shadow-lg">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-white">수신 채널</p>
            <p className="text-xs text-slate-400">어디로 받을지 선택하세요.</p>
          </div>
        </div>
        <div className="space-y-3">
          <ChannelToggle
            label="대시보드 위젯"
            description="로그인 시 인사이트 카드로 표시합니다."
            checked={channels.widget}
            disabled={!settings.enabled || saving}
            onChange={toggleWidget}
          />
          <div className="rounded-xl border border-white/10 bg-black/10 p-3">
            <ChannelToggle
              label="이메일 다이제스트"
              description="관심 키워드 기반 요약을 이메일로 수신합니다."
              checked={channels.email.enabled}
              disabled={!settings.enabled || saving}
              onChange={toggleEmail}
            />
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              {(["morning", "evening"] as const).map((slot) => {
                const active = channels.email.schedule === slot;
                return (
                  <button
                    key={slot}
                    type="button"
                    disabled={!settings.enabled || !channels.email.enabled || saving}
                    onClick={() => setEmailSchedule(slot)}
                    className={`rounded-full border px-3 py-1 font-semibold transition ${
                      active ? "border-blue-400 bg-blue-500/20 text-white" : "border-white/10 text-slate-300 hover:border-white/30"
                    } disabled:opacity-50`}
                  >
                    {slot === "morning" ? "아침" : "저녁"} 전달
                  </button>
                );
              })}
            </div>
          </div>
          <ChannelToggle
            label="Slack (준비 중)"
            description="팀 슬랙 채널로 전달 (예정)."
            checked={Boolean(channels.slack)}
            disabled
            onChange={() => {}}
            badge="coming soon"
          />
        </div>
      </div>
    </div>
  );
}

type ChannelToggleProps = {
  label: string;
  description: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (value: boolean) => void;
  badge?: string;
};

function ChannelToggle({ label, description, checked, disabled, onChange, badge }: ChannelToggleProps) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-xl border border-white/10 bg-black/10 p-3">
      <div>
        <p className="text-sm font-semibold text-white">{label}</p>
        <p className="text-xs text-slate-400">{description}</p>
        {badge ? (
          <span className="mt-1 inline-flex items-center gap-1 rounded-full border border-white/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-300">
            <Check className="h-3 w-3 text-blue-300" />
            {badge}
          </span>
        ) : null}
      </div>
      <label className="relative inline-flex cursor-pointer items-center">
        <input
          type="checkbox"
          className="peer sr-only"
          checked={checked}
          disabled={disabled}
          onChange={(event) => onChange(event.target.checked)}
        />
        <div className="peer h-5 w-10 rounded-full bg-slate-600 after:absolute after:left-[3px] after:top-[3px] after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all peer-checked:bg-blue-500 peer-checked:after:translate-x-4 peer-disabled:opacity-60" />
      </label>
    </div>
  );
}
