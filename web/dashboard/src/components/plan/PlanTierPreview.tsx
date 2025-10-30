"use client";

import clsx from "classnames";
import { useMemo, useState } from "react";

import { PLAN_PRESETS } from "@/constants/planPresets";
import { usePlanStore, type PlanTier } from "@/store/planStore";
import { useToastStore } from "@/store/toastStore";

const PLAN_DESCRIPTIONS: Record<PlanTier, string> = {
  free: "가볍게 써보는 체험 플랜이에요. 핵심 기능만 맛볼 수 있어요.",
  pro: "팀과 함께 자동화하고 싶은 분들을 위한 플랜이에요. 이메일과 웹훅이 바로 열려요.",
  enterprise: "모든 채널과 맞춤 한도를 마음껏 쓰는 파트너 전용 플랜이에요.",
};

type PlanTierPreviewProps = {
  className?: string;
  variant?: "card" | "inline";
};

export function PlanTierPreview({ className, variant = "card" }: PlanTierPreviewProps) {
  const { planTier, expiresAt } = usePlanStore((state) => ({
    planTier: state.planTier,
    expiresAt: state.expiresAt,
  }));
  const setPlanFromServer = usePlanStore((state) => state.setPlanFromServer);
  const pushToast = useToastStore((state) => state.show);
  const [selectedTier, setSelectedTier] = useState<PlanTier>(planTier);
  const presets = useMemo(() => PLAN_PRESETS[selectedTier], [selectedTier]);

  const handleApply = () => {
    if (selectedTier === planTier) {
      pushToast({
        id: "plan-preview/no-change",
        title: "이미 같은 플랜이에요",
        message: "지금 보고 있는 정보는 현재 플랜과 동일해요.",
        intent: "info",
      });
      return;
    }
    const preset = PLAN_PRESETS[selectedTier];
    setPlanFromServer({
      planTier: selectedTier,
      expiresAt: expiresAt ?? null,
      entitlements: preset.entitlements,
      featureFlags: preset.featureFlags,
      quota: preset.quota,
    });
    pushToast({
      id: `plan-preview/${selectedTier}`,
      title: `${selectedTier === "free" ? "Free" : selectedTier === "pro" ? "Pro" : "Enterprise"} 플랜 미리보기 적용!`,
      message: "지금 보는 화면과 한도가 선택한 플랜 기준으로 새로고침됐어요.",
      intent: "success",
    });
  };

  const content = (
    <div className="space-y-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
          플랜 미리보기
        </p>
        <h3 className="mt-1 text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">
          어떤 플랜이 어울리는지 바로 체험해보세요
        </h3>
        <p className="mt-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          아래에서 원하는 플랜을 골라 적용하면 카드와 알림 한도, 잠금 표시가 즉시 갱신돼요. 저장하기 전까지는 미리보기라서 언제든 다시 바꿀 수 있어요.
        </p>
      </div>

      <div className="space-y-3">
        {(Object.keys(PLAN_PRESETS) as PlanTier[]).map((tier) => (
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
                {tier === "free" ? "Free" : tier === "pro" ? "Pro" : "Enterprise"}
              </span>
              <span className="ml-2 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] uppercase tracking-wide text-primary dark:bg-primary.dark/20 dark:text-primary.dark">
                {tier}
              </span>
              <p className="mt-1 text-xs leading-5">{PLAN_DESCRIPTIONS[tier]}</p>
            </span>
          </label>
        ))}
      </div>

      <div className="rounded-lg border border-dashed border-border-light/70 bg-white/60 p-4 text-xs text-text-secondaryLight dark:border-border-dark/70 dark:bg-background-cardDark/60 dark:text-text-secondaryDark">
        <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">미리보기로 적용하면?</p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>요약 카드와 알림 한도 카드가 즉시 업데이트돼요.</li>
          <li>플랜 잠금 문구도 선택한 플랜 톤에 맞춰 바뀝니다.</li>
          <li>정식 반영은 곧 연결될 토스페이먼츠 결제 플로우에서 바로 진행할 수 있어요.</li>
        </ul>
      </div>

      <button
        type="button"
        onClick={handleApply}
        className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary dark:bg-primary.dark dark:hover:bg-primary.dark/90"
      >
        지금 플랜 분위기 체험하기
      </button>

      <div className="rounded-lg border border-border-light/70 bg-white/70 px-3 py-2 text-xs text-text-secondaryLight dark:border-border-dark/70 dark:bg-background-cardDark/70 dark:text-text-secondaryDark">
        <p>
          선택한 플랜의 주요 한도:{" "}
          <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
            채팅 {presets.quota.chatRequestsPerDay === null ? "무제한" : `${presets.quota.chatRequestsPerDay.toLocaleString("ko-KR")}회`}
            · RAG Top-K {presets.quota.ragTopK === null ? "무제한" : `${presets.quota.ragTopK}`}
            · 팀 내보내기 {presets.quota.peerExportRowLimit === null ? "무제한" : `${presets.quota.peerExportRowLimit}행`}
          </span>
        </p>
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
