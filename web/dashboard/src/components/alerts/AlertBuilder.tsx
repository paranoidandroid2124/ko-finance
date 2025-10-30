"use client";

import { useCallback, useEffect, useMemo, useRef, useState, useId } from "react";

import clsx from "classnames";
import { motion } from "framer-motion";
import { useCreateAlertRule, useUpdateAlertRule } from "@/hooks/useAlerts";
import {
  ApiError,
  type AlertPlanInfo,
  type AlertRule,
  type AlertChannelType,
  type AlertChannel,
  type AlertRuleCreatePayload,
  type AlertRuleUpdatePayload,
} from "@/lib/alertsApi";
import { useToastStore } from "@/store/toastStore";
import { PlanLock } from "@/components/ui/PlanLock";
import { usePlanTier, type PlanTier } from "@/store/planStore";
import { logEvent } from "@/lib/telemetry";
import { deriveInitialChannels, type BuilderMode, type ChannelState } from "@/components/alerts/channelForm";
import { useChannelValidation } from "@/components/alerts/useChannelValidation";
import { getPlanCopy, parsePlanTier, UNKNOWN_PLAN_COPY } from "@/components/alerts/planMessaging";
import { cloneChannels, useAlertChannels } from "@/components/alerts/useAlertChannels";
import { ChannelEditor } from "@/components/alerts/ChannelEditor";
import {
  buildInitialFormState,
  useAlertBuilderState,
} from "@/components/alerts/useAlertBuilderState";
import type { ToastInput } from "@/store/toastStore";

const parseList = (value: string) =>
  value
    .split(/[\s,]+/)
    .map((item) => item.trim())
    .filter(Boolean);

type AlertBuilderProps = {
  plan: AlertPlanInfo | null;
  existingCount: number;
  onSuccess?: () => void;
  onCancel?: () => void;
  editingRule?: AlertRule | null;
  mode?: BuilderMode;
  onRequestUpgrade?: (tier: PlanTier) => void;
};

export function AlertBuilder({
  plan,
  existingCount,
  onSuccess,
  onCancel,
  editingRule,
  mode = "create",
  onRequestUpgrade,
}: AlertBuilderProps) {
  const nameInputId = useId();
  const planTier = usePlanTier();
  const createMutation = useCreateAlertRule();
  const updateMutation = useUpdateAlertRule();
  const pushToast = useToastStore((state) => state.show);
  const showBuilderToast = useCallback(
    (suffix: string, payload: ToastInput) =>
      pushToast({
        ...payload,
        id: payload.id ?? `alerts/builder/${suffix}`,
      }),
    [pushToast],
  );

  const defaultEvaluationInterval = plan?.defaultEvaluationIntervalMinutes ?? 5;
  const minEvaluationInterval = plan?.minEvaluationIntervalMinutes ?? 1;
  const defaultWindowMinutes = plan?.defaultWindowMinutes ?? 60;
  const defaultCooldownMinutes = plan?.defaultCooldownMinutes ?? 60;
  const minCooldownMinutes = plan?.minCooldownMinutes ?? 0;
  const planDailyCap = plan?.maxDailyTriggers ?? undefined;

  const initialChannels = useMemo<ChannelState>(
    () => deriveInitialChannels({ plan, editingRule: editingRule ?? null, mode }),
    [plan, editingRule, mode],
  );

  const initialFormState = useMemo(
    () =>
      buildInitialFormState({
        editingRule: editingRule ?? null,
        mode,
        defaultEvaluationInterval,
        defaultWindowMinutes,
        defaultCooldownMinutes,
        planDailyCap,
      }),
    [defaultCooldownMinutes, defaultEvaluationInterval, defaultWindowMinutes, editingRule, mode, planDailyCap],
  );

  const {
    state: formState,
    actions: formActions,
    applySnapshot: applyFormSnapshot,
    resetToBaseline: resetFormFields,
  } = useAlertBuilderState({ initialState: initialFormState });

  const {
    name,
    description,
    conditionType,
    tickers,
    categories,
    sectors,
    minSentiment,
    evaluationMinutes,
    windowMinutes,
    cooldownMinutes,
    maxTriggersPerDay,
  } = formState;

  const {
    setName,
    setDescription,
    setConditionType,
    setTickers,
    setCategories,
    setSectors,
    setMinSentiment,
    setEvaluationMinutes,
    setWindowMinutes,
    setCooldownMinutes,
    setMaxTriggersPerDay,
  } = formActions;
  const [pendingFocusChannel, setPendingFocusChannel] = useState<string | null>(null);
  const {
    errors: channelErrors,
    validateChannel: validateChannelState,
    validateAll,
    clearChannel,
    resetErrors,
    definitions: channelDefinitions,
  } = useChannelValidation();
  const { channels, replaceAll: replaceChannels, toggleChannel, updateTarget, updateMetadata, updateTemplate } =
    useAlertChannels({
      initialState: initialChannels,
      validateChannel: validateChannelState,
      clearChannel,
    });
  const nameInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    applyFormSnapshot(initialFormState, { asBaseline: true });
    replaceChannels(cloneChannels(initialChannels));
    setPendingFocusChannel(null);
    resetErrors();
  }, [applyFormSnapshot, initialChannels, initialFormState, replaceChannels, resetErrors]);

  const planTierKey = parsePlanTier(plan?.planTier ?? planTier);
  const planCopy = plan ? getPlanCopy(planTierKey) : UNKNOWN_PLAN_COPY;
  const builderCopy = planCopy.builder;
  const maxAlerts = plan?.maxAlerts ?? 0;
  const remainingAlerts = plan?.remainingAlerts ?? Math.max(maxAlerts - existingCount, 0);
  const quotaInfo = useMemo(
    () => ({
      remaining: remainingAlerts,
      max: maxAlerts,
    }),
    [remainingAlerts, maxAlerts],
  );
  const isEligible = planTierKey !== "free";
  const isEditMode = mode === "edit" && Boolean(editingRule);
  const isDuplicateMode = mode === "duplicate" && Boolean(editingRule);
  const isCreateMode = mode === "create";
  const builderAnnouncement = useMemo(() => {
    if (isEditMode && editingRule) {
      return `알림 “${editingRule.name}”을 수정할 수 있는 창이 열렸어요. 탭 키로 필드를 이동하고 ESC나 닫기 버튼으로 언제든 종료할 수 있어요.`;
    }
    if (isDuplicateMode && editingRule) {
      return `알림 “${editingRule.name}”을 복제하는 새 폼이 열렸어요. 필요한 값만 바꾸고 저장하면 복제가 완료돼요.`;
    }
    return "새 알림을 만드는 폼이 열렸어요. 티커와 채널을 입력하고 저장하면 바로 알림을 받을 수 있어요.";
  }, [editingRule, isDuplicateMode, isEditMode]);
  const quotaReached = isCreateMode && maxAlerts > 0 && remainingAlerts <= 0;
  const nextEvaluationAt = plan?.nextEvaluationAt ? new Date(plan.nextEvaluationAt) : null;
  const nextEvaluationLabel = nextEvaluationAt
    ? new Intl.DateTimeFormat("ko-KR", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }).format(nextEvaluationAt)
    : "즉시 평가";
  const planDailyCapLabel =
    planDailyCap && planDailyCap > 0 ? `${planDailyCap.toLocaleString("ko-KR")}회/일` : "무제한";

  useEffect(() => {
    const input = nameInputRef.current;
    if (!input) {
      return;
    }
    if (typeof window === "undefined") {
      input.focus({ preventScroll: true });
      if (!isEditMode) {
        input.select();
      }
      return;
    }
    const raf = window.requestAnimationFrame(() => {
      input.focus({ preventScroll: true });
      if (!isEditMode) {
        input.select();
      }
    });
    return () => {
      window.cancelAnimationFrame(raf);
    };
  }, [editingRule, isEditMode, mode]);

  const allowedChannels = plan?.channels ?? [];
  const submitting = createMutation.isPending || updateMutation.isPending;
  const submitLabel = submitting
    ? isEditMode
      ? "저장 중..."
      : isDuplicateMode
      ? "복제 중..."
      : "생성 중..."
    : isEditMode
    ? "변경사항 저장"
    : isDuplicateMode
    ? "복제 완료"
    : "알림 생성";

  const handleChannelToggle = (channel: string, enabled: boolean) => {
    setPendingFocusChannel((prev) => (enabled ? channel : prev === channel ? null : prev));
    toggleChannel(channel, enabled);
  };

  const handleChannelTarget = (channel: string, targetValue: string) => {
    updateTarget(channel, targetValue);
  };

  const handleChannelMetadata = (channel: string, key: string, value: string) => {
    updateMetadata(channel, key, value);
  };

  const handleChannelTemplate = (channel: string, templateValue: string) => {
    updateTemplate(channel, templateValue);
  };

  const handlePendingFocusHandled = useCallback(() => {
    setPendingFocusChannel(null);
  }, []);

  const resetForm = useCallback(() => {
    resetFormFields();
    replaceChannels(cloneChannels(initialChannels));
    setPendingFocusChannel(null);
    resetErrors();
  }, [initialChannels, replaceChannels, resetErrors, resetFormFields]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!plan) {
      return;
    }
    if (quotaReached) {
      const { title, description: formatDescription } = builderCopy.quotaToast;
      showBuilderToast("quota", {
        title,
        message: formatDescription(quotaInfo),
        intent: "warning",
      });
      return;
    }
    const activeChannels = Object.entries(channels).filter(([, value]) => value.enabled);
    if (activeChannels.length === 0) {
      showBuilderToast("channel-required", {
        title: "채널 선택 필요",
        message: "최소 한 개 이상의 알림 채널을 선택해야 합니다.",
        intent: "warning",
      });
      return;
    }
    const activeChannelMap = Object.fromEntries(activeChannels) as ChannelState;
    const channelsValid = validateAll(activeChannelMap);
    if (!channelsValid) {
      const firstInvalid = activeChannels.find(([channelKey, config]) => !validateChannelState(channelKey, config));
      if (firstInvalid) {
        setPendingFocusChannel(firstInvalid[0]);
      }
      showBuilderToast("channel-invalid", {
        title: "채널 설정을 확인해주세요",
        message: "채널별 수신자와 메타데이터 입력값을 다시 살펴봐 주세요.",
        intent: "warning",
      });
      return;
    }
    const parsedTickers = parseList(tickers);
    if (parsedTickers.length === 0) {
      showBuilderToast("tickers", {
        title: "티커 입력 필요",
        message: "관심 기업 티커를 최소 한 개 이상 입력해 주세요.",
        intent: "warning",
      });
      return;
    }
    const categoriesList = parseList(categories);
    const sectorsList = parseList(sectors);
    const rawSentiment = Number.parseFloat(minSentiment);
    const sentimentValue =
      conditionType === "news" && minSentiment !== "" && Number.isFinite(rawSentiment) ? rawSentiment : undefined;
    const evaluationMinBound = Math.max(1, minEvaluationInterval);
    const evaluationValue = Number.isFinite(evaluationMinutes)
      ? Math.max(evaluationMinBound, Math.round(evaluationMinutes))
      : defaultEvaluationInterval;
    const windowMinBound = Math.max(evaluationMinBound, 5);
    const windowValue = Number.isFinite(windowMinutes)
      ? Math.max(windowMinBound, Math.round(windowMinutes))
      : defaultWindowMinutes;
    const cooldownMinBound = Math.max(0, minCooldownMinutes);
    const cooldownValue = Number.isFinite(cooldownMinutes)
      ? Math.max(cooldownMinBound, Math.round(cooldownMinutes))
      : defaultCooldownMinutes;
    const parsedMaxTriggers = maxTriggersPerDay ? Number(maxTriggersPerDay) : undefined;
    let maxTriggersValue: number | undefined;
    if (parsedMaxTriggers !== undefined && Number.isFinite(parsedMaxTriggers)) {
      const normalized = Math.max(1, Math.round(parsedMaxTriggers));
      maxTriggersValue = planDailyCap ? Math.min(normalized, planDailyCap) : normalized;
    } else if (planDailyCap) {
      maxTriggersValue = planDailyCap;
    } else {
      maxTriggersValue = undefined;
    }

    const channelPayloads: AlertChannel[] = activeChannels.map(([type, value]) => {
      const metadataEntries = Object.fromEntries(
        Object.entries(value.metadata)
          .map(([key, metadataValue]) => [key, metadataValue.trim()])
          .filter(([, metadataValue]) => metadataValue.length > 0),
      );
      const channelConfig: AlertChannel = {
        type: type as AlertChannelType,
        targets: value.targets.length > 0 ? value.targets : undefined,
      };
      if (value.targets.length > 0) {
        channelConfig.target = value.targets[0];
      }
      if (value.template && value.template !== "default") {
        channelConfig.template = value.template;
      }
      if (Object.keys(metadataEntries).length > 0) {
        channelConfig.metadata = metadataEntries;
      }
      return channelConfig;
    });

    if (channelPayloads.length === 0) {
      showBuilderToast("channel-empty", {
        title: "채널 설정 필요",
        message: "선택된 채널에 유효한 수신자가 없습니다.",
        intent: "warning",
      });
      return;
    }

    const trimmedName = name.trim();
    const createPayload: AlertRuleCreatePayload = {
      name: trimmedName || `새 알림 (${parsedTickers[0]})`,
      description: description.trim() || null,
      condition: {
        type: conditionType,
        tickers: parsedTickers,
        categories: conditionType === "filing" ? categoriesList : [],
        sectors: conditionType === "news" ? sectorsList : [],
        minSentiment: conditionType === "news" ? sentimentValue : undefined,
      },
      channels: channelPayloads,
      messageTemplate: null,
      evaluationIntervalMinutes: evaluationValue,
      windowMinutes: windowValue,
      cooldownMinutes: cooldownValue,
      maxTriggersPerDay: maxTriggersValue,
      extras: {},
    };

    try {
      if (isEditMode && editingRule) {
        const updatePayload: AlertRuleUpdatePayload = { ...createPayload };
        await updateMutation.mutateAsync({ id: editingRule.id, payload: updatePayload });
        logEvent("alerts.rule.updated", {
          planTier: plan.planTier,
          conditionType,
          channelTypes: channelPayloads.map((channel) => channel.type),
        });
        showBuilderToast("save-success", {
          title: "알림 수정 완료",
          message: "선택한 알림 규칙을 업데이트했습니다.",
          intent: "success",
        });
      } else {
        const createdRule = await createMutation.mutateAsync(createPayload);
        logEvent("alerts.rule.created", {
          planTier: plan.planTier,
          conditionType,
          channelTypes: channelPayloads.map((channel) => channel.type),
        });
        if (isDuplicateMode && editingRule) {
          logEvent("alerts.rule.duplicated", { sourceRuleId: editingRule.id, newRuleId: createdRule.id });
        }
        showBuilderToast(isDuplicateMode ? "duplicate-success" : "create-success", {
          title: isDuplicateMode ? "알림 복제 완료" : "알림 생성 완료",
          message: "새 알림 규칙을 저장했습니다.",
          intent: "success",
        });
      }
      resetForm();
      onSuccess?.();
    } catch (error) {
      let message = "요청을 처리하지 못했습니다.";
      let code: string | undefined;

      if (error instanceof ApiError) {
        code = error.code;
        if (code === "plan.quota_exceeded") {
          message = "플랜 한도를 초과했습니다. 기존 알림을 비활성화하거나 플랜을 업그레이드해 주세요.";
        } else if (code === "plan.channel_not_permitted") {
          message = "현재 플랜에서는 해당 채널을 사용할 수 없습니다.";
        } else if (code === "plan.quota_unavailable") {
          message = "플랜 정보를 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.";
        } else {
          message = error.message;
        }
      } else if (error instanceof Error) {
        message = error.message;
      }

      logEvent("alerts.rule.save_failed", {
        planTier: plan.planTier,
        conditionType,
        code,
        mode,
      });

      showBuilderToast("save-error", {
        title: isEditMode ? "알림 수정 실패" : "알림 생성 실패",
        message,
        intent: "error",
      });
    }
  };

  if (!plan || !plan.channels.length) {
    return (
      <div className="space-y-3 rounded-xl border border-border-light/80 bg-white/60 p-4 text-sm dark:border-border-dark/70 dark:bg-background-cardDark/40">
        <p className="text-text-secondaryLight dark:text-text-secondaryDark">플랜 정보를 불러오는 중입니다...</p>
      </div>
    );
  }

  if (!isEligible) {
    const lock = builderCopy.lock ?? {
      requiredTier: "pro",
      title: "Pro 플랜에서 사용할 수 있는 기능이에요",
      description: "Free 플랜에서는 알림 자동화를 미리보기로만 제공합니다. Pro로 업그레이드하고 이메일·Slack 등 원하는 채널로 즉시 보내 보세요.",
    };
    return (
      <PlanLock
        requiredTier={lock.requiredTier}
        title={lock.title}
        description={lock.description}
        className="rounded-xl border border-dashed border-border-light/70 bg-white/50 p-4"
        onUpgrade={onRequestUpgrade}
      />
    );
  }


  return (
    <motion.form
      className="space-y-4 rounded-xl border border-border-light/80 bg-white/80 p-4 text-sm shadow-sm dark:border-border-dark/70 dark:bg-background-cardDark/60"
      onSubmit={handleSubmit}
      initial={{ opacity: 0, y: 12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 8, scale: 0.98 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      role="form"
      data-testid="alert-builder-form"
    >
      <p className="sr-only" aria-live="polite" role="status">
        {builderAnnouncement}
      </p>
      <div className="rounded-lg border border-border-light/60 bg-white/70 p-3 dark:border-border-dark/70 dark:bg-background-cardDark/80">
        <div className="flex flex-wrap gap-3 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          <div className="flex-1 min-w-[120px]">
            <p className="font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
              남은 슬롯
            </p>
            <p className="mt-1 text-sm font-medium text-text-primaryLight dark:text-text-primaryDark">
              {maxAlerts > 0 ? `${remainingAlerts}/${maxAlerts}` : "무제한"}
            </p>
          </div>
          <div className="flex-1 min-w-[120px]">
            <p className="font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
              일일 발송 한도
            </p>
            <p className="mt-1 text-sm font-medium text-text-primaryLight dark:text-text-primaryDark">
              {planDailyCapLabel}
            </p>
          </div>
          <div className="flex-1 min-w-[120px]">
            <p className="font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
              다음 평가 예정
            </p>
            <p className="mt-1 text-sm font-medium text-text-primaryLight dark:text-text-primaryDark">
              {nextEvaluationLabel}
            </p>
          </div>
        </div>
      </div>

      <div>
        <label
          htmlFor={nameInputId}
          className="block text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark"
        >
          이름
        </label>
        <input
          id={nameInputId}
          ref={nameInputRef}
          type="text"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="예: TEST 티커 주요 공시"
          className="mt-1 w-full rounded-lg border border-border-light/70 bg-white/70 px-3 py-2 text-sm text-text-primaryLight outline-none transition focus:border-primary dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-primaryDark dark:focus:border-primary.dark"
        />
      </div>

      <div>
        <label className="block text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
          설명 (선택)
        </label>
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="팀원들이 알아보기 쉬운 메모를 남겨주세요."
          rows={3}
          className="mt-1 w-full rounded-lg border border-border-light/70 bg-white/70 px-3 py-2 text-sm text-text-primaryLight outline-none transition focus:border-primary dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-primaryDark dark:focus:border-primary.dark"
        />
      </div>

      <div>
        <label className="block text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-ter티aryDark">
          대상 데이터
        </label>
        <div className="mt-2 flex gap-3">
          {(["filing", "news"] as const).map((type) => (
            <button
              key={type}
              type="button"
              onClick={() => setConditionType(type)}
              className={clsx(
                "flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition",
                conditionType === type
                  ? "border-primary bg-primary/10 text-primary dark:border-primary.dark dark:bg-primary.dark/15 dark:text-primary.dark"
                  : "border-border-light/70 text-text-secondaryLight hover:border-primary hover:text-primary dark:border-border-dark/70 dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark",
              )}
            >
              {type === "filing" ? "공시" : "뉴스"}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
          티커
        </label>
        <input
          type="text"
          value={tickers}
          onChange={(event) => setTickers(event.target.value)}
          placeholder="콤마로 여러 개 입력 (예: KOSPI:005930, KOSDAQ:035420)"
          className="mt-1 w-full rounded-lg border border-border-light/70 bg-white/70 px-3 py-2 text-sm text-text-primaryLight outline-none transition focus:border-primary dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-primaryDark dark:focus:border-primary.dark"
        />
      </div>

      {conditionType === "filing" ? (
        <div>
          <label className="block text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
            공시 카테고리
          </label>
          <input
            type="text"
            value={categories}
            onChange={(event) => setCategories(event.target.value)}
            placeholder="예: periodic_report, capital_increase"
            className="mt-1 w-full rounded-lg border border-border-light/70 bg-white/70 px-3 py-2 text-sm text-text-primaryLight outline-none transition focus:border-primary dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-primaryDark dark:focus:border-primary.dark"
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div>
            <label className="block text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
              섹터/산업
            </label>
            <input
              type="text"
              value={sectors}
              onChange={(event) => setSectors(event.target.value)}
              placeholder="콤마 구분 (예: IT, 반도체)"
              className="mt-1 w-full rounded-lg border border-border-light/70 bg-white/70 px-3 py-2 text-sm text-text-primaryLight outline-none transition focus:border-primary dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-primaryDark dark:focus:border-primary.dark"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
              최소 감성 점수
            </label>
            <input
              type="number"
              step="0.1"
              min="-1"
              max="1"
              value={minSentiment}
              onChange={(event) => setMinSentiment(event.target.value)}
              className="mt-1 w-full rounded-lg border border-border-light/70 bg-white/70 px-3 py-2 text-sm text-text-primaryLight outline-none transition focus:border-primary dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-primaryDark dark:focus:border-primary.dark"
            />
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div>
          <label className="block text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
            평가 주기(분)
          </label>
          <input
            type="number"
            min={1}
            value={evaluationMinutes}
            onChange={(event) => setEvaluationMinutes(Number(event.target.value))}
            className="mt-1 w-full rounded-lg border border-border-light/70 bg-white/70 px-3 py-2 text-sm text-text-primaryLight outline-none transition focus:border-primary dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-primaryDark dark:focus:border-primary.dark"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
            탐색 윈도우(분)
          </label>
          <input
            type="number"
            min={5}
            value={windowMinutes}
            onChange={(event) => setWindowMinutes(Number(event.target.value))}
            className="mt-1 w-full rounded-lg border border-border-light/70 bg-white/70 px-3 py-2 text-sm text-text-primaryLight outline-none transition focus:border-primary dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-primaryDark dark:focus:border-primary.dark"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
            쿨다운(분)
          </label>
          <input
            type="number"
            min={0}
            value={cooldownMinutes}
            onChange={(event) => setCooldownMinutes(Number(event.target.value))}
            className="mt-1 w-full rounded-lg border border-border-light/70 bg-white/70 px-3 py-2 text-sm text-text-primaryLight outline-none transition focus:border-primary dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-primaryDark dark:focus:border-primary.dark"
          />
        </div>
      </div>

      <div>
        <label className="block text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
          일일 발송 제한(선택)
        </label>
        <input
          type="number"
          min={1}
          value={maxTriggersPerDay}
          onChange={(event) => setMaxTriggersPerDay(event.target.value)}
          placeholder="예: 하루 최대 5회"
          className="mt-1 w-full rounded-lg border border-border-light/70 bg-white/70 px-3 py-2 text-sm text-text-primaryLight outline-none transition focus:border-primary dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-primaryDark dark:focus:border-primary.dark"
        />
      </div>

      <ChannelEditor
        allowedChannels={allowedChannels}
        channels={channels}
        channelErrors={channelErrors}
        channelDefinitions={channelDefinitions}
        pendingFocusChannel={pendingFocusChannel}
        onPendingFocusHandled={handlePendingFocusHandled}
        onToggleChannel={handleChannelToggle}
        onTargetChange={handleChannelTarget}
        onTemplateChange={handleChannelTemplate}
        onMetadataChange={handleChannelMetadata}
      />

      <div className="flex items-center justify-between gap-3">
        <div className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
          {maxAlerts > 0
            ? `남은 슬롯 ${remainingAlerts}개 · 총 ${maxAlerts}개`
            : "남은 슬롯 무제한"}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => {
              resetForm();
              onCancel?.();
            }}
            className="rounded-lg border border-border-light/70 px-3 py-2 text-sm font-medium text-text-secondaryLight transition hover:border-border-light hover:text-text-primaryLight dark:border-border-dark/70 dark:text-text-secondaryDark dark:hover:border-border-dark dark:hover:text-text-primaryDark"
          >
            취소
          </button>
          <button
            type="submit"
            disabled={submitting || quotaReached}
            className={clsx(
              "rounded-lg px-3 py-2 text-sm font-semibold text-white transition",
              quotaReached
                ? "cursor-not-allowed bg-border-light/60 text-text-secondaryLight dark:bg-border-dark/60"
                : "bg-primary hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary dark:bg-primary.dark dark:hover:bg-primary.dark/90",
            )}
          >
            {submitLabel}
          </button>
        </div>
      </div>

      {quotaReached ? (
        <div className="rounded-lg border border-warning/50 bg-warning/10 px-3 py-2 text-xs text-warning dark:border-warning/40 dark:bg-warning/20">
          {builderCopy.quotaBanner(quotaInfo)}
        </div>
      ) : null}
    </motion.form>
  );
}

