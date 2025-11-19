"use client";

import type { CommanderRouteDecision } from "@/lib/chatApi";
import { GenericToolPlaceholder } from "./GenericToolPlaceholder";

type SnapshotPanelProps = {
  params?: Record<string, unknown>;
  decision?: CommanderRouteDecision | null;
};

export function SnapshotPanel({ params, decision }: SnapshotPanelProps) {
  const identifier = typeof params?.ticker === "string" ? params.ticker : (params?.identifier as string | undefined);
  return (
    <GenericToolPlaceholder
      title="기업 Snapshot"
      description="기본 시세, 재무, 주요 주주 현황을 카드 형태로 제공합니다."
      hint="챗에서 Snapshot을 호출하면 이 영역에 카드가 렌더링됩니다."
    >
      {identifier ? <p className="text-xs text-text-secondaryLight">요청 종목: {identifier}</p> : null}
      {decision?.reason ? <p className="text-xs text-text-secondaryLight">{decision.reason}</p> : null}
    </GenericToolPlaceholder>
  );
}
