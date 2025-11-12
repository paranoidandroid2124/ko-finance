import type { JSX } from "react";
import type { Meta, StoryObj } from "@storybook/react";

import { AlertBuilder } from "@/components/alerts/AlertBuilder";
import { createAlertRuleFixture, AlertStoryProviders, proPlanInfo, freePlanInfo, enterprisePlanInfo } from "@/testing/fixtures/alerts";
import type { AlertPlanInfo } from "@/lib/alertsApi";
import type { PlanTier } from "@/store/planStore";

type Story = StoryObj<typeof AlertBuilder>;

type StoryRenderer = () => JSX.Element;

const wrapWithProviders = (plan?: AlertPlanInfo) => {
  const tier = resolvePlanTier(plan);
  const Decorator = (StoryComponent: StoryRenderer) => (
    <AlertStoryProviders planTier={tier}>
      <div className="min-h-screen bg-surface-subtle px-8 py-10">
        <div className="mx-auto max-w-4xl rounded-xl border border-border-subtle bg-surface-base p-8 shadow-md">
          <StoryComponent />
        </div>
      </div>
    </AlertStoryProviders>
  );
  Decorator.displayName = "AlertBuilderStoryDecorator";
  return Decorator;
};

const resolvePlanTier = (plan?: AlertPlanInfo): PlanTier => {
  const tier = plan?.planTier;
  if (tier === "free" || tier === "starter" || tier === "pro" || tier === "enterprise") {
    return tier;
  }
  return "pro";
};

const meta: Meta<typeof AlertBuilder> = {
  title: "Alerts/AlertBuilder",
  component: AlertBuilder,
  parameters: {
    layout: "fullscreen",
  },
  decorators: [
    (StoryComponent, context) => wrapWithProviders(context.args?.plan as AlertPlanInfo | undefined)(() => (
      <StoryComponent />
    )),
  ],
  args: {
    existingCount: 3,
    onSuccess: () => console.info("규칙을 저장했어요."),
    onCancel: () => console.info("빌더를 닫을게요."),
  },
};

export default meta;

export const 기본_새규칙: Story = {
  name: "기본 설정 (Pro)",
  args: {
    plan: proPlanInfo,
  },
};

export const 편집모드: Story = {
  name: "편집 모드",
  args: {
    plan: proPlanInfo,
    mode: "edit",
    editingRule: createAlertRuleFixture({
      id: "rule-edit",
      name: "시장 공지 모니터링",
      channels: [
        {
          type: "email",
          targets: ["alerts@ko-finance.org"],
          metadata: { subject_template: "따끈따끈한 소식이에요" },
          template: "digest",
        },
        {
          type: "slack",
          target: "https://hooks.slack.com/services/demo",
          metadata: { channel: "#alerts-demo" },
          template: "blocks",
        },
      ],
    }),
  },
};

export const 플랜잠김: Story = {
  name: "Free 플랜 - 잠금 안내",
  args: {
    plan: { ...freePlanInfo, remainingAlerts: 0 },
    existingCount: 1,
  },
};

export const 채널제한: Story = {
  name: "Enterprise - 채널 확장",
  args: {
    plan: enterprisePlanInfo,
    existingCount: 6,
    mode: "duplicate",
    editingRule: createAlertRuleFixture({
      id: "rule-dup",
      name: "중요 뉴스 알림",
      channels: [
        {
          type: "pagerduty",
          target: undefined,
          targets: [],
          metadata: { severity: "info" },
          template: "default",
        },
        {
          type: "webhook",
          target: "https://alerts.ko-finance.org/webhook",
          template: "default",
        },
      ],
      condition: {
        type: "news",
        tickers: ["KOFC", "FINC"],
        sectors: ["finance"],
        categories: [],
        minSentiment: 0.1,
      },
    }),
  },
};
