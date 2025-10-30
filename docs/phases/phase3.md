# Phase 3 — Pro/Enterprise Enablement & Payments (완료)

**핵심 목표** 플랜 스토어 정착, Toss 결제/웹훅 연동, Admin 퀵 액션 제공

## 주요 산출물
- 결제/요금제
  - `services/payments/toss_payments.py`, `web/routers/payments.py` — Toss 결제 확인·웹훅 처리
  - `services/payments/toss_webhook_store.py`, `toss_webhook_audit.py`, `toss_webhook_replay.py` — 서명 검증, 중복 방지, 감사/재시도 파이프라인
  - 프런트 결제 플로우 (`web/dashboard/src/app/payments/success|fail/page.tsx`) 및 토스트/재시도 UX 개선
- 플랜 컨텍스트 & 잠금
  - `services/plan_service.py`, `/api/v1/plan/context` — 글로벌 플랜 상태 관리
  - `web/dashboard/src/store/planStore.ts`, `PlanLock.tsx`, `PlanSummaryCard.tsx` 등 — 플랜 잠금/요약 UI
- Alerts/Plan Builder
  - `services/alert_service.py`, `web/routers/alerts.py` — 플랜별 채널·규칙 CRUD
  - `web/dashboard/src/components/alerts/*` — Alert Builder flows, Plan messaging
- Admin 퀵 액션 & 감사
  - `/api/v1/admin/*` — 플랜 조정, Toss 감사 로그 조회/재시도
  - `PlanQuickActionsPanel.tsx`, `TossWebhookAuditPanel.tsx` — 운영자 UI
  - QA 문서: `docs/qa/admin_quick_actions.md`

## QA / 문서
- pytest: 결제·플랜·웹훅·Admin API 전반 테스트 셋 정비
- Playwright: `paymentsFlow.spec.ts`, `alertsPlan.spec.ts`, `adminQuickActions.spec.ts`
- 문서: Admin/Plan/Toss 흐름을 통합한 Phase 3 QA 가이드 작성
