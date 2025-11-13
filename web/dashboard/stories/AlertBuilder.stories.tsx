"use client";

import { useEffect, useMemo, useRef } from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AlertBuilder } from "../src/components/alerts/AlertBuilder";
import type { AlertPlanInfo, AlertRule } from "../src/lib/alertsApi";
import { usePlanStore, type PlanTier } from "../src/store/planStore";

type AlertBuilderStoryProps = {
  plan: AlertPlanInfo | null;
  existingCount: number;
  mode?: "create" | "edit" | "duplicate";
  editingRule?: AlertRule | null;
};

const makeQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
      },
    },
  });

const AlertBuilderStoryProvider = ({ plan, existingCount, mode = "create", editingRule }: AlertBuilderStoryProps) => {
  const queryClientRef = useRef<QueryClient>();
  if (!queryClientRef.current) {
    queryClientRef.current = makeQueryClient();
  }

  const storeSnapshot = useMemo(() => usePlanStore.getState(), []);

  useEffect(() => {
    const tier = (plan?.planTier ?? storeSnapshot.planTier) as PlanTier;
    usePlanStore.setState({ ...storeSnapshot, planTier: tier }, true);
    return () => {
      usePlanStore.setState(storeSnapshot, true);
    };
  }, [plan?.planTier, storeSnapshot]);

  return (
    <QueryClientProvider client={queryClientRef.current}>
      <div className="w-full max-w-3xl rounded-xl border border-border-light/70 bg-white/80 p-6 shadow-sm dark:border-border-dark/70 dark:bg-background-cardDark/80">
        <AlertBuilder
          plan={plan}
          existingCount={existingCount}
          mode={mode}
          editingRule={editingRule}
          onSuccess={() => undefined}
          onCancel={() => undefined}
        />
      </div>
    </QueryClientProvider>
  );
};

const meta: Meta<typeof AlertBuilder> = {
  title: "Alerts/AlertBuilder",
  component: AlertBuilder,
  parameters: {
    layout: "centered",
  },
  argTypes: {
    plan: { control: { type: "object" } },
    existingCount: { control: { type: "number" } },
    mode: {
      options: ["create", "edit", "duplicate"],
      control: { type: "select" },
    },
    editingRule: { control: { type: "object" } },
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

const basePlan: AlertPlanInfo = {
  planTier: "pro",
  maxAlerts: 10,
  remainingAlerts: 6,
  channels: ["email", "slack", "webhook"],
  maxDailyTriggers: 20,
  defaultEvaluationIntervalMinutes: 5,
  defaultWindowMinutes: 60,
  defaultCooldownMinutes: 30,
  minEvaluationIntervalMinutes: 1,
  minCooldownMinutes: 5,
  nextEvaluationAt: null,
  frequencyDefaults: {
    evaluationIntervalMinutes: 5,
    windowMinutes: 60,
    cooldownMinutes: 30,
    maxTriggersPerDay: 20,
  },
};

const freePlan: AlertPlanInfo = {
  ...basePlan,
  planTier: "free",
  maxAlerts: 0,
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
};

const proPlan: AlertPlanInfo = {
  ...basePlan,
  planTier: "pro",
};

const sampleRule: AlertRule = {
  id: "rule-1",
  name: "뉴스 급등 알림 - 삼성전자",
  description: "긍정 뉴스가 임계치를 넘으면 메일로 알립니다.",
  planTier: "pro",
  status: "active",
  condition: {
    type: "news",
    tickers: ["KRX:005930"],
    categories: [],
    sectors: [],
    minSentiment: 0.2,
  },
  trigger: {
    type: "news",
    tickers: ["KRX:005930"],
    categories: [],
    sectors: [],
    minSentiment: 0.2,
  },
  frequency: {
    evaluationIntervalMinutes: 10,
    windowMinutes: 60,
    cooldownMinutes: 30,
    maxTriggersPerDay: 5,
  },
  channels: [
    {
      type: "email",
      targets: ["alerts@example.com"],
      template: "default",
      metadata: { subject_template: "[K-Finance] 삼성전자 알림" },
    },
  ],
  messageTemplate: "default",
  evaluationIntervalMinutes: 10,
  windowMinutes: 60,
  cooldownMinutes: 30,
  maxTriggersPerDay: 5,
  lastTriggeredAt: null,
  lastEvaluatedAt: null,
  cooledUntil: null,
  throttleUntil: null,
  errorCount: 0,
  extras: {},
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
};

export const Default: Story = {
  render: (args) => <AlertBuilderStoryProvider {...(args as AlertBuilderStoryProps)} />,
  args: {
    plan: proPlan,
    existingCount: 2,
    mode: "create",
  },
};

export const FreePlanLocked: Story = {
  render: (args) => <AlertBuilderStoryProvider {...(args as AlertBuilderStoryProps)} />,
  args: {
    plan: freePlan,
    existingCount: 1,
    mode: "create",
  },
};

export const DuplicateExistingRule: Story = {
  render: (args) => <AlertBuilderStoryProvider {...(args as AlertBuilderStoryProps)} />,
  args: {
    plan: proPlan,
    existingCount: 4,
    mode: "duplicate",
    editingRule: sampleRule,
  },
};
