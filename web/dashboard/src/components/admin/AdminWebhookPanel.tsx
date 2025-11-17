"use client";

import { Webhook } from "lucide-react";

import { TossWebhookAuditPanel } from "./TossWebhookAuditPanel";

export function AdminWebhookPanel() {
  return (
    <div className="rounded-xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
            Webhook &amp; Keys
          </p>
          <h3 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">토스 결제 웹훅</h3>
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            최근 전달된 웹훅 이벤트와 서명 검증 상태를 확인하고, 키 회전 가이드를 참고하세요.
          </p>
          <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
            Webhook Secret은 Admin Console &gt; 환경설정에서 회전 후 여기 기록을 모니터링하세요.
          </p>
        </div>
        <Webhook className="h-8 w-8 text-primary" aria-hidden />
      </div>
      <TossWebhookAuditPanel />
    </div>
  );
}
