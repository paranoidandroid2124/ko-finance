import type { Meta, StoryObj } from "@storybook/react";
import { PlanLock } from "@/components/ui/PlanLock";

const meta: Meta<typeof PlanLock> = {
  title: "UI/PlanLock",
  component: PlanLock,
  parameters: {
    layout: "centered",
  },
  args: {
    requiredTier: "pro",
    currentTier: "free",
    description: "Pro 플랜으로 업그레이드하면 하이라이트, PDF 미리보기, 내보내기 기능을 사용할 수 있습니다.",
  },
};

export default meta;

type Story = StoryObj<typeof PlanLock>;

export const FreeUser: Story = {};

export const ProNeedsTeam: Story = {
  args: {
    requiredTier: "enterprise",
    currentTier: "pro",
    title: "Team 플랜 기능입니다.",
    description: "Slack/웹훅 알림, SLA 모니터링, 감사 로그는 Team(구 Enterprise) 전용 기능이에요.",
  },
};

export const WithCallToAction: Story = {
  args: {
    onUpgrade: (tier) => console.info(`[storybook] upgrade CTA clicked for ${tier}`),
    children: (
      <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
        CSV/ZIP 내보내기, 증거 차이 비교, 알림 채널 확장을 포함해 Pro 플랜에서 바로 시작할 수 있어요.
      </p>
    ),
  },
};
