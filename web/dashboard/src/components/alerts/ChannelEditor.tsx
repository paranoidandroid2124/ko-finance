"use client";

import { memo, useMemo } from "react";

import type { AlertChannelType } from "@/lib/alertsApi";
import { emptyChannelState, type ChannelState } from "@/components/alerts/channelForm";
import { ChannelCard } from "@/components/alerts/ChannelCard";
import type { ChannelValidationError } from "@/components/alerts/useChannelValidation";

const CHANNEL_UI: Record<
  AlertChannelType,
  {
    placeholder?: string;
    helper?: string;
    templateOptions?: Array<{ value: string; label: string }>;
  }
> = {
  email: {
    placeholder: "이메일 주소 (쉼표 또는 줄바꿈으로 여러 명 입력)",
    helper: "예: user@example.com, finance@example.com",
    templateOptions: [
      { value: "default", label: "표준 본문" },
    ],
  },
  telegram: {
    helper: "봇과 대화한 chat id를 입력하세요.",
    templateOptions: [
      { value: "default", label: "표준" },
      { value: "compact", label: "컴팩트" },
    ],
  },
  slack: {
    placeholder: "Slack Webhook URL (https://hooks.slack.com/…)",
    helper: "예: https://hooks.slack.com/services/AAA/BBB/CCC",
    templateOptions: [
      { value: "default", label: "텍스트 카드" },
      { value: "blocks", label: "리치 블록" },
    ],
  },
  webhook: {
    placeholder: "Webhook URL (POST JSON 수신 주소)",
    helper: "POST JSON을 받는 엔드포인트 URL",
    templateOptions: [{ value: "default", label: "표준 JSON" }],
  },
  pagerduty: {
    placeholder: "Routing Key (Integration Key)",
    helper: "PagerDuty Event API v2 Routing Key",
    templateOptions: [{ value: "default", label: "표준" }],
  },
};

type ChannelEditorProps = {
  allowedChannels: string[];
  channels: ChannelState;
  channelErrors: Record<string, ChannelValidationError>;
  pendingFocusChannel: string | null;
  onPendingFocusHandled: () => void;
  onToggleChannel: (channel: string, enabled: boolean) => void;
  onTargetChange: (channel: string, value: string) => void;
  onTemplateChange: (channel: string, value: string) => void;
  onMetadataChange: (channel: string, key: string, value: string) => void;
  channelDefinitions?: Partial<Record<AlertChannelType, { requiresTarget: boolean }>>;
};

const DEFAULT_TARGET_REQUIREMENTS: Partial<Record<AlertChannelType, boolean>> = {
  email: true,
  slack: true,
  webhook: true,
  pagerduty: true,
  telegram: false,
};

export const ChannelEditor = memo(function ChannelEditor({
  allowedChannels,
  channels,
  channelErrors,
  pendingFocusChannel,
  onPendingFocusHandled,
  onToggleChannel,
  onTargetChange,
  onTemplateChange,
  onMetadataChange,
  channelDefinitions,
}: ChannelEditorProps) {
  const selectedChannelCount = useMemo(
    () => Object.values(channels).filter((entry) => entry.enabled).length,
    [channels],
  );

  return (
    <div>
      <p className="text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">채널</p>
      <div className="mt-2 space-y-2">
        {allowedChannels.map((channel) => {
          const channelType = channel as AlertChannelType;
          const state = channels[channel] ?? emptyChannelState();
          const channelError = channelErrors[channel];
          const requiresTarget =
            channelDefinitions?.[channelType]?.requiresTarget ??
            DEFAULT_TARGET_REQUIREMENTS[channelType] ??
            false;
          const ui = CHANNEL_UI[channelType] ?? {};
          return (
            <ChannelCard
              key={channel}
              channelKey={channel}
              channelType={channelType}
              state={state}
              requiresTarget={requiresTarget}
              ui={ui}
              errors={channelError}
              onToggle={(enabled) => onToggleChannel(channel, enabled)}
              onTargetChange={(value) => onTargetChange(channel, value)}
              onTemplateChange={(value) => onTemplateChange(channel, value)}
              onMetadataChange={(key, value) => onMetadataChange(channel, key, value)}
              autoFocusTarget={pendingFocusChannel === channel}
              onAutoFocusHandled={onPendingFocusHandled}
            />
          );
        })}
      </div>
      {selectedChannelCount === 0 ? (
        <p className="mt-2 text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
          알림 채널을 최소 한 개 이상 활성화해주세요.
        </p>
      ) : null}
    </div>
  );
});
