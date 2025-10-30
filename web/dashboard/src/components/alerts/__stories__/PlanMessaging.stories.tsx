import type { Meta, StoryObj } from "@storybook/react";
import { useMemo } from "react";

import { getPlanCopy, parsePlanTier } from "@/components/alerts/planMessaging";
import type { PlanTier } from "@/store/planStore";

type Props = {
  planTier: PlanTier;
  remaining: number;
  max: number;
};

const PlanMessagingPreview = ({ planTier, remaining, max }: Props) => {
  const copy = useMemo(() => getPlanCopy(parsePlanTier(planTier)), [planTier]);
  const quotaInfo = { remaining, max };

  return (
    <div className="flex flex-col gap-6 rounded-xl border border-border-subtle bg-surface-base p-6 shadow-sm">
      <section>
        <h3 className="text-base font-semibold text-text-primaryLight">빌더 메시지</h3>
        <p className="mt-2 text-sm text-text-secondaryLight">{copy.builder.disabledHint}</p>
        <p className="mt-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-700">
          <strong className="block font-semibold text-amber-800">{copy.builder.quotaToast.title}</strong>
          {copy.builder.quotaToast.description(quotaInfo)}
        </p>
        <p className="mt-2 rounded-md bg-indigo-50 px-3 py-2 text-sm text-indigo-700">
          {copy.builder.quotaBanner(quotaInfo)}
        </p>
        {copy.builder.lock ? (
          <div className="mt-3 rounded-md border border-dashed border-indigo-300 px-3 py-2 text-sm text-indigo-800">
            <strong className="block font-semibold">{copy.builder.lock.title}</strong>
            <span>{copy.builder.lock.description}</span>
          </div>
        ) : null}
      </section>

      <section>
        <h3 className="text-base font-semibold text-text-primaryLight">알림 벨 메시지</h3>
        <p className="mt-2 text-sm text-text-secondaryLight">{copy.bell.disabledHint}</p>
        <p className="mt-2 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">
          <strong className="block font-semibold text-rose-800">{copy.bell.quotaToast.title}</strong>
          {copy.bell.quotaToast.description(quotaInfo)}
        </p>
      </section>
    </div>
  );
};

const meta: Meta<typeof PlanMessagingPreview> = {
  title: "Alerts/PlanMessaging",
  component: PlanMessagingPreview,
  args: {
    planTier: "pro",
    remaining: 2,
    max: 10,
  },
  argTypes: {
    planTier: {
      options: ["free", "pro", "enterprise"],
      control: { type: "inline-radio" },
    },
    remaining: { control: { type: "number" } },
    max: { control: { type: "number" } },
  },
  parameters: {
    layout: "centered",
  },
};

export default meta;

type Story = StoryObj<typeof PlanMessagingPreview>;

export const Free티어: Story = {
  args: {
    planTier: "free",
    remaining: 0,
    max: 1,
  },
};

export const Pro티어: Story = {
  args: {
    planTier: "pro",
    remaining: 3,
    max: 10,
  },
};

export const Enterprise티어: Story = {
  args: {
    planTier: "enterprise",
    remaining: 20,
    max: 25,
  },
};

