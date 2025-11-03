import type { Meta, StoryObj } from "@storybook/react";

import { ChannelCard } from "@/components/alerts/ChannelCard";
import type { ChannelConfigState } from "@/components/alerts/channelForm";
import type { ChannelValidationError } from "@/components/alerts/useChannelValidation";

type Story = StoryObj<typeof ChannelCard>;

const baseState = (overrides?: Partial<ChannelConfigState>): ChannelConfigState => ({
  enabled: true,
  input: "",
  targets: [],
  metadata: {},
  template: "default",
  ...overrides,
});

const meta: Meta<typeof ChannelCard> = {
  title: "Alerts/ChannelCard",
  component: ChannelCard,
  args: {
    channelKey: "email",
    channelType: "email",
    requiresTarget: true,
    ui: {
      placeholder: "팀 이메일 주소를 입력해주세요",
      helper: "예: alert@ko-finance.org, team@ko-finance.org",
      templateOptions: [
        { value: "default", label: "빠른 알림" },
        { value: "digest", label: "요약 모드" },
      ],
    },
    state: baseState({
      input: "alert@ko-finance.org",
      targets: ["alert@ko-finance.org"],
      metadata: { subject_template: "따끈한 소식을 전해요" },
      template: "digest",
    }),
    errors: undefined,
    onToggle: () => {},
    onTargetChange: () => {},
    onTemplateChange: () => {},
    onMetadataChange: () => {},
    autoFocusTarget: false,
    onAutoFocusHandled: () => {},
  },
  parameters: {
    layout: "centered",
  },
};

export default meta;

export const Email기본: Story = {
  name: "Email - 기본",
};

export const Slack검증오류: Story = {
  name: "Slack - URL 검증 오류",
  args: {
    channelKey: "slack",
    channelType: "slack",
    requiresTarget: true,
    ui: {
      placeholder: "https://hooks.slack.com/…",
      helper: "슬랙 채널 웹훅 주소를 붙여주세요",
      templateOptions: [
        { value: "default", label: "기본 카드" },
        { value: "blocks", label: "풍성한 카드" },
      ],
    },
    state: baseState({
      input: "not-a-valid-url",
      targets: ["not-a-valid-url"],
      metadata: { channel: "#ops-alerts" },
    }),
    errors: {
      targets: "올바른 URL을 입력해주세요.",
    } satisfies ChannelValidationError,
  },
};

export const PagerDuty토글: Story = {
  name: "PagerDuty - 토글 대기",
  args: {
    channelKey: "pagerduty",
    channelType: "pagerduty",
    requiresTarget: true,
    state: baseState({
      enabled: false,
      input: "",
      targets: [],
      metadata: { severity: "info" },
    }),
    ui: {
      placeholder: "Routing Key",
      helper: "PagerDuty 이벤트 라우팅 키를 붙여주세요",
      templateOptions: [{ value: "default", label: "기본 템플릿" }],
    },
    errors: undefined,
  },
};
