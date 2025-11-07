"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, Bold, CheckCircle2, Italic, List, Loader2, Mail, Plus, Slack, Trash2, X } from "lucide-react";

import { FilterChip } from "@/components/ui/FilterChip";
import { TagInput } from "@/components/ui/TagInput";
import { CompanyTickerInput } from "@/components/watchlist/CompanyTickerInput";
import { useCreateAlertRule, useUpdateAlertRule } from "@/hooks/useAlerts";
import type {
  AlertChannel,
  AlertChannelType,
  AlertCondition,
  AlertRule,
  AlertRuleCreatePayload,
  AlertRuleUpdatePayload,
} from "@/lib/alertsApi";
import { ApiError } from "@/lib/alertsApi";
import { useToastStore } from "@/store/toastStore";
import type { WatchlistRuleDetail } from "@/lib/alertsApi";

type WizardMode = "create" | "edit";
type WizardStep = 0 | 1 | 2;

type ChannelDraft = {
  id: string;
  type: AlertChannelType;
  label: string;
  target: string;
  targets: string[];
  template: string;
};

type RuleDraft = {
  name: string;
  description: string;
  conditionType: AlertCondition["type"];
  tickers: string[];
  sectors: string[];
  categories: string[];
  minSentiment: string;
  evaluationIntervalMinutes: string;
  windowMinutes: string;
  cooldownMinutes: string;
  maxTriggersPerDay: string;
  channels: ChannelDraft[];
  messageTemplate: string;
};

const DEFAULT_RULE_DRAFT: RuleDraft = {
  name: "",
  description: "",
  conditionType: "news",
  tickers: [],
  sectors: [],
  categories: [],
  minSentiment: "",
  evaluationIntervalMinutes: "60",
  windowMinutes: "1440",
  cooldownMinutes: "60",
  maxTriggersPerDay: "",
  channels: [],
  messageTemplate: "",
};

const SLACK_FAVORITES = ["#executive-brief", "@ceo"];
const EMAIL_FAVORITES = ["management@example.com"];

type PolicyPreset = {
  label: string;
  evaluationIntervalMinutes: string;
  windowMinutes: string;
  cooldownMinutes: string;
  maxTriggersPerDay?: string | null;
};

const POLICY_PRESETS: PolicyPreset[] = [
  {
    label: "빠른 감지",
    evaluationIntervalMinutes: "5",
    windowMinutes: "60",
    cooldownMinutes: "10",
    maxTriggersPerDay: "40",
  },
  {
    label: "표준",
    evaluationIntervalMinutes: "30",
    windowMinutes: "240",
    cooldownMinutes: "30",
    maxTriggersPerDay: "20",
  },
  {
    label: "조용하게",
    evaluationIntervalMinutes: "60",
    windowMinutes: "1440",
    cooldownMinutes: "120",
    maxTriggersPerDay: "5",
  },
];

const formatMinutesToText = (value: string | number | null | undefined): string | null => {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const numeric = typeof value === "string" ? Number(value) : Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return null;
  }
  if (numeric % 1440 === 0) {
    const days = numeric / 1440;
    return days === 1 ? "1일" : `${days}일`;
  }
  if (numeric >= 60) {
    const hours = Math.floor(numeric / 60);
    const minutes = numeric % 60;
    if (minutes === 0) {
      return hours === 1 ? "1시간" : `${hours}시간`;
    }
    return `${hours}시간 ${minutes}분`;
  }
  return `${numeric}분`;
};

const formatDailyLimitSummary = (value: string | null | undefined): string => {
  const trimmed = value ? value.trim() : "";
  if (!trimmed) {
    return "제한 없음";
  }
  const numeric = Number(trimmed);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return "제한 없음";
  }
  return `하루 최대 ${numeric}회`;
};

const CHANNEL_TYPE_OPTIONS: Array<{ value: AlertChannelType; label: string }> = [
  { value: "slack", label: "Slack" },
  { value: "email", label: "Email" },
  { value: "telegram", label: "Telegram" },
  { value: "webhook", label: "Webhook" },
  { value: "pagerduty", label: "PagerDuty" },
];

const CONDITION_TYPE_OPTIONS: Array<{ value: AlertCondition["type"]; label: string }> = [
  { value: "news", label: "뉴스" },
  { value: "filing", label: "공시" },
];

const STEP_COPY: Array<{ title: string; description: string }> = [
  { title: "기본 정보", description: "룰 이름과 목적을 입력하세요." },
  { title: "조건 설정", description: "모니터링할 기업, 섹터, 임계값을 지정하세요." },
  { title: "채널 · 검토", description: "전송 채널을 선택하고 전체 구성을 확인하세요." },
];

const getChannelLabelPlaceholder = (type: AlertChannelType) => {
  switch (type) {
    case "email":
      return "예: 재무팀 메일링 리스트";
    case "slack":
      return "예: #watchlist-alerts";
    case "telegram":
      return "예: 경영진 텔레그램";
    case "webhook":
      return "예: 외부 웹훅";
    case "pagerduty":
      return "예: 온콜 담당자";
    default:
      return "채널 이름";
  }
};

const getChannelTargetPlaceholder = (type: AlertChannelType) => {
  switch (type) {
    case "email":
      return "예: finance-team@example.com";
    case "slack":
      return "예: #alerts 또는 @username";
    case "telegram":
      return "예: @finance_ops_bot";
    case "webhook":
      return "예: https://hooks.slack.com/...";
    case "pagerduty":
      return "PagerDuty 통합 키";
    default:
      return "전송 대상을 입력하세요";
  }
};

const createChannelDraft = (type: AlertChannelType = "slack"): ChannelDraft => ({
  id: crypto.randomUUID(),
  type,
  label: "",
  target: "",
  targets: [],
  template: "",
});

const extractDraftFromRule = (rule?: WatchlistRuleDetail | null): RuleDraft => {
  if (!rule) {
    return { ...DEFAULT_RULE_DRAFT };
  }

  return {
    name: rule.name ?? "",
    description: rule.description ?? "",
    conditionType: (rule.condition.type as AlertCondition["type"]) ?? "news",
    tickers: Array.isArray(rule.condition.tickers) ? rule.condition.tickers : [],
    sectors: Array.isArray(rule.condition.sectors) ? rule.condition.sectors : [],
    categories: Array.isArray(rule.condition.categories) ? rule.condition.categories : [],
    minSentiment:
      rule.condition.minSentiment !== null && rule.condition.minSentiment !== undefined
        ? String(rule.condition.minSentiment)
        : "",
    evaluationIntervalMinutes: rule.evaluationIntervalMinutes ? String(rule.evaluationIntervalMinutes) : "60",
    windowMinutes: rule.windowMinutes ? String(rule.windowMinutes) : "1440",
    cooldownMinutes: rule.cooldownMinutes ? String(rule.cooldownMinutes) : "60",
    maxTriggersPerDay:
      rule.maxTriggersPerDay !== null && rule.maxTriggersPerDay !== undefined ? String(rule.maxTriggersPerDay) : "",
    channels: (rule.channels ?? []).map((channel) => ({
      id: crypto.randomUUID(),
      type: (channel.type as AlertChannelType) ?? "slack",
      label: channel.label ?? "",
      target: channel.target ?? channel.targets?.[0] ?? "",
      targets: Array.isArray(channel.targets)
        ? channel.targets.filter((value) => typeof value === "string" && value.trim().length > 0)
        : [],
      template: "",
    })),
    messageTemplate:
      typeof (rule as Record<string, unknown>).messageTemplate === "string"
        ? String((rule as Record<string, unknown>).messageTemplate)
        : "",
  };
};

const normalizeList = (values: string[]) =>
  Array.from(new Set(values.map((value) => value.trim()).filter((value) => value.length > 0)));

const normalizeChannelTargets = (values: string[]) =>
  Array.from(
    new Set(
      values
        .map((value) => value.trim())
        .filter((value) => value.length > 0),
    ),
  );

const toNumberOrNull = (value: string) => {
  if (!value) {
    return null;
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return null;
  }
  return parsed;
};

const buildConditionPayload = (draft: RuleDraft): AlertCondition => {
  const base: AlertCondition = {
    type: draft.conditionType,
    tickers: normalizeList(draft.tickers),
    categories: normalizeList(draft.categories),
    sectors: normalizeList(draft.sectors),
  };

  if (draft.conditionType === "news") {
    return {
      ...base,
      minSentiment: toNumberOrNull(draft.minSentiment),
    };
  }

  return base;
};

const sanitizeChannelDraft = (channel: ChannelDraft): AlertChannel | null => {
  const candidates = [
    channel.target?.trim() ?? "",
    ...channel.targets.map((value) => value.trim()),
  ].filter((value) => value.length > 0);
  if (candidates.length === 0) {
    return null;
  }
  const [primary, ...rest] = Array.from(new Set(candidates));
  return {
    type: channel.type,
    target: primary,
    targets: rest.length > 0 ? rest : [],
    label: channel.label.trim() || undefined,
    template: channel.template.trim() || undefined,
    metadata: {},
  };
};

const buildChannelsPayload = (draft: RuleDraft): AlertChannel[] =>
  draft.channels
    .map(sanitizeChannelDraft)
    .filter((channel): channel is AlertChannel => channel !== null);

const parsePositiveInt = (value: string, fallback: number) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }
  return Math.round(parsed);
};

const parseNonNegativeInt = (value: string, fallback: number) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return fallback;
  }
  return Math.round(parsed);
};

const parseOptionalPositiveInt = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  const digitsOnly = trimmed.replace(/\D+/g, "");
  if (!digitsOnly) {
    return undefined;
  }
  const parsed = Number(digitsOnly);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return undefined;
  }
  return Math.round(parsed);
};

const buildCreatePayload = (draft: RuleDraft): AlertRuleCreatePayload => ({
  name: draft.name.trim(),
  description: draft.description.trim() || undefined,
  condition: buildConditionPayload(draft),
  channels: buildChannelsPayload(draft),
  messageTemplate: draft.messageTemplate.trim() || undefined,
  evaluationIntervalMinutes: parsePositiveInt(draft.evaluationIntervalMinutes, 60),
  windowMinutes: parsePositiveInt(draft.windowMinutes, 1440),
  cooldownMinutes: parseNonNegativeInt(draft.cooldownMinutes, 60),
  maxTriggersPerDay: parseOptionalPositiveInt(draft.maxTriggersPerDay),
  extras: {},
});

const buildUpdatePayload = (draft: RuleDraft): AlertRuleUpdatePayload => ({
  name: draft.name.trim() || undefined,
  description: draft.description.trim() || undefined,
  condition: buildConditionPayload(draft),
  channels: buildChannelsPayload(draft),
  messageTemplate: draft.messageTemplate.trim() || undefined,
  evaluationIntervalMinutes: parsePositiveInt(draft.evaluationIntervalMinutes, 60),
  windowMinutes: parsePositiveInt(draft.windowMinutes, 1440),
  cooldownMinutes: parseNonNegativeInt(draft.cooldownMinutes, 60),
  maxTriggersPerDay: parseOptionalPositiveInt(draft.maxTriggersPerDay),
  extras: {},
});
type WatchlistRuleWizardProps = {
  open: boolean;
  mode?: WizardMode;
  initialRule?: WatchlistRuleDetail | null;
  onClose: () => void;
  onCompleted?: (rule: AlertRule) => void;
};

export function WatchlistRuleWizard({
  open,
  mode = "create",
  initialRule,
  onClose,
  onCompleted,
}: WatchlistRuleWizardProps) {
  const showToast = useToastStore((state) => state.show);

  const createMutation = useCreateAlertRule();
  const updateMutation = useUpdateAlertRule();

  const [step, setStep] = useState<WizardStep>(0);
  const [draft, setDraft] = useState<RuleDraft>(() => extractDraftFromRule(initialRule));
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!open) {
      return;
    }
    setStep(0);
    setError(null);
    setDraft(extractDraftFromRule(initialRule));
  }, [open, initialRule]);

  const isEditing = mode === "edit" && Boolean(initialRule?.id);
  const totalSteps = STEP_COPY.length;
  const activeStep = STEP_COPY[step];
  const isLastStep = step === totalSteps - 1;

  const canProceed = useMemo(() => {
    if (step === 0) {
      return draft.name.trim().length >= 2;
    }
    if (step === 1) {
      const hasTicker = draft.tickers.length > 0;
      const hasSector = draft.sectors.length > 0;
      if (!hasTicker && !hasSector) {
        return false;
      }
      if (draft.conditionType === "news" && draft.minSentiment) {
        return !Number.isNaN(Number(draft.minSentiment));
      }
      return true;
    }
    if (step === 2) {
      return draft.channels.length > 0 && draft.channels.every((channel) => channel.target.trim().length > 0);
    }
    return true;
  }, [draft, step]);

  const handleUpdateDraft = <Key extends keyof RuleDraft>(key: Key, value: RuleDraft[Key]) => {
    setDraft((prev) => ({
      ...prev,
      [key]: Array.isArray(value) ? [...value] : value,
    }));
  };

  const handleRemoveChannel = (id: string) => {
    setDraft((prev) => ({
      ...prev,
      channels: prev.channels.filter((channel) => channel.id !== id),
    }));
  };

  const handleChangeChannel = (id: string, patch: Partial<ChannelDraft>) => {
    setDraft((prev) => ({
      ...prev,
      channels: prev.channels.map((channel) => (channel.id === id ? { ...channel, ...patch } : channel)),
    }));
  };

  const summarizedTickers = normalizeList(draft.tickers);
  const summarizedSectors = normalizeList(draft.sectors);
  const summarizedCategories = normalizeList(draft.categories);

  const slackChannel = useMemo(
    () => draft.channels.find((channel) => channel.type === "slack"),
    [draft.channels],
  );
  const emailChannel = useMemo(
    () => draft.channels.find((channel) => channel.type === "email"),
    [draft.channels],
  );
  const auxiliaryChannels = useMemo(
    () => draft.channels.filter((channel) => channel.type !== "slack" && channel.type !== "email"),
    [draft.channels],
  );

  const handleApplyPolicyPreset = useCallback((preset: PolicyPreset) => {
    setDraft((prev) => ({
      ...prev,
      evaluationIntervalMinutes: preset.evaluationIntervalMinutes,
      windowMinutes: preset.windowMinutes,
      cooldownMinutes: preset.cooldownMinutes,
      maxTriggersPerDay: preset.maxTriggersPerDay ?? "",
    }));
  }, []);

  const matchedPolicyPreset = useMemo(() => {
    const normalizedLimit = (draft.maxTriggersPerDay ?? "").trim();
    return (
      POLICY_PRESETS.find((preset) => {
        const presetLimit = (preset.maxTriggersPerDay ?? "").trim();
        return (
          preset.evaluationIntervalMinutes === draft.evaluationIntervalMinutes &&
          preset.windowMinutes === draft.windowMinutes &&
          preset.cooldownMinutes === draft.cooldownMinutes &&
          presetLimit === normalizedLimit
        );
      }) ?? null
    );
  }, [
    draft.cooldownMinutes,
    draft.evaluationIntervalMinutes,
    draft.maxTriggersPerDay,
    draft.windowMinutes,
  ]);

  const policyPresetName = matchedPolicyPreset?.label ?? "사용자 지정";

  const evaluationRaw = draft.evaluationIntervalMinutes.trim();
  const windowRaw = draft.windowMinutes.trim();
  const cooldownRaw = draft.cooldownMinutes.trim();
  const dailyLimitRaw = draft.maxTriggersPerDay.trim();

  const evaluationDisplay =
    formatMinutesToText(evaluationRaw || DEFAULT_RULE_DRAFT.evaluationIntervalMinutes) ??
    `${evaluationRaw || DEFAULT_RULE_DRAFT.evaluationIntervalMinutes}분`;
  const windowDisplay =
    formatMinutesToText(windowRaw || DEFAULT_RULE_DRAFT.windowMinutes) ??
    `${windowRaw || DEFAULT_RULE_DRAFT.windowMinutes}분`;
  const cooldownDisplay =
    cooldownRaw === "0"
      ? "즉시 재발송"
      : formatMinutesToText(cooldownRaw || DEFAULT_RULE_DRAFT.cooldownMinutes) ??
        `${cooldownRaw || DEFAULT_RULE_DRAFT.cooldownMinutes}분`;
  const evaluationWindowSummary = `평가 ${evaluationDisplay}${evaluationRaw ? "" : " (기본)"} · 관찰 ${windowDisplay}${
    windowRaw ? "" : " (기본)"
  }`;
  const cooldownSummary =
    cooldownRaw === "0"
      ? "즉시 재발송"
      : `${cooldownDisplay}${cooldownRaw ? "" : " (기본)"}`;
  const dailyLimitSummary = formatDailyLimitSummary(dailyLimitRaw);

  const channelSummary = useMemo(() => {
    if (draft.channels.length === 0) {
      return "선택된 채널 없음";
    }
    const labelMap = new Map(CHANNEL_TYPE_OPTIONS.map((option) => [option.value, option.label]));
    const labels = Array.from(
      new Set(draft.channels.map((channel) => labelMap.get(channel.type) ?? channel.type)),
    );
    return labels.join(", ");
  }, [draft.channels]);

  const handleChannelToggle = useCallback((type: AlertChannelType, enabled: boolean) => {
    setDraft((prev) => {
      const existing = prev.channels.filter((channel) => channel.type === type);
      if (enabled) {
        if (existing.length > 0) {
          return prev;
        }
        return {
          ...prev,
          channels: [...prev.channels, createChannelDraft(type)],
        };
      }
      if (existing.length === 0) {
        return prev;
      }
      return {
        ...prev,
        channels: prev.channels.filter((channel) => channel.type !== type),
      };
    });
  }, []);

  const handleChannelLabelChange = useCallback((type: AlertChannelType, value: string) => {
    setDraft((prev) => ({
      ...prev,
      channels: prev.channels.map((channel) =>
        channel.type === type
          ? {
              ...channel,
              label: value,
            }
          : channel,
      ),
    }));
  }, []);

  const handleChannelTargetsChange = useCallback((type: AlertChannelType, values: string[]) => {
    const normalized = normalizeChannelTargets(values);
    setDraft((prev) => ({
      ...prev,
      channels: prev.channels.map((channel) =>
        channel.type === type
          ? {
              ...channel,
              target: normalized[0] ?? "",
              targets: normalized.slice(1),
            }
          : channel,
      ),
    }));
  }, []);

  const handleChannelTemplateChange = useCallback((type: AlertChannelType, value: string) => {
    setDraft((prev) => ({
      ...prev,
      channels: prev.channels.map((channel) =>
        channel.type === type
          ? {
              ...channel,
              template: value,
            }
          : channel,
      ),
    }));
  }, []);

  const handleAddAuxiliaryChannel = useCallback(() => {
    setDraft((prev) => ({
      ...prev,
      channels: [...prev.channels, createChannelDraft("webhook")],
    }));
  }, []);

  const renderStep = () => {
    switch (step) {
      case 0:
        return (
          <div className="space-y-6">
            <div className="space-y-2">
              <label className="block text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                룰 이름<span className="ml-1 text-primary">*</span>
              </label>
              <input
                type="text"
                value={draft.name}
                onChange={(event) => handleUpdateDraft("name", event.target.value)}
                placeholder="예: 금융주 뉴스 급등 모니터링"
                className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
              />
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                워치리스트와 알림에 그대로 노출되니 명확하게 작성해 주세요.
              </p>
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">설명</label>
              <textarea
                value={draft.description}
                onChange={(event) => handleUpdateDraft("description", event.target.value)}
                rows={3}
                placeholder="룰이 감시하는 조건과 활용 목적을 자유롭게 적어 주세요."
                className="w-full resize-none rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
              />
            </div>
          </div>
        );
      case 1:
        return (
          <div className="space-y-6">
            <div className="space-y-3">
              <span className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                감지 유형
              </span>
              <div className="flex flex-wrap gap-2">
                {CONDITION_TYPE_OPTIONS.map((option) => (
                  <FilterChip
                    key={option.value}
                    active={draft.conditionType === option.value}
                    onClick={() => handleUpdateDraft("conditionType", option.value)}
                  >
                    {option.label}
                  </FilterChip>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                기업 / 티커
              </label>
              <CompanyTickerInput
                values={draft.tickers}
                onChange={(next) => handleUpdateDraft("tickers", next)}
                placeholder="예: 삼성전자, 현대차"
                aria-label="기업 티커 입력"
                helperText="기업명을 입력해도 자동으로 티커가 매핑돼요. 쉼표로 여러 개를 추가할 수 있습니다."
              />
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                섹터 / 산업군
              </label>
              <TagInput
                values={draft.sectors}
                onChange={(next) => handleUpdateDraft("sectors", next)}
                placeholder="예: 반도체, 자동차"
                aria-label="섹터 태그 입력"
              />
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                분류가 애매하면 비워 두어도 괜찮아요. 필요할 때 다시 수정할 수 있습니다.
              </p>
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                관심 키워드
              </label>
              <TagInput
                values={draft.categories}
                onChange={(next) => handleUpdateDraft("categories", next)}
                placeholder="예: M&A, 실적"
                aria-label="키워드 태그 입력"
              />
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                뉴스/공시 필터링에 사용돼요. 핵심 키워드를 위주로 입력해 주세요.
              </p>
            </div>

            {draft.conditionType === "news" ? (
              <div className="space-y-2">
                <label className="block text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                  감성 임계값
                </label>
                <input
                  type="number"
                  step={0.05}
                  min={-1}
                  max={1}
                  value={draft.minSentiment}
                  onChange={(event) => handleUpdateDraft("minSentiment", event.target.value)}
                  placeholder="?: -0.30"
                  className="w-32 rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                />
                <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  해당 값 이상(또는 이하)의 감성 점수만 수신합니다.
                </p>
              </div>
            ) : null}
          </div>
        );
      case 2:
        return (
          <div className="space-y-6">
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
              <div className="space-y-4 rounded-2xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="space-y-1">
                    <h3 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">전송 정책</h3>
                    <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                      알림이 얼마나 자주 평가되고 발송될지 숫자로 조정하세요. 필요하면 언제든지 다시 바꿀 수 있습니다.
                    </p>
                  </div>
                  <span className="inline-flex items-center rounded-full bg-border-light px-3 py-1 text-xs font-semibold text-text-secondaryLight dark:bg-border-dark dark:text-text-secondaryDark">
                    {policyPresetName}
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {POLICY_PRESETS.map((preset) => (
                    <FilterChip
                      key={preset.label}
                      active={matchedPolicyPreset?.label === preset.label}
                      onClick={() => handleApplyPolicyPreset(preset)}
                    >
                      {preset.label}
                    </FilterChip>
                  ))}
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <label className="block text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                      평가 주기
                    </label>
                    <div className="relative">
                      <input
                        type="number"
                        min={1}
                        step={1}
                        inputMode="numeric"
                        value={draft.evaluationIntervalMinutes}
                        onChange={(event) => handleUpdateDraft("evaluationIntervalMinutes", event.target.value)}
                        placeholder="예: 30"
                        className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 pr-10 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                      />
                      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-text-tertiaryLight dark:text-text-tertiaryDark">
                        분
                      </span>
                    </div>
                    <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                      감지 조건을 얼마나 자주 확인할지 결정합니다.
                    </p>
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                      관찰 창
                    </label>
                    <div className="relative">
                      <input
                        type="number"
                        min={5}
                        step={5}
                        inputMode="numeric"
                        value={draft.windowMinutes}
                        onChange={(event) => handleUpdateDraft("windowMinutes", event.target.value)}
                        placeholder="예: 1440"
                        className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 pr-10 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                      />
                      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-text-tertiaryLight dark:text-text-tertiaryDark">
                        분
                      </span>
                    </div>
                    <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                      최근 데이터를 얼마나 길게 모아볼지 정합니다.
                    </p>
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                      쿨다운
                    </label>
                    <div className="relative">
                      <input
                        type="number"
                        min={0}
                        step={5}
                        inputMode="numeric"
                        value={draft.cooldownMinutes}
                        onChange={(event) => handleUpdateDraft("cooldownMinutes", event.target.value)}
                        placeholder="예: 60"
                        className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 pr-10 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                      />
                      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-text-tertiaryLight dark:text-text-tertiaryDark">
                        분
                      </span>
                    </div>
                    <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                      한 번 전송된 뒤 다음 알림까지 기다릴 최소 시간입니다.
                    </p>
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                      일일 한도
                    </label>
                    <div className="flex items-center gap-2">
                      <div className="relative flex-1">
                        <input
                          type="number"
                          min={0}
                          step={1}
                          inputMode="numeric"
                          value={draft.maxTriggersPerDay}
                          onChange={(event) => handleUpdateDraft("maxTriggersPerDay", event.target.value)}
                          placeholder="예: 20"
                          className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 pr-10 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                        />
                        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-text-tertiaryLight dark:text-text-tertiaryDark">
                          회
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleUpdateDraft("maxTriggersPerDay", "")}
                        className="shrink-0 rounded-full border border-border-light px-2.5 py-1 text-xs font-semibold text-text-secondaryLight transition hover:border-primary/40 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark/40 dark:hover:text-primary.dark"
                      >
                        무제한
                      </button>
                    </div>
                    <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                      비워 두면 하루 동안 횟수 제한 없이 발송합니다.
                    </p>
                  </div>
                </div>
              </div>
              <div className="space-y-4">
                <div className="space-y-3 rounded-2xl border border-border-light bg-background-cardLight p-4 dark:border-border-dark dark:bg-background-cardDark">
                  <h3 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">조건 요약</h3>
                  <div className="space-y-2">
                    <SummaryRow
                      label="기업"
                      value={summarizedTickers.length > 0 ? summarizedTickers.join(", ") : "선택된 기업 없음"}
                    />
                    <SummaryRow
                      label="섹터"
                      value={summarizedSectors.length > 0 ? summarizedSectors.join(", ") : "선택된 섹터 없음"}
                    />
                    <SummaryRow
                      label="키워드"
                      value={summarizedCategories.length > 0 ? summarizedCategories.join(", ") : "선택된 키워드 없음"}
                    />
                  </div>
                </div>
                <div className="space-y-3 rounded-2xl border border-border-light bg-background-cardLight p-4 dark:border-border-dark dark:bg-background-cardDark">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">정책 요약</h3>
                    <span className="text-xs font-semibold text-text-secondaryLight dark:text-text-secondaryDark">
                      {policyPresetName}
                    </span>
                  </div>
                  <div className="space-y-2">
                    <SummaryRow label="채널" value={channelSummary} />
                    <SummaryRow label="평가 · 관찰" value={evaluationWindowSummary} />
                    <SummaryRow label="쿨다운" value={cooldownSummary} />
                    <SummaryRow label="일일 한도" value={dailyLimitSummary} />
                  </div>
                </div>
              </div>
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <PrimaryChannelCard
                title="Slack"
                description="슬랙 채널이나 사용자에게 바로 전달합니다."
                icon={Slack}
                channel={slackChannel ?? null}
                enabled={Boolean(slackChannel)}
                labelPlaceholder={getChannelLabelPlaceholder("slack")}
                targetPlaceholder={getChannelTargetPlaceholder("slack")}
                helperText="예: #alerts, @finance_ops 등 하나 이상의 채널이나 사용자를 입력하세요."
                favoriteTargets={SLACK_FAVORITES}
                normalizeTarget={(value) => value.replace(/\s+/g, "")}
                onToggle={(enabled) => handleChannelToggle("slack", enabled)}
                onLabelChange={(value) => handleChannelLabelChange("slack", value)}
                onTargetsChange={(values) => handleChannelTargetsChange("slack", values)}
                onTemplateChange={(value) => handleChannelTemplateChange("slack", value)}
              />
              <PrimaryChannelCard
                title="Email"
                description="지정한 메일 주소로 알림을 동시에 발송합니다."
                icon={Mail}
                channel={emailChannel ?? null}
                enabled={Boolean(emailChannel)}
                labelPlaceholder={getChannelLabelPlaceholder("email")}
                targetPlaceholder={getChannelTargetPlaceholder("email")}
                helperText="쉼표 없이 한 주소씩 입력하세요. 여러 주소는 엔터로 구분할 수 있습니다."
                favoriteTargets={EMAIL_FAVORITES}
                normalizeTarget={(value) => value.replace(/\s+/g, "").toLowerCase()}
                onToggle={(enabled) => handleChannelToggle("email", enabled)}
                onLabelChange={(value) => handleChannelLabelChange("email", value)}
                onTargetsChange={(values) => handleChannelTargetsChange("email", values)}
                onTemplateChange={(value) => handleChannelTemplateChange("email", value)}
              />
            </div>

            <button
              type="button"
              onClick={handleAddAuxiliaryChannel}
              className="inline-flex items-center gap-2 rounded-lg border border-dashed border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition hover:border-primary/40 hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark/40 dark:hover:text-primary.dark"
            >
              <Plus className="h-3.5 w-3.5" aria-hidden />
              기타 채널 추가
            </button>

            {auxiliaryChannels.length > 0 ? (
              <div className="space-y-3 rounded-2xl border border-border-light bg-background-cardLight p-4 dark:border-border-dark dark:bg-background-cardDark">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">추가 채널</h3>
                  <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                    기존에 설정해 둔 기타 채널이에요. 필요하다면 여기에서 수정하거나 삭제할 수 있습니다.
                  </p>
                </div>
                <div className="space-y-3">
                  {auxiliaryChannels.map((channel) => (
                    <div
                      key={channel.id}
                      className="space-y-3 rounded-xl border border-border-light bg-background-base p-3 dark:border-border-dark dark:bg-background-cardDark"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <select
                          value={channel.type}
                          onChange={(event) =>
                            handleChangeChannel(channel.id, {
                              type: event.target.value as AlertChannelType,
                            })
                          }
                          className="rounded-md border border-border-light bg-background-light px-2 py-1 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-dark dark:text-text-primaryDark"
                        >
                          {CHANNEL_TYPE_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          onClick={() => handleRemoveChannel(channel.id)}
                          className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-border-light text-text-secondaryLight transition hover:border-accent-negative/60 hover:text-accent-negative focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-negative/40 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-accent-negative/60 dark:hover:text-accent-negative"
                        >
                          <Trash2 className="h-4 w-4" aria-hidden />
                          <span className="sr-only">채널 삭제</span>
                        </button>
                      </div>
                      <div className="grid gap-3 md:grid-cols-2">
                        <div className="space-y-1">
                          <label className="block text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                            채널 이름
                          </label>
                          <input
                            type="text"
                            value={channel.label}
                            onChange={(event) =>
                              handleChangeChannel(channel.id, {
                                label: event.target.value,
                              })
                            }
                            placeholder={getChannelLabelPlaceholder(channel.type)}
                            className="w-full rounded-md border border-border-light bg-background-light px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-dark dark:text-text-primaryDark"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="block text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                            전송 대상
                          </label>
                          <input
                            type="text"
                            value={channel.target}
                            onChange={(event) =>
                              handleChangeChannel(channel.id, {
                                target: event.target.value,
                              })
                            }
                            placeholder={getChannelTargetPlaceholder(channel.type)}
                            className="w-full rounded-md border border-border-light bg-background-light px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-dark dark:text-text-primaryDark"
                          />
                        </div>
                      </div>
                      <div className="space-y-1">
                        <label className="block text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                          메시지 템플릿 (선택)
                        </label>
                        <textarea
                          value={channel.template}
                          onChange={(event) =>
                            handleChangeChannel(channel.id, {
                              template: event.target.value,
                            })
                          }
                          rows={3}
                          placeholder="예: {{ruleName}} 감지 건을 요약해 전달합니다."
                          className="w-full rounded-md border border-border-light bg-background-light px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-dark dark:text-text-primaryDark"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="space-y-2">
              <label className="block text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                알림 메시지 (선택)
              </label>
            <RichTextEditor
              value={draft.messageTemplate}
              onChange={(value) => handleUpdateDraft("messageTemplate", value)}
              placeholder="예: 오늘 감지된 소식을 팀과 나눕니다."
            />
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                다이제스트나 이메일 알림에 포함되는 소개 문구예요.
              </p>
            </div>
          </div>
        );
      default:
        return null;
    }
  };
  const handleNext = () => {
    if (!canProceed) {
      return;
    }
    setError(null);
    setStep((prev) => Math.min(prev + 1, totalSteps - 1) as WizardStep);
  };

  const handleBack = () => {
    setError(null);
    setStep((prev) => Math.max(prev - 1, 0) as WizardStep);
  };

  const resetWizard = () => {
    setStep(0);
    setError(null);
    setDraft(extractDraftFromRule(initialRule));
  };

  const handleClose = () => {
    if (isSubmitting) {
      return;
    }
    resetWizard();
    onClose();
  };

  const mutationLoading = isSubmitting || createMutation.isPending || updateMutation.isPending;

  const handleSubmit = async () => {
    if (!canProceed || mutationLoading) {
      return;
    }

    if (!isLastStep) {
      handleNext();
      return;
    }

    if (draft.channels.length === 0) {
      setError("저장하기 전에 전송 채널을 최소 한 개 이상 추가해 주세요.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      if (isEditing && initialRule?.id) {
        const payload = buildUpdatePayload(draft);
        const updated = await updateMutation.mutateAsync({ id: initialRule.id, payload });
        showToast({
          title: "워치리스트 룰이 수정됐어요.",
          message: "변경 사항이 즉시 반영됐습니다.",
          intent: "success",
        });
        onCompleted?.(updated);
      } else {
        const payload = buildCreatePayload(draft);
        const created = await createMutation.mutateAsync(payload);
        showToast({
          title: "새 워치리스트 룰을 만들었어요.",
          message: "워치리스트에서 곧바로 확인할 수 있어요.",
          intent: "success",
        });
        onCompleted?.(created);
      }
      resetWizard();
      onClose();
    } catch (cause) {
      const message =
        cause instanceof ApiError
          ? cause.message || "We could not process that request."
          : cause instanceof Error
            ? cause.message
            : "We could not process that request.";
      setError(message);
      showToast({
        title: "알림 룰을 저장하지 못했어요.",
        message,
        intent: "error",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const primaryButtonLabel = isLastStep ? (isEditing ? "변경사항 저장" : "룰 생성") : "다음 단계";

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          key="watchlist-wizard-root"
          className="fixed inset-0 z-50 flex items-center justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2, ease: [0.17, 0.67, 0.45, 1] }}
        >
          <motion.button
            type="button"
            aria-label="마법사 닫기"
            onClick={handleClose}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.div
            className="relative z-10 w-full max-w-3xl px-4 sm:px-6"
            initial={{ opacity: 0, scale: 0.96, y: 18 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 12 }}
            transition={{ duration: 0.22, ease: [0.17, 0.67, 0.45, 1] }}
          >
            <div className="flex flex-col gap-6 rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-2xl dark:border-border-dark dark:bg-background-cardDark">
              <header className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    {STEP_COPY.map((copy, index) => (
                      <span
                        key={copy.title}
                        className={clsx(
                          "rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide",
                          index === step
                            ? "bg-primary/15 text-primary dark:bg-primary.dark/20 dark:text-primary.dark"
                            : "bg-border-light text-text-secondaryLight dark:bg-border-dark dark:text-text-secondaryDark",
                        )}
                      >
                        STEP {index + 1}
                      </span>
                    ))}
                  </div>
                  <h2 className="text-2xl font-semibold text-text-primaryLight dark:text-text-primaryDark">
                    {activeStep.title}
                  </h2>
                  <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                    {activeStep.description}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleClose}
                  className="rounded-full border border-border-light p-2 text-text-secondaryLight transition hover:border-primary/50 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark/50 dark:hover:text-primary.dark"
                  aria-label="마법사 닫기"
                >
                  <X className="h-4 w-4" aria-hidden />
                </button>
              </header>

              {error ? (
                <div className="rounded-lg border border-accent-negative/40 bg-accent-negative/10 px-3 py-2 text-sm text-accent-negative">
                  {error}
                </div>
              ) : null}

              <div className="max-h-[60vh] overflow-y-auto pr-1">{renderStep()}</div>

              <footer className="flex flex-col gap-4 border-t border-border-light pt-4 dark:border-border-dark">
                <div className="flex items-center justify-between">
                  {step > 0 ? (
                    <button
                      type="button"
                      onClick={handleBack}
                      className="inline-flex items-center gap-2 rounded-lg border border-border-light px-3 py-1.5 text-sm font-semibold text-text-secondaryLight transition hover:border-primary/40 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark/40 dark:hover:text-primary.dark"
                      disabled={mutationLoading}
                    >
                      <ArrowLeft className="h-4 w-4" aria-hidden />
                      이전 단계
                    </button>
                  ) : (
                    <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                      {isEditing
                        ? "현재 저장된 설정을 불러왔어요. 필요한 부분만 수정해 주세요."
                        : "각 단계는 나중에 다시 돌아와도 자유롭게 수정할 수 있어요."}
                    </span>
                  )}

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={handleClose}
                      className="rounded-lg border border-border-light px-3 py-1.5 text-sm font-semibold text-text-secondaryLight transition hover:border-primary/30 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark/30 dark:hover:text-primary.dark"
                      disabled={mutationLoading}
                    >
                      취소
                    </button>
                    <button
                      type="button"
                      onClick={handleSubmit}
                      disabled={!canProceed || mutationLoading}
                      className={clsx(
                        "inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 disabled:cursor-not-allowed disabled:opacity-60",
                        "dark:bg-primary.dark dark:hover:bg-primary.dark/90 dark:focus-visible:ring-primary.dark/60",
                      )}
                    >
                      {mutationLoading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
                      {primaryButtonLabel}
                    </button>
                  </div>
                </div>
              </footer>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );

}

type PrimaryChannelCardProps = {
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  channel: ChannelDraft | null;
  enabled: boolean;
  labelPlaceholder: string;
  targetPlaceholder: string;
  helperText: string;
  favoriteTargets?: string[];
  normalizeTarget?: (value: string) => string;
  onToggle: (enabled: boolean) => void;
  onLabelChange: (value: string) => void;
  onTargetsChange: (values: string[]) => void;
  onTemplateChange: (value: string) => void;
};

const channelVariants = {
  enabled: { y: -2, scale: 1.01, boxShadow: "0 20px 40px rgba(59, 130, 246, 0.15)" },
  disabled: { y: 0, scale: 1, boxShadow: "0 8px 24px rgba(15, 23, 42, 0.12)" },
};

const PrimaryChannelCard = ({
  title,
  description,
  icon: Icon,
  channel,
  enabled,
  labelPlaceholder,
  targetPlaceholder,
  helperText,
  favoriteTargets,
  normalizeTarget,
  onToggle,
  onLabelChange,
  onTargetsChange,
  onTemplateChange,
}: PrimaryChannelCardProps) => {
  const normalizer = useMemo(
    () => (value: string) => {
      const trimmed = value.trim();
      if (!trimmed) {
        return "";
      }
      const processed = normalizeTarget ? normalizeTarget(trimmed) : trimmed;
      return processed.trim();
    },
    [normalizeTarget],
  );

  const normalizedTargets = useMemo(() => {
    const values = channel ? normalizeChannelTargets([channel.target, ...(channel.targets ?? [])]) : [];
    return values
      .map((value) => normalizer(value))
      .filter((value) => value.length > 0);
  }, [channel, normalizer]);

  const quickFavorites = useMemo(() => {
    if (!favoriteTargets || favoriteTargets.length === 0) {
      return [];
    }
    const map = new Map<string, string>();
    favoriteTargets.forEach((candidate) => {
      const normalized = normalizer(candidate);
      if (!normalized) {
        return;
      }
      if (!map.has(normalized)) {
        map.set(normalized, candidate);
      }
    });
    return Array.from(map.entries()).map(([normalized, label]) => ({ normalized, label }));
  }, [favoriteTargets, normalizer]);

  const handleQuickToggle = (candidate: string) => {
    const normalized = normalizer(candidate);
    if (!normalized) {
      return;
    }
    if (normalizedTargets.includes(normalized)) {
      onTargetsChange(normalizedTargets.filter((value) => value !== normalized));
    } else {
      onTargetsChange([...normalizedTargets, normalized]);
    }
  };

  const templateValue = channel?.template ?? "";
  const toggleLabel = enabled ? "활성" : "비활성";
  return (
    <motion.div
      layout
      initial={false}
      animate={enabled ? "enabled" : "disabled"}
      variants={channelVariants}
      transition={{ duration: 0.24, ease: [0.22, 0.61, 0.36, 1] }}
      className={clsx(
        "flex h-full flex-col rounded-2xl border bg-background-cardLight p-4 transition-all duration-200 dark:bg-background-cardDark",
        enabled
          ? "border-primary/40 shadow-card dark:border-primary.dark/40"
          : "border-border-light shadow-sm dark:border-border-dark",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary dark:bg-primary.dark/15 dark:text-primary.dark">
            <Icon className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">{title}</p>
            <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{description}</p>
          </div>
        </div>
        <motion.button
          type="button"
          onClick={() => onToggle(!enabled)}
          className={clsx(
            "inline-flex items-center gap-2 whitespace-nowrap rounded-full px-3 py-1 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50",
            enabled
              ? "bg-primary/15 text-primary hover:bg-primary/20 dark:bg-primary.dark/20 dark:text-primary.dark"
              : "bg-border-light text-text-secondaryLight hover:bg-border-light/80 dark:bg-border-dark dark:text-text-secondaryDark",
          )}
          aria-pressed={enabled}
          whileTap={{ scale: 0.92 }}
          whileHover={{ scale: 1.03 }}
        >
          {toggleLabel}
        </motion.button>
      </div>
      {enabled ? (
        <div className="mt-4 space-y-4">
          <div className="space-y-1">
            <label className="block text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
              채널 이름
            </label>
            <input
              type="text"
              value={channel?.label ?? ""}
              onChange={(event) => onLabelChange(event.target.value)}
              placeholder={labelPlaceholder}
              className="w-full rounded-md border border-border-light bg-background-light px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-dark dark:text-text-primaryDark"
            />
          </div>
          <div className="space-y-1">
            <label className="block text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
              전송 대상
            </label>
            <TagInput
              values={normalizedTargets}
              onChange={onTargetsChange}
              placeholder={targetPlaceholder}
              aria-label={`${title} 대상`}
              normalize={normalizer}
            />
            {quickFavorites.length > 0 ? (
              <div className="flex flex-wrap items-center gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">즐겨찾기</span>
                {quickFavorites.map(({ normalized, label }) => {
                  const active = normalizedTargets.includes(normalized);
                  return (
                    <FilterChip
                      key={`${label}-${normalized}`}
                      active={active}
                      onClick={() => handleQuickToggle(label)}
                      className="px-2 py-0.5 text-[11px]"
                    >
                      {label}
                    </FilterChip>
                  );
                })}
              </div>
            ) : null}
            <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{helperText}</p>
          </div>
          <div className="space-y-1">
            <label className="block text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
              채널별 메시지 (선택)
            </label>
            <textarea
              value={templateValue}
              onChange={(event) => onTemplateChange(event.target.value)}
              rows={3}
              placeholder="예: 새로 감지된 소식을 팀에 공유합니다."
              className="w-full rounded-md border border-border-light bg-background-light px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-dark dark:text-text-primaryDark"
            />
          </div>
        </div>
      ) : (
        <p className="mt-4 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          버튼을 눌러 {title} 알림을 켜면 대상과 메시지를 설정할 수 있어요.
        </p>
      )}
    </motion.div>
  );
};

type ToolbarButtonProps = {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  onClick: () => void;
};

const ToolbarButton = ({ icon: Icon, label, onClick }: ToolbarButtonProps) => (
  <button
    type="button"
    onMouseDown={(event) => event.preventDefault()}
    onClick={onClick}
    className="inline-flex h-8 w-8 items-center justify-center rounded-md text-text-secondaryLight transition hover:bg-border-light hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 dark:text-text-secondaryDark dark:hover:bg-border-dark"
  >
    <Icon className="h-4 w-4" aria-hidden />
    <span className="sr-only">{label}</span>
  </button>
);

type RichTextEditorProps = {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
};

const RichTextEditor = ({ value, onChange, placeholder }: RichTextEditorProps) => {
  const editorRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = editorRef.current;
    if (!el) {
      return;
    }
    const safeValue = value || "";
    if (safeValue === el.innerHTML) {
      return;
    }
    el.innerHTML = safeValue;
  }, [value]);

  const applyFormat = (command: string) => {
    if (typeof document === "undefined") {
      return;
    }
    document.execCommand(command, false);
    editorRef.current?.focus();
    handleInput();
  };

  const handleInput = () => {
    const el = editorRef.current;
    if (!el) {
      return;
    }
    onChange(el.innerHTML);
  };

  const isEmpty =
    !value || value.replace(/<[^>]+>/g, "").replace(/&nbsp;/g, "").trim().length === 0;

  return (
    <div className="rounded-lg border border-border-light bg-background-base shadow-sm dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex items-center gap-1 border-b border-border-light px-2 py-1 dark:border-border-dark">
        <ToolbarButton icon={Bold} label="굵게" onClick={() => applyFormat("bold")} />
        <ToolbarButton icon={Italic} label="기울임" onClick={() => applyFormat("italic")} />
        <ToolbarButton icon={List} label="글머리 목록" onClick={() => applyFormat("insertUnorderedList")} />
      </div>
      <div className="relative">
        <div
          ref={editorRef}
          contentEditable
          suppressContentEditableWarning
          onInput={handleInput}
          onBlur={handleInput}
          className="min-h-[140px] w-full rounded-b-lg px-3 py-3 text-sm text-text-primaryLight focus:outline-none dark:text-text-primaryDark"
        />
        {isEmpty && placeholder ? (
          <span className="pointer-events-none absolute left-3 top-3 text-sm text-text-tertiaryLight dark:text-text-tertiaryDark">
            {placeholder}
          </span>
        ) : null}
      </div>
    </div>
  );
};

type SummaryRowProps = {
  label: string;
  value: string;
};

const SummaryRow = ({ label, value }: SummaryRowProps) => (
  <div className="flex items-start gap-3">
    <CheckCircle2 className="mt-0.5 h-4 w-4 text-primary dark:text-primary.dark" aria-hidden />
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
        {label}
      </p>
      <p className="text-sm text-text-primaryLight dark:text-text-primaryDark">{value}</p>
    </div>
  </div>
);
