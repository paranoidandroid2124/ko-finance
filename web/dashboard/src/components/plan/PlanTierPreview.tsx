"use client";

import clsx from "classnames";
import { useCallback, useEffect, useMemo, useState } from "react";

import { usePlanPresets } from "@/hooks/usePlanPresets";
import { usePlanStore, type PlanTier } from "@/store/planStore";
import { useToastStore } from "@/store/toastStore";
import { getTrialCountdownLabel } from "@/lib/trialUtils";
import { usePlanCatalog } from "@/hooks/usePlanCatalog";
import { resolvePlanMarketingCopy } from "@/lib/planContext";
import { usePlanTrialCta } from "@/hooks/usePlanTrialCta";

const PLAN_TIER_SEQUENCE: PlanTier[] = ["free", "starter", "pro", "enterprise"];

type PlanTierPreviewProps = {
  className?: string;
  variant?: "card" | "inline";
  focusTier?: PlanTier | null;
};

export function PlanTierPreview({ className, variant = "card", focusTier }: PlanTierPreviewProps) {
  const { planTier, expiresAt, memoryFlags } = usePlanStore((state) => ({
    planTier: state.planTier,
    expiresAt: state.expiresAt,
    memoryFlags: state.memoryFlags,
  }));
  const setPlanFromServer = usePlanStore((state) => state.setPlanFromServer);
  const pushToast = useToastStore((state) => state.show);
  const { presets, loading: presetsLoading } = usePlanPresets();
  const [selectedTier, setSelectedTier] = useState<PlanTier>(focusTier ?? planTier);
  const { catalog } = usePlanCatalog();
  const { trial, trialActive, trialAvailable, trialDurationDays, trialStarting, startTrialCta } = usePlanTrialCta();

  const tierOptions = useMemo(() => {
    if (!presets) {
      return PLAN_TIER_SEQUENCE;
    }
    return PLAN_TIER_SEQUENCE.filter((tier) => Boolean(presets[tier]));
  }, [presets]);

  const preset = useMemo(() => (presets ? presets[selectedTier] : null), [presets, selectedTier]);
  const trialEndsLabel = getTrialCountdownLabel(trial?.endsAt);
  const selectedTierCopy = useMemo(
    () => resolvePlanMarketingCopy(selectedTier, catalog),
    [selectedTier, catalog],
  );

  useEffect(() => {
    if (focusTier && focusTier !== selectedTier) {
      setSelectedTier(focusTier);
    }
  }, [focusTier, selectedTier]);

  const handleApply = useCallback(() => {
    if (!preset) {
      pushToast({
        id: "plan-preview/missing-preset",
        title: "플랜 정보를 불러오는 중입니다",
        message: "잠시 후 다시 시도해 주세요.",
        intent: "warning",
      });
      return;
    }
    if (selectedTier === planTier) {
      pushToast({
        id: "plan-preview/no-change",
        title: "이미 같은 플랜이에요",
        message: "지금 보고 있는 정보는 현재 플랜과 동일해요.",
        intent: "info",
      });
      return;
    }
    setPlanFromServer({
      planTier: selectedTier,
      expiresAt: expiresAt ?? null,
      entitlements: preset.entitlements,
      featureFlags: preset.featureFlags,
      memoryFlags,
      quota: preset.quota,
    });
    pushToast({
      id: `plan-preview/${selectedTier}`,
      title: `${selectedTierCopy.title} 플랜 미리보기 적용!`,
      message: "지금 보는 화면과 한도가 선택한 플랜 기준으로 새로고침됐어요.",
      intent: "success",
    });
  }, [expiresAt, memoryFlags, planTier, preset, pushToast, selectedTier, selectedTierCopy.title, setPlanFromServer]);

  const handleStartTrial = useCallback(() => {
    startTrialCta({ source: "plan-tier-preview" }).catch(() => undefined);
  }, [startTrialCta]);

  const content = (
    <div className="space-y-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
          플랜 미리보기
        </p>
        <h3 className="mt-1 text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">
          어떤 플랜이 어울리는지 바로 체험해 보세요
        </h3>
        <p className="mt-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          아래에서 원하는 플랜을 골라 적용하면 카드와 알림 톤이 즉시 갱신돼요. 저장하기 전까지는 미리보기라서 언제든 다시
          바꿀 수 있어요.
        </p>
      </div>

      {trialActive ? (
        <div className="rounded-lg border border-primary/40 bg-primary/10 p-4 text-xs text-text-primaryLight dark:border-primary.dark/40 dark:bg-primary.dark/15 dark:text-white">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-semibold">Pro 플랜 체험이 진행 중이에요</p>
              <p className="text-[11px] text-text-secondaryLight dark:text-white/80">
                {trialEndsLabel ? `${trialEndsLabel} 후 만료됩니다.` : "만료 예정 시간이 곧 갱신됩니다."}
              </p>
            </div>
            <span className="rounded-full border border-white/40 px-2 py-1 text-[11px] uppercase tracking-wide">Trial Live</span>
          </div>
        </div>
      ) : trialAvailable ? (
        <div className="rounded-lg border border-dashed border-primary/40 bg-primary/5 p-4 text-xs text-text-secondaryLight dark:border-primary.dark/40 dark:bg-primary.dark/10">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                지금 Pro {trialDurationDays}일 무료 체험을 시작해볼까요?
              </p>
              <p className="text-[11px]">검색 비교·알림 자동화·PDF 뷰어를 결제 없이 모두 사용해볼 수 있어요.</p>
            </div>
            <button
              type="button"
              onClick={handleStartTrial}
              disabled={trialStarting}
              className="rounded-lg border border-primary bg-primary px-3 py-2 text-[11px] font-semibold text-white shadow disabled:cursor-not-allowed disabled:opacity-60"
            >
              {trialStarting ? "체험 준비 중..." : "무료 체험 시작"}
            </button>
          </div>
        </div>
      ) : null}

      <div className="space-y-3">
        {tierOptions.map((tier) => {
          const tierCopy = resolvePlanMarketingCopy(tier, catalog);
          return (
            <label
              key={tier}
              className={clsx(
                "flex cursor-pointer items-start gap-3 rounded-xl border px-4 py-3 text-sm transition",
                selectedTier === tier
                  ? "border-primary bg-primary/10 text-text-primaryLight dark:border-primary.dark dark:bg-primary.dark/15"
                  : "border-border-light bg-white/70 text-text-secondaryLight hover:border-primary hover:text-text-primaryLight dark:border-border-dark dark:bg-background-cardDark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-text-primaryDark",
              )}
            >
              <input
                type="radio"
                name="plan-tier"
                value={tier}
                checked={selectedTier === tier}
                onChange={() => setSelectedTier(tier)}
                className="mt-1 h-4 w-4 accent-primary"
              />
              <span>
                <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                  {tierCopy.title}
                </span>
                <span className="ml-2 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] uppercase tracking-wide text-primary dark:bg-primary.dark/20 dark:text-primary.dark">
                  {tier}
                </span>
                <p className="mt-1 text-xs leading-5">{tierCopy.tagline}</p>
              </span>
            </label>
          );
        })}
      </div>

      <div className="rounded-lg border border-dashed border-border-light/70 bg-white/60 p-4 text-xs text-text-secondaryLight dark:border-border-dark/70 dark:bg-background-cardDark/60 dark:text-text-secondaryDark">
        <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">미리보기로 적용하면?</p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>요약 카드와 알림 한도가 즉시 업데이트돼요.</li>
          <li>플랜 잠금 문구도 선택한 플랜 톤에 맞춰 바뀝니다.</li>
          <li>정식 반영은 곧 연동될 Toss 결제 플로우에서 바로 진행할 수 있어요.</li>
        </ul>
      </div>

      <button
        type="button"
        onClick={handleApply}
        disabled={!preset || presetsLoading}
        className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-60 dark:bg-primary.dark dark:hover:bg-primary.dark/90"
      >
        {presetsLoading ? "플랜 정보 불러오는 중..." : "지금 플랜 분위기 체험하기"}
      </button>

      <div className="rounded-lg border border-border-light/70 bg-white/70 px-3 py-2 text-xs text-text-secondaryLight dark:border-border-dark/70 dark:bg-background-cardDark/70 dark:text-text-secondaryDark">
        {preset ? (
          <p>
            선택한 플랜의 주요 한도:{" "}
            <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
              채팅 {preset.quota.chatRequestsPerDay === null ? "무제한" : `${preset.quota.chatRequestsPerDay.toLocaleString("ko-KR")}회`}
              · RAG Top-K {preset.quota.ragTopK === null ? "무제한" : `${preset.quota.ragTopK}`}
              · 팀 내보내기 {preset.quota.peerExportRowLimit === null ? "무제한" : `${preset.quota.peerExportRowLimit}행`}
            </span>
          </p>
        ) : (
          <p className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">플랜 한도를 불러오는 중입니다...</p>
        )}
      </div>
    </div>
  );

  if (variant === "inline") {
    return <section className={clsx("space-y-4", className)}>{content}</section>;
  }

  return (
    <section
      className={clsx(
        "rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark",
        className,
      )}
    >
      {content}
    </section>
  );
}
