"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import Link from "next/link";
import type { Route } from "next";
import { AlertTriangle, Sparkles, Clock3, ShieldCheck, Mail, Copy, PhoneCall } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { PlanLock } from "@/components/ui/PlanLock";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { EmptyState } from "@/components/ui/EmptyState";
import { ListState } from "@/components/ui/ListState";
import { ErrorState } from "@/components/ui/ErrorState";
import {
  useAlertRules,
  useAlertEventMatches,
  useCreateAlertRule,
} from "@/hooks/useAlerts";
import {
  ApiError,
  type AlertRule,
  type AlertRulePreset,
  type AlertEventMatch,
  type AlertChannelType,
  type AlertChannel,
  type AlertPlanInfo,
} from "@/lib/alertsApi";
import { logEvent } from "@/lib/telemetry";
import { formatDateTime, formatRelativeTime } from "@/lib/date";
import { useToastStore } from "@/store/toastStore";

type PresetBundle = {
  key: string;
  label: string;
  presets: AlertRulePreset[];
};

export default function AlertCenterPage() {
  const { data, isLoading, isError, error } = useAlertRules();
  const {
    data: matchData,
    isLoading: matchesLoading,
    isError: matchesError,
  } = useAlertEventMatches({ limit: 15 });
  const [presetDialog, setPresetDialog] = useState<AlertRulePreset | null>(null);

  const showToast = useToastStore((state) => state.show);

  const plan = data?.plan;
  const rules = data?.items ?? [];
  const presets = data?.presets ?? [];

  const bundles = useMemo<PresetBundle[]>(() => {
    if (!presets.length) {
      return [];
    }
    const groups = presets.reduce<Record<string, PresetBundle>>((acc, preset) => {
      const key = preset.bundle ?? "default";
      if (!acc[key]) {
        acc[key] = {
          key,
          label: preset.bundleLabel ?? preset.bundle ?? "추천 프리셋",
          presets: [],
        };
      }
      acc[key].presets.push(preset);
      return acc;
    }, {});
    return Object.values(groups);
  }, [presets]);

  if (error instanceof ApiError) {
    const isPlanGuard = error.status === 402 || error.code?.startsWith("plan.");
    return (
      <AppShell>
        {isPlanGuard ? (
          <PlanLock requiredTier="pro" title="Alert Center" description={error.message} />
        ) : (
          <ErrorState title="Alert Center" description={error.message} />
        )}
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <HeroSection plan={plan} totalRules={rules.length} />

        <section className="rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
          <SectionHeader
            title="활성 알림 룰"
            description="공시/뉴스 룰 현황을 한 번에 확인하세요. 워치리스트 페이지에서 세부편집이 가능합니다."
            ctaLabel="워치리스트로 이동"
            ctaHref="/watchlist"
          />
          <ListState
            className="mt-4"
            state={isLoading ? "loading" : rules.length === 0 ? "empty" : "ready"}
            skeleton={<SkeletonBlock className="h-40 rounded-2xl" />}
            emptyTitle="활성화된 알림 룰이 없어요"
            emptyDescription="프리셋을 선택하거나 워치리스트에서 직접 알림을 만들어 보세요."
            emptyAction={
              <Link href="/watchlist" className="text-primary underline">
                워치리스트 열기
              </Link>
            }
          >
            <div className="grid gap-4 md:grid-cols-2">
              {rules.map((rule) => (
                <RuleCard key={rule.id} rule={rule} />
              ))}
            </div>
          </ListState>
        </section>

        <section className="rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
          <SectionHeader
            title="Starter / Pro 프리셋"
            description="플랜에 맞춰 튜닝된 DSL 조합입니다. 채널만 지정하면 바로 룰을 만들 수 있어요."
          />
          <ListState
            className="mt-4"
            state={isLoading && !bundles.length ? "loading" : bundles.length === 0 ? "empty" : "ready"}
            skeleton={<SkeletonBlock className="h-48 rounded-2xl" />}
            emptyTitle="사용 가능한 프리셋이 없습니다"
            emptyDescription="플랜을 업그레이드하면 추천 룰 묶음을 사용할 수 있어요."
            emptyAction={
              <Link href="/pricing" className="text-primary underline">
                플랜 보기
              </Link>
            }
          >
            <div className="space-y-6">
              {bundles.map((bundle) => (
                <div key={bundle.key} className="space-y-3 rounded-2xl border border-border-light p-4 dark:border-border-dark">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
                        {bundle.label}
                      </p>
                      <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                        {bundle.presets.length}개 프리셋
                      </p>
                    </div>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    {bundle.presets.map((preset) => (
                      <button
                        key={preset.id}
                        type="button"
                        onClick={() => {
                          logEvent("alerts.preset.dialog_open", {
                            presetId: preset.id,
                            bundle: preset.bundle ?? "default",
                          });
                          setPresetDialog(preset);
                        }}
                        className="flex flex-col rounded-2xl border border-border-light bg-background-base p-4 text-left transition hover:border-primary hover:shadow-sm dark:border-border-dark dark:bg-background-baseDark"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                              {preset.name}
                            </p>
                            {preset.description ? (
                              <p className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                                {preset.description}
                              </p>
                            ) : null}
                          </div>
                          <Sparkles className="h-5 w-5 text-primary" aria-hidden />
                        </div>
                        {preset.tags.length ? (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {preset.tags.map((tag) => (
                              <span
                                key={`${preset.id}-${tag}`}
                                className="rounded-full bg-border-light/60 px-2 py-0.5 text-[11px] font-semibold text-text-secondaryLight dark:bg-border-dark/60 dark:text-text-secondaryDark"
                              >
                                {tag}
                              </span>
                            ))}
                          </div>
                        ) : null}
                        {preset.sampleDsl ? (
                          <p className="mt-3 truncate rounded-md bg-border-light/40 px-3 py-2 text-xs font-mono text-text-secondaryLight dark:bg-border-dark/50 dark:text-text-secondaryDark">
                            {preset.sampleDsl}
                          </p>
                        ) : null}
                        <div className="mt-3 flex items-center justify-between text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                          <span>추천 채널 · {preset.recommendedChannel?.toUpperCase() ?? "EMAIL"}</span>
                          <span className="font-semibold text-primary">한 번에 생성</span>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </ListState>
        </section>

        <section className="rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
          <SectionHeader
            title="최근 매칭된 이벤트"
            description="DSL 룰이 감지한 공시/뉴스 매칭 로그입니다."
          />
          {matchesError ? (
            <ErrorState
              title="최근 이벤트를 불러오지 못했어요"
              description="잠시 후 다시 시도해 주세요."
            />
          ) : matchesLoading ? (
            <SkeletonBlock className="mt-4 h-40 rounded-2xl" />
          ) : (
            <RecentEventList matches={matchData?.matches ?? []} />
          )}
        </section>
      </div>

      {presetDialog ? (
        <PresetDialog
          preset={presetDialog}
          planChannels={plan?.channels ?? ["email"]}
          onClose={() => setPresetDialog(null)}
          onSubmitSuccess={() => {
            setPresetDialog(null);
            showToast({
              id: `preset-${presetDialog.id}`,
              title: "프리셋 알림이 생성되었어요",
              message: `"${presetDialog.name}" DSL 룰이 활성화되었습니다.`,
              intent: "success",
            });
          }}
          onSubmitError={(message) =>
            showToast({
              id: `preset-${presetDialog.id}-error`,
              title: "프리셋 생성에 실패했어요",
              message: message ?? "잠시 후 다시 시도해 주세요.",
              intent: "error",
            })
          }
        />
      ) : null}
    </AppShell>
  );
}

function HeroSection({ plan, totalRules }: { plan?: AlertPlanInfo; totalRules: number }) {
  return (
    <section className="rounded-3xl border border-border-light bg-gradient-to-r from-background-cardLight via-white to-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:from-background-cardDark dark:via-background-baseDark dark:to-background-cardDark">
      <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
            Alert Center · Evidence-first
          </p>
          <h1 className="mt-2 text-2xl font-semibold text-text-primaryLight dark:text-text-primaryDark">
            공시/뉴스 알림을 Preset으로 바로 시작하세요
          </h1>
          <p className="mt-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            DSL에 익숙하지 않아도 Starter/Pro에 맞춰 튜닝된 룰을 한 번에 생성하고, 워치리스트 Digest와 연결할 수 있습니다.
          </p>
          <div className="mt-4 flex flex-wrap gap-3 text-sm">
            <MetricPill icon={<ShieldCheck className="h-4 w-4" />} label="플랜" value={plan?.planTier?.toUpperCase() ?? "⋯"} />
            <MetricPill
              icon={<Sparkles className="h-4 w-4" />}
              label="사용 중"
              value={`${totalRules}/${plan?.maxAlerts ?? "∞"} Rules`}
            />
            <MetricPill
              icon={<Clock3 className="h-4 w-4" />}
              label="다음 평가"
              value={formatDateTime(plan?.nextEvaluationAt, { fallback: "예정 없음" })}
            />
          </div>
        </div>
        <div className="flex flex-col gap-3 rounded-2xl border border-border-light bg-background-base p-4 dark:border-border-dark dark:bg-background-baseDark">
          <div className="flex items-start gap-3">
            <Sparkles className="mt-1 h-5 w-5 text-primary" aria-hidden />
            <div>
              <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">Evidence-first Preset</p>
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                루틴 알림 + Digest까지 연결하는 워크플로를 5분 안에 구성하세요.
              </p>
            </div>
          </div>
          <Link
            href="/watchlist"
            className="inline-flex items-center justify-center rounded-full bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary/90"
          >
            워치리스트로 이동
          </Link>
        </div>
      </div>
    </section>
  );
}

function MetricPill({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-border-light/80 bg-white px-3 py-1 text-xs font-medium text-text-secondaryLight shadow-sm dark:border-border-dark/70 dark:bg-background-baseDark dark:text-text-secondaryDark">
      {icon}
      <span>
        {label} · <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{value}</span>
      </span>
    </div>
  );
}

type SectionHeaderProps = {
  title: string;
  description: string;
  ctaLabel?: string;
  ctaHref?: Route;
};

function SectionHeader({
  title,
  description,
  ctaLabel,
  ctaHref,
}: SectionHeaderProps) {
  return (
    <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
      <div>
        <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">{title}</h2>
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">{description}</p>
      </div>
      {ctaLabel && ctaHref ? (
        <Link
          href={ctaHref}
          className="inline-flex items-center gap-2 rounded-full border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark"
        >
          {ctaLabel}
        </Link>
      ) : null}
    </div>
  );
}

function RuleCard({ rule }: { rule: AlertRule }) {
  const statusLabel =
    rule.status === "paused" ? "일시 중지" : rule.status === "archived" ? "보관" : "활성";
  const topChannel = rule.channels?.[0];
  const channelLabel = topChannel ? topChannel.type.toUpperCase() : "N/A";
  return (
    <div className="rounded-2xl border border-border-light bg-background-base p-4 transition hover:border-primary dark:border-border-dark dark:bg-background-baseDark">
      <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">{rule.name}</p>
            <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              {rule.trigger.type === "news" ? "뉴스" : "공시"} · {channelLabel}
            </p>
          </div>
          <span
            className={clsx(
              "rounded-full px-3 py-1 text-xs font-semibold",
              rule.status === "active"
                ? "bg-primary/10 text-primary"
                : rule.status === "paused"
                  ? "bg-accent-warning/15 text-accent-warning"
                  : "bg-border-light/60 text-text-secondaryLight dark:bg-border-dark/60 dark:text-text-secondaryDark",
            )}
          >
            {statusLabel}
          </span>
        </div>
      <p className="mt-3 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
        윈도우 {rule.frequency.windowMinutes}분 · 평가 {rule.frequency.evaluationIntervalMinutes}분 · 쿨다운{" "}
        {rule.frequency.cooldownMinutes}분
      </p>
      <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
        {rule.trigger.tickers.slice(0, 3).map((ticker) => (
          <span key={`${rule.id}-${ticker}`} className="rounded-full bg-border-light/60 px-2 py-0.5 dark:bg-border-dark/50">
            #{ticker}
          </span>
        ))}
        {rule.trigger.categories?.slice(0, 3).map((category) => (
          <span key={`${rule.id}-category-${category}`} className="rounded-full bg-border-light/60 px-2 py-0.5 dark:bg-border-dark/50">
            {category}
          </span>
        ))}
        {rule.trigger.sectors?.slice(0, 2).map((sector) => (
          <span key={`${rule.id}-sector-${sector}`} className="rounded-full bg-border-light/60 px-2 py-0.5 dark:bg-border-dark/50">
            {sector}
          </span>
        ))}
      </div>
    </div>
  );
}

function RecentEventList({ matches }: { matches: AlertEventMatch[] }) {
  if (matches.length === 0) {
    return <EmptyState title="최근 이벤트가 없습니다" description="새로운 매칭이 들어오면 이곳에 표시됩니다." />;
  }
  return (
    <div className="mt-4 divide-y divide-border-light rounded-2xl border border-border-light dark:divide-border-dark dark:border-border-dark">
      {matches.map((match) => {
        const relativeMatchedAt = formatRelativeTime(match.matchedAt, { fallback: "시각 미상" });
        const absoluteMatchedAt = formatDateTime(match.matchedAt, {
          fallback: "시각 미상",
          includeSeconds: true,
        });
        return (
          <div
            key={match.eventId}
            className="flex flex-col gap-1 px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between"
          >
            <div>
              <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                {match.ruleName}
                {match.ticker ? (
                  <span className="ml-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">{match.ticker}</span>
                ) : null}
              </p>
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                {match.eventType?.toUpperCase()} · {match.corpName ?? "N/A"}
              </p>
            </div>
            <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark" title={absoluteMatchedAt}>
              {relativeMatchedAt}
            </p>
          </div>
        );
      })}
    </div>
  );
}

type PresetDialogProps = {
  preset: AlertRulePreset;
  planChannels: string[];
  onClose: () => void;
  onSubmitSuccess: () => void;
  onSubmitError: (message: string) => void;
};

function PresetDialog({ preset, planChannels, onClose, onSubmitSuccess, onSubmitError }: PresetDialogProps) {
  const [channel, setChannel] = useState<AlertChannelType>(
    (planChannels[0] as AlertChannelType) ?? "email",
  );
  const [target, setTarget] = useState("");
  const [copyTooltip, setCopyTooltip] = useState(false);
  const createRule = useCreateAlertRule();

  const handleSubmit = async () => {
    const trimmed = target.trim();
    if (!trimmed) {
      onSubmitError("전달할 채널 주소를 입력해 주세요.");
      return;
    }
    try {
      await createRule.mutateAsync({
        name: preset.name,
        description: preset.description ?? undefined,
        trigger: preset.trigger,
        frequency: preset.frequency,
        channels: [
          {
            type: channel,
            target: trimmed,
          } as AlertChannel,
        ],
        messageTemplate: preset.sampleDsl ?? undefined,
        extras: {
          presetId: preset.id,
          presetBundle: preset.bundle ?? undefined,
        },
      });
      logEvent("alerts.preset.created", {
        presetId: preset.id,
        bundle: preset.bundle ?? "default",
        channel,
      });
      onSubmitSuccess();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "알 수 없는 오류가 발생했어요.";
      onSubmitError(message);
    }
  };

  const handleCopy = () => {
    if (!preset.sampleDsl) {
      return;
    }
    void navigator.clipboard.writeText(preset.sampleDsl);
    setCopyTooltip(true);
    setTimeout(() => setCopyTooltip(false), 1500);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
      <div className="w-full max-w-lg rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-2xl dark:border-border-dark dark:bg-background-cardDark">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
              Preset · {preset.bundleLabel ?? "추천"}
            </p>
            <h3 className="mt-1 text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark">
              {preset.name}
            </h3>
            {preset.insight ? (
              <p className="mt-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">{preset.insight}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-border-light p-1 text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark"
          >
            ✕
          </button>
        </div>

        {preset.sampleDsl ? (
          <div className="mt-4 rounded-2xl border border-border-light bg-background-base p-3 font-mono text-xs text-text-secondaryLight dark:border-border-dark dark:bg-background-baseDark dark:text-text-secondaryDark">
            <div className="flex items-center justify-between text-[11px]">
              <span>DSL 예시</span>
              <button
                type="button"
                onClick={handleCopy}
                className="inline-flex items-center gap-1 text-primary"
              >
                <Copy className="h-3.5 w-3.5" />
                {copyTooltip ? "복사됨" : "복사"}
              </button>
            </div>
            <p className="mt-2 break-words">{preset.sampleDsl}</p>
          </div>
        ) : null}

        <div className="mt-4 space-y-3 text-sm">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-semibold text-text-secondaryLight dark:text-text-secondaryDark">채널</span>
            <select
              value={channel}
              onChange={(event) => setChannel(event.target.value as AlertChannelType)}
              className="rounded-xl border border-border-light bg-background-base px-3 py-2 text-sm dark:border-border-dark dark:bg-background-baseDark"
            >
              {planChannels.map((type) => (
                <option key={type} value={type}>
                  {type.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs font-semibold text-text-secondaryLight dark:text-text-secondaryDark">
              전달 대상
            </span>
            <input
              value={target}
              onChange={(event) => setTarget(event.target.value)}
              placeholder={channel === "email" ? "alerts@company.com" : channel === "telegram" ? "@channel" : "#alerts"}
              className="rounded-xl border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary dark:border-border-dark dark:bg-background-baseDark dark:text-text-primaryDark"
            />
          </label>
        </div>

        <div className="mt-6 flex flex-col gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          <p className="flex items-center gap-2">
            <Mail className="h-3.5 w-3.5" />
            {preset.planTiers.includes("starter") ? "Starter" : "Pro"} 플랜 권장 프리셋
          </p>
          <p className="flex items-center gap-2">
            <PhoneCall className="h-3.5 w-3.5" />
            채널은 생성 후에도 워치리스트에서 수정할 수 있어요.
          </p>
        </div>

        <div className="mt-6 flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-2xl border border-border-light px-4 py-2 text-sm font-semibold text-text-secondaryLight transition hover:border-border-dark/70 dark:border-border-dark dark:text-text-secondaryDark"
          >
            취소
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={createRule.isPending}
            className="w-full rounded-2xl bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary/90 disabled:opacity-70"
          >
            {createRule.isPending ? "생성 중…" : "프리셋 생성"}
          </button>
        </div>
      </div>
    </div>
  );
}
