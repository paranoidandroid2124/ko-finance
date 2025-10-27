import type { Meta, StoryObj } from "@storybook/react";
import { TimelineSparkline, type TimelineSparklinePoint } from "@/components/company/TimelineSparkline";

const BASE_POINTS: TimelineSparklinePoint[] = Array.from({ length: 14 }).map((_, index) => {
  const date = new Date();
  date.setDate(date.getDate() - (13 - index));
  return {
    date: date.toISOString().split("T")[0] ?? "",
    sentimentZ: Math.sin(index / 3) * 1.2,
    priceClose: 72000 + index * 420 - Math.pow(index - 7, 2) * 80,
    volume: 250000 + Math.max(0, 8 - Math.abs(index - 6)) * 35000,
    eventType: index === 6 ? "실적 발표" : undefined,
  };
});

const meta: Meta<typeof TimelineSparkline> = {
  title: "Company/TimelineSparkline",
  component: TimelineSparkline,
  parameters: {
    layout: "fullscreen",
  },
  args: {
    planTier: "pro",
    points: BASE_POINTS,
    showVolume: true,
    highlightDate: BASE_POINTS[6]?.date,
  },
};

export default meta;

type Story = StoryObj<typeof TimelineSparkline>;

export const Default: Story = {};

export const FreePlan: Story = {
  args: {
    planTier: "free",
    showVolume: false,
  },
};

export const Locked: Story = {
  args: {
    locked: true,
    planTier: "free",
  },
};

export const EmptyState: Story = {
  args: {
    points: [],
    planTier: "pro",
  },
};

