"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";

const NOTIFICATION_CHANNELS = [
  { id: "telegram", label: "텔레그램", description: "실시간 공시·감성 알림을 받습니다." },
  { id: "email", label: "이메일", description: "일간 요약과 중요 경보를 이메일로 전송합니다." },
  { id: "webhook", label: "Webhook", description: "사내 시스템으로 이벤트를 전달합니다." }
] as const;

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [channelState, setChannelState] = useState<Record<string, boolean>>({
    telegram: true,
    email: false,
    webhook: false
  });
  const [sentimentThreshold, setSentimentThreshold] = useState(65);

  useEffect(() => setMounted(true), []);

  const isDark = mounted ? theme === "dark" : false;

  const handleChannelToggle = (channelId: string) => {
    setChannelState((prev) => ({
      ...prev,
      [channelId]: !prev[channelId]
    }));
  };

  const handleThemeToggle = () => {
    setTheme(isDark ? "light" : "dark");
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <section className="rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
          <header className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-sm font-semibold">테마 설정</h2>
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                라이트/다크 테마를 전환해 개인화된 화면을 설정하세요.
              </p>
            </div>
            <button
              type="button"
              onClick={handleThemeToggle}
              className="rounded-md border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
            >
              {isDark ? "라이트 테마로 전환" : "다크 테마로 전환"}
            </button>
          </header>
        </section>

        <section className="rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
          <h2 className="text-sm font-semibold">알림 채널</h2>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            사용할 알림 채널을 선택하세요. 추후 API 연동 시 이 설정이 기본값으로 사용됩니다.
          </p>
          <ul className="mt-4 space-y-3 text-sm">
            {NOTIFICATION_CHANNELS.map((channel) => (
              <li
                key={channel.id}
                className="flex items-start justify-between gap-3 rounded-lg border border-border-light px-4 py-3 dark:border-border-dark"
              >
                <div>
                  <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{channel.label}</p>
                  <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{channel.description}</p>
                </div>
                <label className="inline-flex cursor-pointer items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-primary"
                    checked={channelState[channel.id]}
                    onChange={() => handleChannelToggle(channel.id)}
                  />
                  사용
                </label>
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
          <h2 className="text-sm font-semibold">감성 임계값</h2>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            부정 감성 경보를 발생시키는 최소 감성 지수를 설정하세요.
          </p>
          <div className="mt-4">
            <input
              type="range"
              min={0}
              max={100}
              value={sentimentThreshold}
              onChange={(event) => setSentimentThreshold(Number(event.target.value))}
              className="w-full accent-primary"
            />
            <div className="mt-2 flex items-center justify-between text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              <span>0</span>
              <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{sentimentThreshold}</span>
              <span>100</span>
            </div>
          </div>
        </section>

        <section className="rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
          <h2 className="text-sm font-semibold">연동 준비</h2>
          <EmptyState
            title="추가 연동이 예정되어 있습니다"
            description="Langfuse, Qdrant, Telegram 등 외부 서비스와의 연동 상태는 추후 MLOps 구축 시 이 영역에서 관리할 예정입니다."
            className="border-none bg-transparent px-0 py-6"
          />
        </section>
      </div>
    </AppShell>
  );
}
