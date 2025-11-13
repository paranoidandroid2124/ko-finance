import type { Meta, StoryObj } from "@storybook/react";

import { PlanSummaryCard } from "@/components/plan/PlanSummaryCard";
import { PlanAlertOverview } from "@/components/plan/PlanAlertOverview";
import type { PlanTier } from "@/store/planStore";
import {
  AlertStoryProviders,
  enterprisePlanInfo,
  freePlanInfo,
  starterPlanInfo,
  proPlanInfo,
} from "@/testing/fixtures/alerts";

type StoryArgs = {
  planTier: PlanTier;
};

const meta: Meta<StoryArgs> = {
  title: "Plan/Overview",
  parameters: {
    layout: "centered",
  },
  args: {
    planTier: "pro",
  },
  argTypes: {
    planTier: {
      control: { type: "radio" },
      options: ["free", "starter", "pro", "enterprise"],
    },
  },
};

export default meta;

type Story = StoryObj<StoryArgs>;

export const SummaryCard: Story = {
  render: ({ planTier }) => (
    <AlertStoryProviders planTier={planTier}>
      <div className="w-full max-w-xl">
        <PlanSummaryCard />
      </div>
    </AlertStoryProviders>
  ),
};

const planByTier: Record<PlanTier, typeof freePlanInfo> = {
  free: freePlanInfo,
  starter: starterPlanInfo,
  pro: proPlanInfo,
  enterprise: enterprisePlanInfo,
};

export const AlertLimits: Story = {
  render: ({ planTier }) => (
    <div className="w-full max-w-xl">
      <PlanAlertOverview plan={planByTier[planTier]} />
    </div>
  ),
};
