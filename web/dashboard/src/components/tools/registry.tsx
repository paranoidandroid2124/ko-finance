import { type ComponentType } from "react";

import { DisclosurePanel } from "@/components/tools/panels/DisclosurePanel";
import { NewsPanel } from "@/components/tools/panels/NewsPanel";
import { PeerPanel } from "@/components/tools/panels/PeerPanel";
import type { CommanderPaywallTier, CommanderRouteDecision, CommanderUiContainer } from "@/lib/chatApi";

export type CommanderToolId =
  | "disclosure_viewer"
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
