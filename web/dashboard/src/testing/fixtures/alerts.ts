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
  nextEvaluationAt: null,
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
  nextEvaluationAt: null,
};

export const sampleEmailChannel: AlertChannel = {
  type: "email",
  targets: ["team@ko-finance.org"],
  template: "digest",
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
  condition: {
    type: "filing",
    tickers: ["KOFC"],
    categories: ["10-Q"],
    sectors: [],
    minSentiment: null,
    ...overrides?.condition,
  },
  channels: overrides?.channels ?? [sampleEmailChannel],
  messageTemplate: overrides?.messageTemplate ?? null,
  evaluationIntervalMinutes: overrides?.evaluationIntervalMinutes ?? 5,
  windowMinutes: overrides?.windowMinutes ?? 60,
  cooldownMinutes: overrides?.cooldownMinutes ?? 30,
  maxTriggersPerDay: overrides?.maxTriggersPerDay ?? 5,
  lastTriggeredAt: overrides?.lastTriggeredAt ?? null,
  lastEvaluatedAt: overrides?.lastEvaluatedAt ?? null,
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
  const memoryFlags: PlanMemoryFlags = {
    watchlist: tier !== "free",
    digest: tier !== "free",
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
