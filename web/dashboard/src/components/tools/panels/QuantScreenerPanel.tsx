"use client";

import type { CommanderRouteDecision } from "@/lib/chatApi";
import { GenericToolPlaceholder } from "./GenericToolPlaceholder";

type QuantScreenerPanelProps = {
  params?: Record<string, unknown>;
  decision?: CommanderRouteDecision | null;
};

export function QuantScreenerPanel({ params, decision }: QuantScreenerPanelProps) {
  const filters = Array.isArray(params?.filters) ? (params?.filters as unknown[]) : [];
  return (
    <GenericToolPlaceholder
      title="퀀트 스크리너"
      description="자연어 조건을 수치 필터로 변환해 후보 종목을 찾습니다."
      hint="파라미터가 준비되면 Commander가 이곳에 스크리너 결과를 표시합니다."
    >
      {filters.length ? (
        <ul className="text-xs text-text-secondaryLight">
          {filters.slice(0, 4).map((filter, idx) => (
            <li key={idx}>• {JSON.stringify(filter)}</li>
          ))}
          {filters.length > 4 ? <li>… 외 {filters.length - 4}개 조건</li> : null}
        </ul>
      ) : (
        <p className="text-xs text-text-secondaryLight">조건이 전달되면 여기에서 확인할 수 있어요.</p>
      )}
      {decision?.reason ? <p className="mt-2 text-xs text-text-secondaryLight">{decision.reason}</p> : null}
    </GenericToolPlaceholder>
  );
}
