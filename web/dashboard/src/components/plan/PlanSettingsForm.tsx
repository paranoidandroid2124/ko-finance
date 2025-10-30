"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import clsx from "classnames";

import {
  usePlanStore,
  type PlanContextUpdateInput,
  type PlanQuota,
  type PlanTier,
} from "@/store/planStore";
import { useToastStore } from "@/store/toastStore";
import { useTossCheckout } from "@/hooks/useTossCheckout";
import { planTierLabel } from "@/constants/planPricing";

type FormState = {
  planTier: PlanTier;
  expiresAt: string;
  entitlements: string[];
  quota: PlanQuota;
  updatedBy: string;
  changeNote: string;
  triggerCheckout: boolean;
};

const PLAN_TIER_OPTIONS: Array<{ value: PlanTier; label: string; helper: string }> = [
  {
    value: "free",
    label: "Free",
    helper: "처음 둘러보는 팀을 위한 맛보기 플랜이에요.",
  },
  {
    value: "pro",
    label: "Pro",
    helper: "자동화와 알림 채널을 한층 넓힐 때 어울리는 옵션이에요.",
  },
  {
    value: "enterprise",
    label: "Enterprise",
    helper: "맞춤 한도와 전담 지원이 필요한 파트너를 위한 플랜이에요.",
  },
];

const ENTITLEMENT_OPTIONS: Array<{ value: string; label: string; helper: string }> = [
  {
    value: "search.compare",
    label: "비교 검색",
    helper: "공시와 뉴스를 나란히 비교할 수 있게 열어줘요.",
  },
  {
    value: "search.alerts",
    label: "알림 검색",
    helper: "관심 키워드와 조건으로 자동 알림을 만들 수 있어요.",
  },
  {
    value: "search.export",
    label: "데이터 내보내기",
    helper: "CSV로 데이터를 내려받고 팀과 공유할 수 있어요.",
  },
  {
    value: "evidence.inline_pdf",
    label: "PDF 인라인 뷰어",
    helper: "문서를 내려받지 않고 바로 살펴볼 수 있게 도와줘요.",
  },
  {
    value: "evidence.diff",
    label: "증거 Diff 비교",
    helper: "버전별 차이를 한눈에 확인할 수 있도록 대비해요.",
  },
  {
    value: "timeline.full",
    label: "전체 타임라인",
    helper: "장기 이력을 끊김 없이 훑어볼 수 있게 확장해요.",
  },
];

const formatKoreanDateTime = (iso: string | null | undefined) => {
  if (!iso) {
    return "아직 저장 이력이 없어요.";
  }
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return "저장 시점을 확인 중이에요.";
  }
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
};

const normalizeNumberInput = (value: string): number | null => {
  if (!value.trim()) {
    return null;
  }
  const numeric = Number(value);
  if (Number.isNaN(numeric)) {
    return null;
  }
  return Math.max(0, Math.floor(numeric));
};

const sanitizeNote = (value: string): string | null => {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
};

type PlanSettingsFormProps = {
  className?: string;
};

export function PlanSettingsForm({ className }: PlanSettingsFormProps) {
  const {
    planTier,
    expiresAt,
    entitlements,
    quota,
    updatedAt,
    updatedBy,
    changeNote,
    checkoutRequested,
    saving,
    saveError,
    savePlan,
  } = usePlanStore((state) => ({
    planTier: state.planTier,
    expiresAt: state.expiresAt ?? "",
    entitlements: state.entitlements,
    quota: state.quota,
    updatedAt: state.updatedAt ?? null,
    updatedBy: state.updatedBy ?? "",
    changeNote: state.changeNote ?? "",
    checkoutRequested: state.checkoutRequested,
    saving: state.saving,
    saveError: state.saveError,
    savePlan: state.savePlan,
  }));
  const pushToast = useToastStore((store) => store.show);
  const { isPreparing: checkoutPreparing, startCheckout, getPreset } = useTossCheckout();

  const [form, setForm] = useState<FormState>({
    planTier,
    expiresAt,
    entitlements,
    quota: { ...quota },
    updatedBy,
    changeNote,
    triggerCheckout: false,
  });

  useEffect(() => {
    setForm({
      planTier,
      expiresAt,
      entitlements,
      quota: { ...quota },
      updatedBy,
      changeNote,
      triggerCheckout: false,
    });
  }, [planTier, expiresAt, entitlements, quota, updatedBy, changeNote]);

  const lastSavedLabel = useMemo(() => formatKoreanDateTime(updatedAt), [updatedAt]);

  const handleTierChange = (value: PlanTier) => {
    setForm((prev) => ({
      ...prev,
      planTier: value,
    }));
  };

  const toggleEntitlement = (value: string) => {
    setForm((prev) => {
      const hasValue = prev.entitlements.includes(value);
      const nextValues = hasValue
        ? prev.entitlements.filter((item) => item !== value)
        : [...prev.entitlements, value];
      return { ...prev, entitlements: nextValues };
    });
  };

  const handleQuotaNumberChange =
    (field: keyof Pick<PlanQuota, "chatRequestsPerDay" | "ragTopK" | "peerExportRowLimit">) =>
    (event: FormEvent<HTMLInputElement>) => {
      const value = event.currentTarget.value;
      setForm((prev) => ({
        ...prev,
        quota: {
          ...prev.quota,
          [field]: normalizeNumberInput(value),
        },
      }));
    };

  const handleBoolChange = (event: FormEvent<HTMLInputElement>) => {
    const checked = event.currentTarget.checked;
    setForm((prev) => ({
      ...prev,
      quota: {
        ...prev.quota,
        selfCheckEnabled: checked,
      },
    }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const payload: PlanContextUpdateInput = {
      planTier: form.planTier,
      expiresAt: form.expiresAt.trim() ? form.expiresAt.trim() : null,
      entitlements: form.entitlements,
      quota: {
        chatRequestsPerDay: form.quota.chatRequestsPerDay,
        ragTopK: form.quota.ragTopK,
        selfCheckEnabled: form.quota.selfCheckEnabled,
        peerExportRowLimit: form.quota.peerExportRowLimit,
      },
      updatedBy: sanitizeNote(form.updatedBy ?? ""),
      changeNote: sanitizeNote(form.changeNote ?? ""),
      triggerCheckout: form.triggerCheckout,
    };

    try {
      const saved = await savePlan(payload);
      pushToast({
        id: "plan-settings/save-success",
        title: "플랜 기본값을 저장했어요",
        message: `${planTierLabel(saved.planTier)} 플랜 기준으로 새 한도가 적용됐습니다.`,
        intent: "success",
      });
      setForm((prev) => ({
        ...prev,
        triggerCheckout: false,
      }));

      if (payload.triggerCheckout) {
        const targetTier = saved.planTier;

        if (targetTier === "free") {
          pushToast({
            id: "plan-settings/checkout-warning",
            title: "업그레이드 대상이 필요해요",
            message: "결제 테스트는 Pro 이상의 플랜을 선택했을 때만 열 수 있어요.",
            intent: "warning",
          });
          return;
        }

        const preset = getPreset(targetTier);
        if (!preset) {
          pushToast({
            id: "plan-settings/checkout-missing-preset",
            title: "결제 정보가 아직 준비되지 않았어요",
            message: "토스 결제 금액과 항목을 먼저 설정해 주세요.",
            intent: "error",
          });
          return;
        }

        pushToast({
          id: "plan-settings/checkout-request",
          title: `${planTierLabel(targetTier)} 결제 창을 띄울게요`,
          message: "토스페이먼츠 창이 열리면 안내에 따라 결제를 완료해 주세요.",
          intent: "info",
        });

        const redirectPath =
          typeof window !== "undefined"
            ? `${window.location.pathname}${window.location.search}`
            : "/settings";

        try {
          await startCheckout({
            targetTier,
            amount: preset.amount,
            orderName: preset.orderName,
            redirectPath,
          });
        } catch {
          // 오류 토스트는 useTossCheckout이 처리합니다.
        }
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : saveError ?? "플랜 저장 중 알 수 없는 오류가 발생했어요.";
      pushToast({
        id: "plan-settings/save-error",
        title: "저장에 잠깐 어려움이 있었어요",
        message,
        intent: "error",
      });
    }
  };

  return (
    <section
      className={clsx(
        "rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark",
        className,
      )}
    >
      <header className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
            Plan Settings
          </p>
          <h2 className="mt-1 text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">
            플랜 기본값을 바로 손볼 수 있어요
          </h2>
          <p className="mt-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            티어, 권한, 한도를 한 번에 정리하면 대시보드 전역에서 동일하게 반영돼요. 저장 기록이 남아 추후 변경 시에도 안심할 수
            있어요.
          </p>
        </div>
        <div className="rounded-lg bg-border-light/40 px-3 py-2 text-xs text-text-secondaryLight dark:bg-border-dark/40 dark:text-text-secondaryDark">
          마지막 저장&nbsp;
          <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{lastSavedLabel}</span>
          {updatedBy ? (
            <span className="ml-1 text-text-secondaryLight dark:text-text-secondaryDark">· {updatedBy}</span>
          ) : null}
        </div>
      </header>

      {saveError ? (
        <div className="mt-4 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive shadow-sm dark:border-destructive/60 dark:bg-destructive/15">
          마지막 저장이 조금 미끄러졌어요. 오류 메시지: {saveError}
        </div>
      ) : null}

      {checkoutRequested ? (
        <div className="mt-4 rounded-lg border border-primary/40 bg-primary/10 px-3 py-2 text-xs text-primary shadow-sm dark:border-primary.dark/60 dark:bg-primary.dark/15">
          토스페이먼츠 결제 요청이 접수되어 확인 중이에요. 승인 완료 후 플랜 정보가 자동으로 갱신됩니다.
        </div>
      ) : null}

      <form className="mt-6 space-y-6" onSubmit={handleSubmit}>
        <fieldset className="space-y-3">
          <legend className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
            플랜 티어
          </legend>
          <div className="grid gap-3 md:grid-cols-3">
            {PLAN_TIER_OPTIONS.map((option) => (
              <label
                key={option.value}
                className={clsx(
                  "flex cursor-pointer flex-col gap-1 rounded-xl border px-4 py-3 text-sm transition",
                  form.planTier === option.value
                    ? "border-primary bg-primary/10 text-text-primaryLight dark:border-primary.dark dark:bg-primary.dark/15"
                    : "border-border-light bg-white/70 text-text-secondaryLight hover:border-primary hover:text-text-primaryLight dark:border-border-dark dark:bg-background-cardDark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-text-primaryDark",
                )}
              >
                <span className="flex items-center justify-between">
                  <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{option.label}</span>
                  <input
                    type="radio"
                    name="plan-tier"
                    value={option.value}
                    checked={form.planTier === option.value}
                    onChange={() => handleTierChange(option.value)}
                    className="h-4 w-4 accent-primary"
                  />
                </span>
                <span className="text-xs leading-5 text-text-secondaryLight dark:text-text-secondaryDark">
                  {option.helper}
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="space-y-3">
          <legend className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
            권한
          </legend>
          <div className="grid gap-3 sm:grid-cols-2">
            {ENTITLEMENT_OPTIONS.map((item) => (
              <label
                key={item.value}
                className="flex cursor-pointer items-start gap-3 rounded-xl border border-border-light bg-white/70 p-3 text-sm text-text-secondaryLight transition hover:border-primary hover:text-text-primaryLight dark:border-border-dark dark:bg-background-cardDark dark:text-text-secondaryDark"
              >
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 accent-primary"
                  checked={form.entitlements.includes(item.value)}
                  onChange={() => toggleEntitlement(item.value)}
                />
                <span>
                  <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{item.label}</span>
                  <p className="mt-1 text-xs leading-5">{item.helper}</p>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="space-y-3">
          <legend className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
            한도
          </legend>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
              하루 채팅 요청
              <input
                type="number"
                min={0}
                inputMode="numeric"
                className="rounded-lg border border-border-light bg-white px-3 py-2 text-sm text-text-primaryLight transition focus:outline-none focus:ring-2 focus:ring-primary/60 dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                value={form.quota.chatRequestsPerDay ?? ""}
                onInput={handleQuotaNumberChange("chatRequestsPerDay")}
                placeholder="무제한이면 비워둘 수 있어요"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
              RAG Top-K
              <input
                type="number"
                min={0}
                inputMode="numeric"
                className="rounded-lg border border-border-light bg-white px-3 py-2 text-sm text-text-primaryLight transition focus:outline-none focus:ring-2 focus:ring-primary/60 dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                value={form.quota.ragTopK ?? ""}
                onInput={handleQuotaNumberChange("ragTopK")}
                placeholder="기본값을 유지하려면 비워둘 수 있어요"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
              팀 내보내기 한도 (행)
              <input
                type="number"
                min={0}
                inputMode="numeric"
                className="rounded-lg border border-border-light bg-white px-3 py-2 text-sm text-text-primaryLight transition focus:outline-none focus:ring-2 focus:ring-primary/60 dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                value={form.quota.peerExportRowLimit ?? ""}
                onInput={handleQuotaNumberChange("peerExportRowLimit")}
                placeholder="무제한이면 비워둘 수 있어요"
              />
            </label>
            <label className="mt-2 flex items-center gap-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
              <input
                type="checkbox"
                className="h-4 w-4 accent-primary"
                checked={form.quota.selfCheckEnabled}
                onChange={handleBoolChange}
              />
              LLM 셀프 체크 켜기
            </label>
          </div>
        </fieldset>

        <div className="grid gap-3 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            만료일 (ISO8601)
            <input
              type="text"
              className="rounded-lg border border-border-light bg-white px-3 py-2 text-sm text-text-primaryLight transition focus:outline-none focus:ring-2 focus:ring-primary/60 dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
              placeholder="예: 2025-12-31T00:00:00+09:00"
              value={form.expiresAt}
            onInput={(event) => {
              const nextValue = event.currentTarget.value;
              setForm((prev) => ({ ...prev, expiresAt: nextValue }));
            }}
            />
            <span className="text-[11px] leading-4 text-text-tertiaryLight dark:text-text-tertiaryDark">
              비워두면 만료일 없이 계속 제공돼요.
            </span>
          </label>
          <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            담당자 이름 또는 이메일
            <input
              type="text"
              className="rounded-lg border border-border-light bg-white px-3 py-2 text-sm text-text-primaryLight transition focus:outline-none focus:ring-2 focus:ring-primary/60 dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
              placeholder="예: hana@kfinance.ai"
              value={form.updatedBy}
              onInput={(event) => {
                const nextValue = event.currentTarget.value;
                setForm((prev) => ({ ...prev, updatedBy: nextValue }));
              }}
            />
            <span className="text-[11px] leading-4 text-text-ter티aryLight dark:text-text-tertiaryDark">
              저장 기록과 감사 로그에 함께 남아요.
            </span>
          </label>
        </div>

        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          관리자 메모
          <textarea
            rows={3}
            className="rounded-lg border border-border-light bg-white px-3 py-2 text-sm text-text-primaryLight transition focus:outline-none focus:ring-2 focus:ring-primary/60 dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
            placeholder="변경 이유나 고객 요청을 간단히 남겨주시면 운영에 큰 도움이 돼요."
            value={form.changeNote}
            onInput={(event) => {
              const nextValue = event.currentTarget.value;
              setForm((prev) => ({ ...prev, changeNote: nextValue }));
            }}
          />
        </label>

        <label className="flex items-start gap-3 rounded-lg border border-dashed border-border-light/70 bg-white/60 p-4 text-sm text-text-secondaryLight dark:border-border-dark/70 dark:bg-background-cardDark/60 dark:text-text-secondaryDark">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4 accent-primary"
            checked={form.triggerCheckout}
            onChange={(event) => {
              const { checked } = event.currentTarget;
              setForm((prev) => ({ ...prev, triggerCheckout: checked }));
            }}
          />
          <span>
            <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
              토스페이먼츠 연동 준비 신호 보내기
            </span>
            <p className="mt-1 text-xs leading-5">
              결제 플로우는 다음 릴리스에서 바로 연결될 예정이에요. 지금은 로그와 메모로만 기록돼요.
            </p>
          </span>
        </label>

        <div className="flex items-center justify-end gap-3">
          <button
            type="submit"
            disabled={saving || checkoutPreparing}
            className={clsx(
              "inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary dark:bg-primary.dark",
              saving || checkoutPreparing ? "opacity-70" : "hover:bg-primary-hover dark:hover:bg-primary.dark/90",
            )}
          >
            {saving ? "저장 중..." : checkoutPreparing ? "결제 창 준비 중..." : "플랜 기본값 저장하기"}
          </button>
        </div>
      </form>
    </section>
  );
}
