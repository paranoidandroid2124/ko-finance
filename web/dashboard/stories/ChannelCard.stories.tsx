import { useMemo, useState } from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { ChannelCard } from "../src/components/alerts/ChannelCard";
import type { AlertChannelType } from "../src/lib/alertsApi";
import type { ChannelConfigState } from "../src/components/alerts/channelForm";
import type { ChannelValidationError } from "../src/components/alerts/useChannelValidation";

type StatefulProps = {
  channelKey: string;
  channelType: AlertChannelType;
  state: ChannelConfigState;
  requiresTarget: boolean;
  ui?: {
    placeholder?: string;
    helper?: string;
    templateOptions?: Array<{ value: string; label: string }>;
  };
  errors?: ChannelValidationError;
};

const parseTargets = (value: string) =>
  value
    .split(/[\s,]+/)
    .map((item) => item.trim())
    .filter(Boolean);

const StatefulCard = (props: StatefulProps) => {
  const [state, setState] = useState<ChannelConfigState>(props.state);
  const templateOptions = useMemo(() => props.ui?.templateOptions ?? [{ value: "default", label: "기본" }], [props.ui]);

  return (
    <ChannelCard
      channelKey={props.channelKey}
      channelType={props.channelType}
      state={state}
      requiresTarget={props.requiresTarget}
      ui={{ placeholder: props.ui?.placeholder, helper: props.ui?.helper, templateOptions }}
      errors={props.errors}
      autoFocusTarget={false}
      onAutoFocusHandled={() => undefined}
      onToggle={(enabled) => setState((prev) => ({ ...prev, enabled }))}
      onTargetChange={(value) =>
        setState((prev) => ({
          ...prev,
          input: value,
          targets: parseTargets(value),
        }))
      }
      onTemplateChange={(value) => setState((prev) => ({ ...prev, template: value }))}
      onMetadataChange={(key, value) =>
        setState((prev) => ({
          ...prev,
          metadata: {
            ...prev.metadata,
            [key]: value,
          },
        }))
      }
    />
  );
};

const meta: Meta<typeof ChannelCard> = {
  title: "Alerts/ChannelCard",
  component: ChannelCard,
  parameters: {
    layout: "centered",
  },
};

export default meta;

type Story = StoryObj<StatefulProps>;

const baseEmailState: ChannelConfigState = {
  enabled: true,
  input: "alerts@example.com",
  targets: ["alerts@example.com"],
  template: "default",
  metadata: {
    subject_template: "새 알림: {message}",
    reply_to: "",
  },
};

export const EmailChannel: Story = {
  render: (args) => <StatefulCard {...args} />,
  args: {
    channelKey: "email",
    channelType: "email",
    requiresTarget: true,
    state: baseEmailState,
    ui: {
      helper: "쉼표나 줄바꿈으로 여러 이메일을 입력할 수 있어요.",
      templateOptions: [
        { value: "default", label: "기본" },
        { value: "digest", label: "요약" },
      ],
    },
  },
};

export const SlackChannelWithError: Story = {
  render: (args) => <StatefulCard {...args} />,
  args: {
    channelKey: "slack",
    channelType: "slack",
    requiresTarget: true,
    state: {
      enabled: true,
      input: "https://hooks.slack.com/services/INVALID",
      targets: ["https://hooks.slack.com/services/INVALID"],
      template: "default",
      metadata: {},
    },
    ui: {
      helper: "예: https://hooks.slack.com/services/T000/B000/XXXX",
      templateOptions: [
        { value: "default", label: "텍스트" },
        { value: "blocks", label: "블록 레이아웃" },
      ],
    },
    errors: {
      targets: "올바른 Slack Webhook URL을 입력해 주세요.",
    },
  },
};

export const PagerDutySeverity: Story = {
  render: (args) => <StatefulCard {...args} />,
  args: {
    channelKey: "pagerduty",
    channelType: "pagerduty",
    requiresTarget: true,
    state: {
      enabled: true,
      input: "aaaaaaaaaaaaaaaa",
      targets: ["aaaaaaaaaaaaaaaa"],
      template: "default",
      metadata: {
        severity: "warning",
      },
    },
    ui: {
      helper: "PagerDuty Event API v2 라우팅 키를 입력하세요.",
    },
  },
};
