import type { AlertPlanInfo, AlertRule, AlertChannel } from "@/lib/alertsApi";

export type BuilderMode = "create" | "edit" | "duplicate";

export type ChannelConfigState = {
  enabled: boolean;
  input: string;
  targets: string[];
  metadata: Record<string, string>;
  template: string;
};

export type ChannelState = Record<string, ChannelConfigState>;

const TARGET_SEPARATORS = /[\r\n,;]+/;

const DEFAULT_CHANNEL_STATE: ChannelConfigState = {
  enabled: false,
  input: "",
  targets: [],
  metadata: {},
  template: "default",
};

const normalizeMetadata = (metadata: AlertChannel["metadata"]): Record<string, string> => {
  if (!metadata || typeof metadata !== "object") {
    return {};
  }
  return Object.fromEntries(
    Object.entries(metadata as Record<string, unknown>)
      .filter((entry): entry is [string, string] => typeof entry[1] === "string")
      .map(([key, value]) => [key, value.trim()]),
  );
};

const extractTargets = (channel: AlertChannel): string[] => {
  if (channel.targets && channel.targets.length > 0) {
    return channel.targets.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
  }
  if (channel.target && typeof channel.target === "string") {
    const trimmed = channel.target.trim();
    return trimmed ? [trimmed] : [];
  }
  return [];
};

export const parseTargetsInput = (value: string): string[] => {
  if (!value) {
    return [];
  }
  const seen = new Set<string>();
  return value
    .split(TARGET_SEPARATORS)
    .map((item) => item.trim())
    .filter((item) => {
      if (!item) {
        return false;
      }
      if (seen.has(item)) {
        return false;
      }
      seen.add(item);
      return true;
    });
};

export const formatTargetsInput = (targets?: string[] | null): string => {
  if (!targets || targets.length === 0) {
    return "";
  }
  return targets.map((item) => item.trim()).filter(Boolean).join(", ");
};

const withDefaults = (state?: Partial<ChannelConfigState>): ChannelConfigState => ({
  ...DEFAULT_CHANNEL_STATE,
  ...state,
});

type DeriveInitialChannelsArgs = {
  plan: AlertPlanInfo | null;
  editingRule: AlertRule | null;
  mode: BuilderMode;
};

export const deriveInitialChannels = ({ plan, editingRule, mode }: DeriveInitialChannelsArgs): ChannelState => {
  const channels: ChannelState = {};
  const planChannels = plan?.channels ?? [];
  const editingChannels = editingRule?.channels ?? [];
  const seen = new Set<string>();
  const shouldAutoEnable = (channel: string, index: number) =>
    !editingRule && mode === "create" && (index === 0 || channel === "telegram");

  planChannels.forEach((channelType, index) => {
    const existing = editingChannels.find((item) => item.type === channelType) ?? null;
    const targets = existing ? extractTargets(existing) : [];
    const metadata = existing ? normalizeMetadata(existing.metadata) : {};
    const template = existing?.template ?? "default";
    channels[channelType] = withDefaults({
      enabled: existing ? true : shouldAutoEnable(channelType, index),
      input: formatTargetsInput(targets),
      targets,
      metadata,
      template,
    });
    seen.add(channelType);
  });

  editingChannels.forEach((channel) => {
    if (seen.has(channel.type)) {
      return;
    }
    const targets = extractTargets(channel);
    channels[channel.type] = withDefaults({
      enabled: true,
      input: formatTargetsInput(targets),
      targets,
      metadata: normalizeMetadata(channel.metadata),
      template: channel.template ?? "default",
    });
  });

  return channels;
};

export const emptyChannelState = (): ChannelConfigState => ({ ...DEFAULT_CHANNEL_STATE });
