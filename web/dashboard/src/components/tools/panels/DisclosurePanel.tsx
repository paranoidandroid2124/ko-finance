"use client";

import type { CommanderRouteDecision } from "@/lib/chatApi";
import { GenericToolPlaceholder } from "./GenericToolPlaceholder";

type DisclosurePanelProps = {
  params?: Record<string, unknown>;
  decision?: CommanderRouteDecision | null;
};

export function DisclosurePanel({ params, decision }: DisclosurePanelProps) {
  const ticker = typeof params?.ticker === "string" ? params.ticker : undefined;
  const receiptNo = typeof params?.receipt_no === "string" ? params.receipt_no : undefined;
  return (
    <GenericToolPlaceholder
      title="지능형 공시 뷰어"
      description="공시 원문에서 중요 문단을 찾아 하이라이트로 점프합니다."
      hint="Commander가 공시를 열면 여기에 해당 문단이 표시됩니다."
    >
      <div className="space-y-1 text-xs">
        {ticker ? <p>요청된 종목: {ticker}</p> : null}
        {receiptNo ? <p>접수번호: {receiptNo}</p> : null}
        {decision?.reason ? <p className="text-text-secondaryLight">{decision.reason}</p> : null}
      </div>
    </GenericToolPlaceholder>
  );
}
