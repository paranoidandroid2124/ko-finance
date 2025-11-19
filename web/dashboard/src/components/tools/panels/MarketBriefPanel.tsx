"use client";

import type { CommanderRouteDecision } from "@/lib/chatApi";
import { GenericToolPlaceholder } from "./GenericToolPlaceholder";

type MarketBriefPanelProps = {
  params?: Record<string, unknown>;
  decision?: CommanderRouteDecision | null;
};

export function MarketBriefPanel({ params, decision }: MarketBriefPanelProps) {
  const date = typeof params?.date === "string" ? params.date : undefined;
  return (
    <GenericToolPlaceholder
      title="AI 마켓 브리핑"
      description="장 마감 시황과 주요 뉴스를 카드로 정리합니다."
      hint="Commander가 호출하면 브리핑 카드가 생성됩니다."
    >
      {date ? <p className="text-xs text-text-secondaryLight">참조 일자: {date}</p> : null}
      {decision?.reason ? <p className="text-xs text-text-secondaryLight">{decision.reason}</p> : null}
    </GenericToolPlaceholder>
  );
}
