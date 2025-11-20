import { type ComponentType } from "react";

import { DisclosurePanel } from "@/components/tools/panels/DisclosurePanel";
import { QuantScreenerPanel } from "@/components/tools/panels/QuantScreenerPanel";
import { SnapshotPanel } from "@/components/tools/panels/SnapshotPanel";
import { MarketBriefPanel } from "@/components/tools/panels/MarketBriefPanel";
import { NewsPanel } from "@/components/tools/panels/NewsPanel";
import { PeerPanel } from "@/components/tools/panels/PeerPanel";
import type { CommanderPaywallTier, CommanderRouteDecision, CommanderUiContainer } from "@/lib/chatApi";

export type CommanderToolId =
  | "disclosure_viewer"
  | "quant_screener"
  | "snapshot"
  | "market_briefing"
  | "news_insights"
  | "peer_compare";

export type CommanderToolComponent = ComponentType<{
  params?: Record<string, unknown>;
  decision?: CommanderRouteDecision | null;
}>;

export type CommanderToolDefinition = {
  id: CommanderToolId;
  callName: string;
  title: string;
  subtitle: string;
  uiContainer: CommanderUiContainer;
  paywall: CommanderPaywallTier;
  teaser?: "blur" | "lock" | "none";
  component: CommanderToolComponent;
};

const buildDefinition = (
  def: Omit<CommanderToolDefinition, "teaser"> & Partial<Pick<CommanderToolDefinition, "teaser">>,
): CommanderToolDefinition => ({
  teaser: "none",
  ...def,
});

export const COMMANDER_TOOL_REGISTRY: Record<CommanderToolId, CommanderToolDefinition> = {
  disclosure_viewer: buildDefinition({
    id: "disclosure_viewer",
    callName: "disclosure.viewer",
    title: "지능형 공시 뷰어",
    subtitle: "공시 원문에서 핵심 문단을 찾아 하이라이트로 이동합니다.",
    uiContainer: "side_panel",
    paywall: "starter",
    component: DisclosurePanel,
  }),
  quant_screener: buildDefinition({
    id: "quant_screener",
    callName: "quant.screener",
    title: "퀀트 스크리너",
    subtitle: "자연어 필터로 저평가·마진 개선 종목을 찾습니다.",
    uiContainer: "overlay",
    paywall: "pro",
    teaser: "blur",
    component: QuantScreenerPanel,
  }),
  snapshot: buildDefinition({
    id: "snapshot",
    callName: "snapshot.company",
    title: "기업 Snapshot",
    subtitle: "기본 시세와 주요 재무지표를 카드로 요약합니다.",
    uiContainer: "inline_card",
    paywall: "free",
    component: SnapshotPanel,
  }),
  market_briefing: buildDefinition({
    id: "market_briefing",
    callName: "market.briefing",
    title: "AI 마켓 브리핑",
    subtitle: "장 마감 후 시황과 주요 뉴스를 정리합니다.",
    uiContainer: "inline_card",
    paywall: "free",
    component: MarketBriefPanel,
  }),
  news_insights: buildDefinition({
    id: "news_insights",
    callName: "news.rag",
    title: "뉴스 리포터",
    subtitle: "요약된 뉴스 근거를 카드 형태로 제공합니다.",
    uiContainer: "overlay",
    paywall: "starter",
    component: NewsPanel,
  }),
  peer_compare: buildDefinition({
    id: "peer_compare",
    callName: "peer.compare",
    title: "Peer 비교",
    subtitle: "섹터/경쟁사 대비 상대 수익률과 상관관계를 확인합니다.",
    uiContainer: "overlay",
    paywall: "pro",
    component: PeerPanel,
  }),
};

const CALL_NAME_INDEX = Object.values(COMMANDER_TOOL_REGISTRY).reduce<Record<string, CommanderToolDefinition>>(
  (acc, tool) => {
    acc[tool.callName] = tool;
    return acc;
  },
  {},
);

export const resolveToolByCallName = (callName?: string | null) => {
  if (!callName) {
    return null;
  }
  return CALL_NAME_INDEX[callName] ?? null;
};
