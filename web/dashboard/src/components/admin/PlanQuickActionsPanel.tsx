"use client";

import clsx from "classnames";
import { useEffect, useMemo, useState } from "react";

import { usePlanQuickAdjust } from "@/hooks/useAdminQuickActions";
import { useAdminSession } from "@/hooks/useAdminSession";
import { resolveApiBase } from "@/lib/apiBase";
import { useToastStore } from "@/store/toastStore";
import { planTierRank, usePlanStore, type PlanMemoryFlags, type PlanPreset, type PlanQuota, type PlanTier } from "@/store/planStore";
import { LIGHTMEM_FLAG_OPTIONS, type LightMemFlagKey } from "@/constants/lightmemFlags";
import { usePlanPresets } from "@/hooks/usePlanPresets";

type EntitlementOption = {
  value: string;
  label: string;
  description: string;
  minTier: PlanTier;
};

const ENTITLEMENT_OPTIONS: EntitlementOption[] = [
  { value: "search.compare", label: "비교 검색", description: "동시에 여러 회사를 비교 검색해요.", minTier: "pro" },
  { value: "search.alerts", label: "알림 검색", description: "조건 기반 알림을 설정하고 Slack/Email로 전달해요.", minTier: "pro" },
  { value: "search.export", label: "데이터 내보내기", description: "검색 결과를 CSV로 추출해요.", minTier: "enterprise" },
  { value: "evidence.inline_pdf", label: "PDF 인라인 뷰어", description: "대시보드에서 바로 PDF를 확인해요.", minTier: "pro" },
  { value: "evidence.diff", label: "정정 Diff 비교", description: "정정 공시 Diff 분석을 제공합니다.", minTier: "enterprise" },
  { value: "timeline.full", label: "전체 타임라인", description: "기업 이벤트 전체 타임라인을 확인해요.", minTier: "enterprise" },
];

const PLAN_TIER_LABEL: Record<PlanTier, string> = {
  free: "Free",
  pro: "Pro",
  enterprise: "Enterprise",
};

const labelForEntitlement = (value: string) =>
  ENTITLEMENT_OPTIONS.find((item) => item.value === value)?.label ?? value;

type ForceCheckoutState = "keep" | "enable" | "disable";

type FormState = {
  planTier: PlanTier;
  entitlements: Set<string>;
  expiresAtInput: string;
  actor: string;
  changeNote: string;
  chatRequestsPerDay: string;
  ragTopK: string;
  peerExportRowLimit: string;
  selfCheckEnabled: boolean;
  triggerCheckout: boolean;
  forceCheckout: ForceCheckoutState;
  memoryFlags: PlanMemoryFlags;
};

const isoToLocalInput = (iso?: string | null) => {
  if (!iso) {
    return "";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60 * 1000);
  return local.toISOString().slice(0, 16);
};

const localInputToIso = (value: string) => {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date.toISOString();
};

const sanitizeNumber = (value: string) => {
  if (!value.trim()) {
    return null;
  }
  const parsed = Number.parseInt(value, 10);
  if (Number.isNaN(parsed)) {
    throw new Error("숫자 필드에는 숫자만 입력해 주세요.");
  }
  return parsed;
};

const isEntitlementAllowed = (entitlement: string, tier: PlanTier) => {
  const option = ENTITLEMENT_OPTIONS.find((item) => item.value === entitlement);
  const requiredTier = option?.minTier ?? "enterprise";
  return planTierRank(tier) >= planTierRank(requiredTier);
};

type BaseEntitlementMap = Record<PlanTier, ReadonlySet<string>>;

const buildBaseEntitlementMap = (presets: Record<PlanTier, PlanPreset> | null): BaseEntitlementMap => ({
  free: new Set<string>(presets?.free?.entitlements ?? []),
  pro: new Set<string>(presets?.pro?.entitlements ?? []),
  enterprise: new Set<string>(presets?.enterprise?.entitlements ?? []),
});

const ensureEntitlementsForTier = (
  tier: PlanTier,
  entitlements: Iterable<string>,
  baseEntitlements: BaseEntitlementMap,
) => {
  const base = baseEntitlements[tier] ?? new Set<string>();
  const allowed = new Set<string>(base);

  for (const item of entitlements) {
    if (allowed.has(item)) {
      continue;
    }
    if (isEntitlementAllowed(item, tier)) {
      allowed.add(item);
    }
  }
  return allowed;
};

const buildInitialState = (
  args: {
  planTier: PlanTier;
  entitlements: string[];
  expiresAt?: string | null;
  quota: PlanQuota;
  updatedBy?: string | null;
  defaultActor?: string | null;
  memoryFlags: PlanMemoryFlags;
  },
  baseEntitlements: BaseEntitlementMap,
): FormState => ({
  planTier: args.planTier,
  entitlements: ensureEntitlementsForTier(args.planTier, args.entitlements, baseEntitlements),
  expiresAtInput: isoToLocalInput(args.expiresAt ?? null),
  actor: args.updatedBy ?? args.defaultActor ?? "admin@kfinance.ai",
  changeNote: "",
  chatRequestsPerDay: args.quota.chatRequestsPerDay?.toString() ?? "",
  ragTopK: args.quota.ragTopK?.toString() ?? "",
  peerExportRowLimit: args.quota.peerExportRowLimit?.toString() ?? "",
  selfCheckEnabled: Boolean(args.quota.selfCheckEnabled),
  triggerCheckout: false,
  forceCheckout: "keep",
  memoryFlags: { ...args.memoryFlags },
});

export function PlanQuickActionsPanel() {
  const {
    planTier,
    entitlements,
    quota,
    expiresAt,
    updatedBy,
    memoryFlags,
    checkoutRequested,
    fetchPlan,
  } = usePlanStore((state) => ({
    planTier: state.planTier,
    entitlements: state.entitlements,
    quota: state.quota,
    expiresAt: state.expiresAt,
    updatedBy: state.updatedBy,
    memoryFlags: state.memoryFlags,
    checkoutRequested: state.checkoutRequested,
    fetchPlan: state.fetchPlan,
  }));
  const { presets, loading: presetsLoading, error: presetsError } = usePlanPresets();
  const baseEntitlementSets = useMemo(() => buildBaseEntitlementMap(presets), [presets]);
  const {
    data: adminSession,
    isLoading: isAdminSessionLoading,
    isUnauthorized: isAdminUnauthorized,
    error: adminSessionError,
    refetch: refetchAdminSession,
  } = useAdminSession();
  const defaultActor = adminSession?.actor ?? null;
  const auditDownloadUrl = `${resolveApiBase()}/api/v1/admin/plan/audit/logs`;

  const [formState, setFormState] = useState<FormState>(() =>
    buildInitialState({ planTier, entitlements, quota, expiresAt, updatedBy, defaultActor, memoryFlags }, baseEntitlementSets),
  );
  const { mutateAsync, isPending } = usePlanQuickAdjust();
  const pushToast = useToastStore((state) => state.show);

  useEffect(() => {
    setFormState(
      buildInitialState({ planTier, entitlements, quota, expiresAt, updatedBy, defaultActor, memoryFlags }, baseEntitlementSets),
    );
  }, [baseEntitlementSets, planTier, entitlements, quota, expiresAt, updatedBy, defaultActor, memoryFlags]);

  const handleEntitlementToggle = (value: string) => {
    setFormState((prev) => {
      const locked = baseEntitlementSets[prev.planTier].has(value);
      if (locked || !isEntitlementAllowed(value, prev.planTier)) {
        return prev;
      }
      const next = new Set(prev.entitlements);
      if (next.has(value)) {
        next.delete(value);
      } else {
        next.add(value);
      }
      return { ...prev, entitlements: next };
    });
  };

  const handleMemoryFlagToggle = (flag: LightMemFlagKey) => {
    setFormState((prev) => ({
      ...prev,
      memoryFlags: {
        ...prev.memoryFlags,
        [flag]: !prev.memoryFlags[flag],
      },
    }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      const entitlementsList = Array.from(formState.entitlements);
      const expiresAtIso = localInputToIso(formState.expiresAtInput);
      const chatRequestsPerDay = sanitizeNumber(formState.chatRequestsPerDay);
      const ragTopK = sanitizeNumber(formState.ragTopK);
      const peerExportRowLimit = sanitizeNumber(formState.peerExportRowLimit);

      const actorValue = formState.actor.trim() || defaultActor || "admin@kfinance.ai";

      const payload = {
        planTier: formState.planTier,
        entitlements: entitlementsList,
        memoryFlags: formState.memoryFlags,
        expiresAt: expiresAtIso,
        actor: actorValue,
        changeNote: formState.changeNote.trim() || undefined,
        triggerCheckout: formState.triggerCheckout,
        quota: {
          chatRequestsPerDay,
          ragTopK,
          selfCheckEnabled: formState.selfCheckEnabled,
          peerExportRowLimit,
        },
        forceCheckoutRequested:
          formState.forceCheckout === "keep"
            ? null
            : formState.forceCheckout === "enable"
            ? true
            : false,
      };

      const result = await mutateAsync(payload);
      await fetchPlan().catch(() => undefined);
      pushToast({
        id: `admin/plan/quick-adjust/${Date.now()}`,
        title: "플랜이 갱신되었어요",
        message: `${PLAN_TIER_LABEL[result.planTier]} 플랜으로 조정되었습니다.`,
        intent: "success",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "플랜 조정 중 오류가 발생했어요.";
      pushToast({
        id: `admin/plan/quick-adjust/error/${Date.now()}`,
        title: "플랜 조정에 실패했어요",
        message,
        intent: "error",
      });
    }
  };

  const handleReset = () => {
    setFormState(
      buildInitialState({ planTier, entitlements, quota, expiresAt, updatedBy, defaultActor, memoryFlags }, baseEntitlementSets),
    );
  };

  const handleTierChange = (tier: PlanTier) => {
    setFormState((prev) => ({
      ...prev,
      planTier: tier,
      entitlements: ensureEntitlementsForTier(tier, prev.entitlements, baseEntitlementSets),
    }));
  };

  const baseEntitlements = baseEntitlementSets[formState.planTier];

  const entitlementSummary = useMemo(() => {
    const baseList = Array.from(baseEntitlements).map(labelForEntitlement);
    const extraList = Array.from(formState.entitlements)
      .filter((item) => !baseEntitlements.has(item))
      .map(labelForEntitlement);

    const baseText = baseList.length ? `기본: ${baseList.join(", ")}` : "기본: 없음";
    const extraText = extraList.length ? `추가: ${extraList.join(", ")}` : "추가: 없음";
    return `${baseText} · ${extraText}`;
  }, [baseEntitlements, formState.entitlements]);

  const memoryFlagSummary = useMemo(() => {
    const active = LIGHTMEM_FLAG_OPTIONS.filter((option) => formState.memoryFlags[option.key]).map(
      (option) => option.label,
    );
    return active.length ? active.join(", ") : "모두 비활성";
  }, [formState.memoryFlags]);

  const checkoutStatusLabel = checkoutRequested ? "진행 중" : "없음";
  const showLoadingSession = isAdminSessionLoading;
  const showUnauthorized = isAdminUnauthorized;
  const sessionError = !showUnauthorized && adminSessionError ? adminSessionError : undefined;
  const sessionErrorMessage =
    sessionError instanceof Error ? sessionError.message : "관리자 세션을 확인하지 못했어요.";

  let content: JSX.Element;

  if (showLoadingSession) {
    content = (
      <div className="mt-4 rounded-xl border border-dashed border-border-light bg-background-base/40 p-5 text-sm text-text-secondaryLight dark:border-border-dark dark:bg-background-cardDark/40 dark:text-text-secondaryDark">
        관리자 권한을 확인하는 중이에요. 잠시만 기다려 주세요.
      </div>
    );
  } else if (showUnauthorized) {
    content = (
      <div className="mt-4 rounded-xl border border-dashed border-amber-300 bg-amber-50 p-5 text-sm text-amber-800 dark:border-amber-500/60 dark:bg-amber-500/10 dark:text-amber-200">
        <p className="font-semibold">운영 팀 전용 공간이에요.</p>
        <p className="mt-2">
          접근 권한이 없거나 세션이 만료된 것 같아요. 새로운 토큰을 등록했거나 권한이 필요하다면 운영 팀에 편하게 알려 주세요.
        </p>
      </div>
    );
  } else if (sessionError) {
    content = (
      <div className="mt-4 rounded-xl border border-dashed border-red-300 bg-red-50 p-5 text-sm text-red-800 dark:border-red-500/60 dark:bg-red-500/10 dark:text-red-200">
        <p className="font-semibold">세션 정보를 불러오지 못했어요.</p>
        <p className="mt-2">{sessionErrorMessage}</p>
        <button
          type="button"
          onClick={() => refetchAdminSession()}
          className="mt-3 inline-flex items-center rounded-lg border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
        >
          다시 확인
        </button>
      </div>
    );
  } else {
    content = (
      <form className="mt-4 space-y-6" onSubmit={handleSubmit}>
        {presetsLoading && !presets && (
          <div className="rounded-lg border border-dashed border-border-light bg-background-base/50 px-3 py-2 text-xs text-text-secondaryLight dark:border-border-dark dark:bg-background-cardDark/40 dark:text-text-secondaryDark">
            플랜 프리셋 정보를 불러오는 중입니다. 잠시만 기다려 주세요.
          </div>
        )}
        {presetsError && (
          <div className="rounded-lg border border-dashed border-amber-400 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-500/60 dark:bg-amber-500/10 dark:text-amber-100">
            플랜 프리셋을 불러오지 못했습니다. 현재 저장된 값을 기준으로 편집합니다.
          </div>
        )}
        <div className="grid gap-4 lg:grid-cols-2">
          <div>
            <label className="text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
              현재 플랜
            </label>
            <div className="mt-1 flex items-center gap-3">
              <span className="rounded-full bg-primary/10 px-3 py-1 text-sm font-semibold text-primary">
                {PLAN_TIER_LABEL[planTier]}
              </span>
              <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                Checkout 상태: <strong>{checkoutStatusLabel}</strong>
              </span>
            </div>
          </div>
          <div className="grid gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            <p>
              만료일:{" "}
              <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                {expiresAt ? new Date(expiresAt).toLocaleString() : "설정되지 않음"}
              </span>
            </p>
            <p>권한: {entitlements.length ? entitlements.join(", ") : "없음"}</p>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <label className="flex flex-col gap-2 text-sm">
            <span className="font-medium text-text-primaryLight dark:text-text-primaryDark">적용할 플랜 티어</span>
            <select
              value={formState.planTier}
              onChange={(event) => handleTierChange(event.target.value as PlanTier)}
              className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark"
            >
              <option value="free">Free</option>
              <option value="pro">Pro</option>
              <option value="enterprise">Enterprise</option>
            </select>
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span className="font-medium text-text-primaryLight dark:text-text-primaryDark">만료일 (선택)</span>
            <input
              type="datetime-local"
              value={formState.expiresAtInput}
              onChange={(event) => setFormState((prev) => ({ ...prev, expiresAtInput: event.target.value }))}
              className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark"
            />
          </label>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-text-primaryLight dark:text-text-primaryDark">실행자(Actor)</span>
            <input
              type="text"
              value={formState.actor}
              onChange={(event) => setFormState((prev) => ({ ...prev, actor: event.target.value }))}
              placeholder={defaultActor ?? "운영자 이름"}
              className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
            />
            <span className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
              현재 로그인한 운영자 계정이 기본으로 채워집니다. 다른 담당자로 기록해야 한다면 직접 입력해 주세요.
            </span>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-text-primaryLight dark:text-text-primaryDark">변경 메모</span>
            <input
              type="text"
              value={formState.changeNote}
              onChange={(event) => setFormState((prev) => ({ ...prev, changeNote: event.target.value }))}
              placeholder="예: Slack 안내 송출, 2주 한시 업그레이드"
              className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
            />
            <span className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
              감사 로그와 알림 히스토리에 함께 남습니다.
            </span>
          </label>
        </div>

        <div>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-text-primaryLight dark:text-text-primaryDark">권한 선택</span>
            <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{entitlementSummary}</span>
          </div>
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            {ENTITLEMENT_OPTIONS.map((option) => {
              const isBase = baseEntitlements.has(option.value);
              const allowed = isEntitlementAllowed(option.value, formState.planTier);
              const checked = formState.entitlements.has(option.value);
              const disabled = isBase || !allowed;

              return (
                <label
                  key={option.value}
                  className={clsx(
                    "flex cursor-pointer flex-col rounded-lg border px-3 py-2 transition",
                    checked
                      ? "border-primary bg-primary/10 text-primary dark:border-primary dark:bg-primary/15 dark:text-primary"
                      : "border-border-light text-text-secondaryLight hover:border-primary/60 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary/40",
                    !allowed ? "cursor-not-allowed opacity-60" : "",
                  )}
                >
                  <span className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={disabled}
                      onChange={() => handleEntitlementToggle(option.value)}
                      className="h-4 w-4 rounded border-border-light text-primary focus:ring-primary dark:border-border-dark"
                    />
                    <span className="text-sm font-medium">{option.label}</span>
                    {isBase ? (
                      <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary dark:bg-primary/20">
                        기본
                      </span>
                    ) : !allowed ? (
                      <span className="rounded-full bg-border-light px-2 py-0.5 text-[10px] text-text-tertiaryLight dark:bg-border-dark dark:text-text-tertiaryDark">
                        {PLAN_TIER_LABEL[option.minTier]} 전용
                      </span>
                    ) : null}
                  </span>
                  <span className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                    
                  </span>
                </label>
              );
            })}
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-text-primaryLight dark:text-text-primaryDark">LightMem 개인화</span>
            <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{memoryFlagSummary}</span>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            {LIGHTMEM_FLAG_OPTIONS.map((option) => (
              <label
                key={option.key}
                className={clsx(
                  "flex cursor-pointer flex-col rounded-lg border px-3 py-2 text-sm transition",
                  formState.memoryFlags[option.key]
                    ? "border-primary bg-primary/10 text-primary dark:border-primary dark:bg-primary/15 dark:text-primary"
                    : "border-border-light text-text-secondaryLight hover:border-primary/60 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary/40",
                )}
              >
                <span className="flex items-center justify-between">
                  <span className="font-medium">{option.label}</span>
                  <input
                    type="checkbox"
                    checked={Boolean(formState.memoryFlags[option.key])}
                    onChange={() => handleMemoryFlagToggle(option.key)}
                    className="h-4 w-4 rounded border-border-light text-primary focus:ring-primary dark:border-border-dark"
                  />
                </span>
                <span className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">{option.helper}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <label className="flex flex-col gap-2 text-sm">
            <span className="font-medium text-text-primaryLight dark:text-text-primaryDark">Chat 제한(1일)</span>
            <input
              type="number"
              min={0}
              value={formState.chatRequestsPerDay}
              onChange={(event) => setFormState((prev) => ({ ...prev, chatRequestsPerDay: event.target.value }))}
              placeholder="예: 500 (비우면 무제한)"
              className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span className="font-medium text-text-primaryLight dark:text-text-primaryDark">RAG Top-K</span>
            <input
              type="number"
              min={1}
              value={formState.ragTopK}
              onChange={(event) => setFormState((prev) => ({ ...prev, ragTopK: event.target.value }))}
              placeholder="예: 6"
              className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span className="font-medium text-text-primaryLight dark:text-text-primaryDark">CSV 내보내기 한도</span>
            <input
              type="number"
              min={0}
              value={formState.peerExportRowLimit}
              onChange={(event) => setFormState((prev) => ({ ...prev, peerExportRowLimit: event.target.value }))}
              placeholder="비우면 무제한"
              className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span className="font-medium text-text-primaryLight dark:text-text-primaryDark">Self-check</span>
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={formState.selfCheckEnabled}
                onChange={(event) => setFormState((prev) => ({ ...prev, selfCheckEnabled: event.target.checked }))}
                className="h-4 w-4 rounded border-border-light text-primary focus:ring-primary dark:border-border-dark"
              />
              <span className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">활성화</span>
            </div>
          </label>
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          <label className="flex items-center gap-3 text-sm">
            <input
              type="checkbox"
              checked={formState.triggerCheckout}
              onChange={(event) => setFormState((prev) => ({ ...prev, triggerCheckout: event.target.checked }))}
              className="h-4 w-4 rounded border-border-light text-primary focus:ring-primary dark:border-border-dark"
            />
            <span className="font-medium text-text-primaryLight dark:text-text-primaryDark">
              저장 후 Toss Checkout 바로 시작
            </span>
          </label>
          <label className="flex flex-col gap-2 text-sm lg:col-span-2">
            <span className="font-medium text-text-primaryLight dark:text-text-primaryDark">
              Checkout Requested 플래그
            </span>
            <select
              value={formState.forceCheckout}
              onChange={(event) =>
                setFormState((prev) => ({ ...prev, forceCheckout: event.target.value as ForceCheckoutState }))
              }
              className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark"
            >
              <option value="keep">현재 상태 유지</option>
              <option value="enable">요청 상태로 설정</option>
              <option value="disable">요청 상태 해제</option>
            </select>
          </label>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-3">
          <button
            type="button"
            onClick={handleReset}
            className="inline-flex items-center rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
            disabled={isPending}
          >
            현재 플랜 값으로 초기화
          </button>
          <button
            type="submit"
            className={clsx(
              "inline-flex items-center rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-white transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
              isPending ? "cursor-not-allowed opacity-60" : "hover:bg-primary-hover",
            )}
            disabled={isPending}
          >
            {isPending ? "반영 중..." : "플랜 조정 적용"}
          </button>
        </div>
      </form>
    );
  }

  return (
    <section className="rounded-xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <header className="flex flex-col gap-1 border-b border-border-light pb-4 dark:border-border-dark">
        <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">플랜 퀵 액션</h2>
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          플랜 티어와 권한, 쿼터를 빠르게 조정하고 Toss checkout 상태를 정리합니다. 기본 제공 권한은 티어별로 잠겨 있어요.
        </p>
        <a
          href={auditDownloadUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs font-semibold text-primary hover:underline dark:text-primary"
        >
          감사 로그 다운로드 (plan_audit.jsonl)
        </a>
        {adminSession ? (
          <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
            확인된 운영 계정:{" "}
            <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{adminSession.actor}</span>
          </p>
        ) : null}
      </header>
      {content}
    </section>
  );
}
