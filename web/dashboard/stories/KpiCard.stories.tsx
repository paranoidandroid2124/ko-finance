import type { Meta, StoryObj } from "@storybook/react";
import { KpiCard } from "../src/components/ui/KpiCard";

const meta: Meta<typeof KpiCard> = {
  title: "Dashboard/KpiCard",
  component: KpiCard,
  parameters: {
    layout: "centered"
  },
  argTypes: {
    trend: {
      control: { type: "select" },
      options: ["up", "down", "flat"]
    }
  }
};

export default meta;

type Story = StoryObj<typeof KpiCard>;

export const Default: Story = {
  args: {
    title: "공시 처리",
    value: "86건",
    delta: "+12%",
    trend: "up",
    description: "24시간 내 분석"
  }
};

