"use client";

import type { AlertRule, WatchlistRuleChannelSummary, WatchlistRuleDetail } from "@/lib/alertsApi";

/**
 * Normalize an AlertRule payload from the list endpoint so that wizard/detail views
 * can reuse it without issuing an additional detail API request.
 */
export const convertAlertRuleToDetail = (rule: AlertRule): WatchlistRuleDetail => ({
  id: rule.id,
  name: rule.name,
  description: rule.description,
  status: rule.status,
  evaluationIntervalMinutes: rule.frequency?.evaluationIntervalMinutes ?? rule.evaluationIntervalMinutes,
  windowMinutes: rule.frequency?.windowMinutes ?? rule.windowMinutes,
  cooldownMinutes: rule.frequency?.cooldownMinutes ?? rule.cooldownMinutes,
  maxTriggersPerDay: rule.frequency?.maxTriggersPerDay ?? rule.maxTriggersPerDay ?? undefined,
  condition: {
    type: rule.trigger.type,
    tickers: rule.trigger.tickers ?? [],
    categories: rule.trigger.categories ?? [],
    sectors: rule.trigger.sectors ?? [],
    minSentiment: rule.trigger.type === "news" ? rule.trigger.minSentiment ?? null : undefined,
  },
  channels: (rule.channels ?? []).map(
    (channel): WatchlistRuleChannelSummary => ({
      type: channel.type,
      label: channel.label ?? null,
      target: channel.target ?? null,
      targets:
        channel.targets && channel.targets.length > 0
          ? channel.targets
          : channel.target
            ? [channel.target]
            : [],
      metadata: channel.metadata ?? {},
    }),
  ),
  extras: rule.extras ?? {},
  lastTriggeredAt: rule.lastTriggeredAt,
  lastEvaluatedAt: rule.lastEvaluatedAt,
  errorCount: rule.errorCount ?? 0,
});
