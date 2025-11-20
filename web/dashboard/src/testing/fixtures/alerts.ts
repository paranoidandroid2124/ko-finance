import { createElement, useEffect, useRef, type PropsWithChildren } from "react";
import { QueryClientProvider } from "@tanstack/react-query";

import type { AlertPlanInfo, AlertRule, AlertChannel } from "@/lib/alertsApi";
import { createMockQueryClient } from "@/testing/queryClient";
import { usePlanStore, type PlanContextPayload, type PlanFeatureFlags, type PlanMemoryFlags, type PlanQuota } from "@/store/planStore";
import { useToastStore } from "@/store/toastStore";

type PlanTier = PlanContextPayload["planTier"];

const baseFeatureFlags: PlanFeatureFlags = {
  searchCompare: true,
  searchAlerts: false,
  searchExport: false,
  ragCore: false,
  evidenceInlinePdf: false,
  evidenceDiff: false,
  timelineFull: false,
  reportsEventExport: false,
};

const baseQuota: PlanQuota = {
  chatRequestsPerDay: 20,
  ragTopK: 5,
  selfCheckEnabled: true,
  peerExportRowLimit: 100,
};

export const freePlanInfo: AlertPlanInfo = {
  planTier: "free",
  maxAlerts: 1,
  remainingAlerts: 0,
  channels: ["email"],
  maxDailyTriggers: 1,
  defaultEvaluationIntervalMinutes: 15,
  defaultWindowMinutes: 120,
  defaultCooldownMinutes: 120,
  minEvaluationIntervalMinutes: 5,
  minCooldownMinutes: 30,
  frequencyDefaults: {
    evaluationIntervalMinutes: 15,
    windowMinutes: 120,
    cooldownMinutes: 120,
    maxTriggersPerDay: 1,
  },
  nextEvaluationAt: null,
};

export const proPlanInfo: AlertPlanInfo = {
  planTier: "pro",
  maxAlerts: 10,
  remainingAlerts: 7,
  channels: ["email", "slack", "webhook"],
  maxDailyTriggers: 6,
  defaultEvaluationIntervalMinutes: 5,
  defaultWindowMinutes: 60,
  defaultCooldownMinutes: 30,
  minEvaluationIntervalMinutes: 1,
  minCooldownMinutes: 5,
  frequencyDefaults: {
    evaluationIntervalMinutes: 5,
    windowMinutes: 60,
    cooldownMinutes: 30,
    maxTriggersPerDay: 6,
  },
  nextEvaluationAt: null,
};

export const starterPlanInfo: AlertPlanInfo = {
  ...proPlanInfo,
  planTier: "starter",
  maxAlerts: 4,
  remainingAlerts: 3,
  channels: ["email", "slack"],
  maxDailyTriggers: 3,
  defaultEvaluationIntervalMinutes: 10,
  defaultWindowMinutes: 90,
  defaultCooldownMinutes: 60,
  minEvaluationIntervalMinutes: 2,
  minCooldownMinutes: 10,
  frequencyDefaults: {
    evaluationIntervalMinutes: 10,
    windowMinutes: 90,
    cooldownMinutes: 60,
    maxTriggersPerDay: 3,
  },
};

export const enterprisePlanInfo: AlertPlanInfo = {
  planTier: "enterprise",
  maxAlerts: 25,
  remainingAlerts: 24,
  channels: ["email", "slack", "webhook", "pagerduty"],
  maxDailyTriggers: 12,
  defaultEvaluationIntervalMinutes: 2,
  defaultWindowMinutes: 30,
  defaultCooldownMinutes: 10,
  minEvaluationIntervalMinutes: 1,
  minCooldownMinutes: 0,
  frequencyDefaults: {
    evaluationIntervalMinutes: 2,
    windowMinutes: 30,
    cooldownMinutes: 10,
    maxTriggersPerDay: 12,
  },
  nextEvaluationAt: null,
};

export const sampleEmailChannel: AlertChannel = {
  type: "email",
  targets: ["team@nuvien.com"],
  metadata: {
    subject_template: "주요 변경 사항 요약",
  },
};

export const createAlertRuleFixture = (overrides?: Partial<AlertRule>): AlertRule => ({
  id: "alert-rule-1",
  name: "분기 보고서 구독",
  description: "주요 공시가 올라오면 알려드릴게요.",
  planTier: overrides?.planTier ?? "pro",
  status: "active",
  trigger: overrides?.trigger ?? {
    type: "filing",
    tickers: ["KOFC"],
    categories: ["10-Q"],
    sectors: [],
    minSentiment: null,
  },
  frequency:
    overrides?.frequency ??
    {
      evaluationIntervalMinutes: overrides?.evaluationIntervalMinutes ?? 5,
      windowMinutes: overrides?.windowMinutes ?? 60,
      cooldownMinutes: overrides?.cooldownMinutes ?? 30,
      maxTriggersPerDay: overrides?.maxTriggersPerDay ?? 5,
    },
  condition: overrides?.condition,
  channels: overrides?.channels ?? [sampleEmailChannel],
  messageTemplate: overrides?.messageTemplate ?? null,
  evaluationIntervalMinutes:
    overrides?.evaluationIntervalMinutes ?? overrides?.frequency?.evaluationIntervalMinutes ?? 5,
  windowMinutes: overrides?.windowMinutes ?? overrides?.frequency?.windowMinutes ?? 60,
  cooldownMinutes: overrides?.cooldownMinutes ?? overrides?.frequency?.cooldownMinutes ?? 30,
  maxTriggersPerDay:
    overrides?.maxTriggersPerDay ?? overrides?.frequency?.maxTriggersPerDay ?? 5,
  lastTriggeredAt: overrides?.lastTriggeredAt ?? null,
  lastEvaluatedAt: overrides?.lastEvaluatedAt ?? null,
  cooledUntil: overrides?.cooledUntil ?? null,
  throttleUntil: overrides?.throttleUntil ?? null,
  errorCount: overrides?.errorCount ?? 0,
  extras: overrides?.extras ?? {},
  createdAt: overrides?.createdAt ?? new Date().toISOString(),
  updatedAt: overrides?.updatedAt ?? new Date().toISOString(),
});

const makePlanContext = (tier: PlanTier): PlanContextPayload => {
  const searchExport = tier !== "free";
  const searchAlerts = tier !== "free";
  const ragCore = tier !== "free";
  const timelineFull = tier === "enterprise";
  const reportsEventExport = tier === "pro" || tier === "enterprise";
  const memoryFlags: PlanMemoryFlags = {
    watchlist: tier !== "free",
    chat: tier !== "free",
  };
  return {
    planTier: tier,
    expiresAt: null,
    entitlements: tier === "enterprise" ? ["alerts:pagerduty"] : [],
    featureFlags: {
      ...baseFeatureFlags,
      searchAlerts,
      searchExport,
      ragCore,
      timelineFull,
      reportsEventExport,
    },
    memoryFlags,
    quota: {
      ...baseQuota,
      peerExportRowLimit: tier === "enterprise" ? 500 : tier === "pro" ? 150 : 50,
    },
  };
};

export const resetAlertStores = () => {
  const planStore = usePlanStore.getState();
  planStore.setPlanFromServer(makePlanContext("free"));
  usePlanStore.setState({ initialized: false, loading: false, error: undefined });
  useToastStore.setState({ toasts: [] });
};

export const loadPlanContext = (tier: PlanTier) => {
  const planStore = usePlanStore.getState();
  planStore.setPlanFromServer(makePlanContext(tier));
  usePlanStore.setState({ initialized: true, loading: false, error: undefined });
};

export const AlertStoryProviders = ({
  planTier = "pro",
  children,
}: PropsWithChildren<{ planTier?: PlanTier }>) => {
  const clientRef = useRef(createMockQueryClient());

  useEffect(() => {
    resetAlertStores();
    loadPlanContext(planTier);
    return () => {
      resetAlertStores();
    };
  }, [planTier]);

  return createElement(QueryClientProvider, { client: clientRef.current }, children);
};
