"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import { RefreshCw } from "lucide-react";

import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { useAlertPresetUsage } from "@/hooks/useAdminConfig";
import { formatKoreanDateTime } from "@/lib/datetime";

const WINDOW_OPTIONS = [
  { label: "최근 7일", value: 7 },
  { label: "최근 14일", value: 14 },
  { label: "최근 30일", value: 30 },
];

const numberFormatter = new Intl.NumberFormat("ko-KR");

export function AdminAlertPresetUsagePanel() {
  const [windowDays, setWindowDays] = useState(14);
  const { data, isLoading, isError, refetch } = useAlertPresetUsage(windowDays, true);

  const topPreset = data?.presets?.[0];
  const topBundle = data?.bundles?.[0];
  const generatedAtLabel =
    formatKoreanDateTime(data?.generatedAt ?? null, { includeSeconds: true }) ?? "집계 시각 미상";

  const planTotals = useMemo(() => {
    if (!data?.planTotals) {
      return [];
    }
    return Object.entries(data.planTotals).map(([tier, count]) => ({ tier, count }));
  }, [data?.planTotals]);

  return (
    <section className="space-y-4 rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
            Preset Launch Analytics
          </p>
          <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">
            프리셋 생성 {numberFormatter.format(data?.totalLaunches ?? 0)}회 · {windowDays}일
          </h2>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">집계 시각: {generatedAtLabel}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {WINDOW_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setWindowDays(option.value)}
              className={clsx(
                "rounded-full border px-3 py-1 text-xs font-semibold transition",
                option.value === windowDays
                  ? "border-primary bg-primary text-white"
                  : "border-border-light text-text-secondaryLight hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark",
              )}
            >
              {option.label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => refetch()}
            className="inline-flex items-center gap-2 rounded-full border border-border-light px-3 py-1 text-xs font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark"
          >
            <RefreshCw className={clsx("h-4 w-4", isLoading ? "animate-spin" : "")} />
            새로고침
          </button>
        </div>
      </header>

      {isError ? (
        <ErrorState
          title="프리셋 사용량을 불러오지 못했어요"
          description="네트워크 상태를 확인한 뒤 다시 시도해 주세요."
        />
      ) : isLoading ? (
        <SkeletonBlock lines={6} />
      ) : !data?.presets?.length ? (
        <EmptyState
          title="프리셋 생성 데이터가 없습니다"
          description="Starter/Pro 프리셋을 생성하면 여기에 사용량이 표시돼요."
        />
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-border-light bg-background-base p-4 text-sm dark:border-border-dark dark:bg-background-baseDark">
              <p className="text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
                Top Preset
              </p>
              <h3 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">
                {topPreset?.name ?? topPreset?.presetId}
              </h3>
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                {topPreset?.bundleLabel ?? topPreset?.bundle ?? "번들 미지정"}
              </p>
              <p className="mt-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                {numberFormatter.format(topPreset?.count ?? 0)}회 생성 · 최근{" "}
                {topPreset?.lastUsedAt
                  ? formatKoreanDateTime(topPreset.lastUsedAt, { includeSeconds: false })
                  : "기록 없음"}
              </p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                {Object.entries(topPreset?.channelTotals ?? {}).map(([channel, count]) => (
                  <span
                    key={`preset-channel-${channel}`}
                    className="rounded-full border border-border-light px-2 py-0.5 dark:border-border-dark"
                  >
                    {channel.toUpperCase()} · {numberFormatter.format(count)}
                  </span>
                ))}
              </div>
            </div>
            <div className="rounded-2xl border border-border-light bg-background-base p-4 text-sm dark:border-border-dark dark:bg-background-baseDark">
              <p className="text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
                Top Bundle
              </p>
              <h3 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">
                {topBundle?.label ?? topBundle?.bundle ?? "데이터 없음"}
              </h3>
              <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                {numberFormatter.format(topBundle?.count ?? 0)}회 생성
              </p>
              <div className="mt-3 space-y-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                {planTotals.map((plan) => (
                  <div key={`plan-${plan.tier}`} className="flex items-center justify-between">
                    <span className="font-semibold uppercase">{plan.tier}</span>
                    <span>{numberFormatter.format(plan.count)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="overflow-hidden rounded-2xl border border-border-light dark:border-border-dark">
            <table className="w-full text-left text-sm">
              <thead className="bg-border-light/40 text-xs uppercase text-text-secondaryLight dark:bg-border-dark/40 dark:text-text-secondaryDark">
                <tr>
                  <th className="px-4 py-2">Preset</th>
                  <th className="px-4 py-2">Bundle</th>
                  <th className="px-4 py-2 text-right">Launches</th>
                  <th className="px-4 py-2">Last Used</th>
                </tr>
              </thead>
              <tbody>
                {data.presets.slice(0, 6).map((preset) => (
                  <tr key={preset.presetId} className="border-t border-border-light/70 dark:border-border-dark/60">
                    <td className="px-4 py-2 font-semibold text-text-primaryLight dark:text-text-primaryDark">
                      {preset.name ?? preset.presetId}
                    </td>
                    <td className="px-4 py-2 text-text-secondaryLight dark:text-text-secondaryDark">
                      {preset.bundleLabel ?? preset.bundle ?? "—"}
                    </td>
                    <td className="px-4 py-2 text-right text-text-primaryLight dark:text-text-primaryDark">
                      {numberFormatter.format(preset.count)}
                    </td>
                    <td className="px-4 py-2 text-text-secondaryLight dark:text-text-secondaryDark">
                      {preset.lastUsedAt
                        ? formatKoreanDateTime(preset.lastUsedAt, { includeSeconds: false })
                        : "기록 없음"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
