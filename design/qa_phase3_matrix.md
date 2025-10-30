# Phase 3 QA Checklist & Automation Guide (2025-10-30)

## 1. Regression Targets

- **결제 플로우**
  - Settings → `토스페이먼츠 연동 준비 신호` 체크 → 저장 → Toss 리다이렉트 → `/payments/success`에서 PlanStore 자동 갱신 확인
  - Toss 리다이렉트 취소 → `/payments/fail` 토스트/안내 확인
  - 관리 콘솔에서 `checkoutRequested` 해제 및 플랜 배지 갱신 여부 확인
- **PlanLock/PlanSettingsForm**
  - Free/Pro/Enterprise별 배지·CTA 노출
  - 저장 성공/실패 토스트, checkoutRequested 배너 표시
- **Alert Builder & Bell (알림)**
  - PlanLock/업그레이드 CTA가 Toss 업그레이드 플로우로 연결되는지 확인

## 2. Automation Assets

- **Storybook**
  - `UI/PlanLock`
  - `Plan/PlanSettingsForm` 기본/checkoutRequested 사례
  - `Payments/PaymentResultCard` 성공/실패 상태
- **Unit & Integration Tests**
  - `web/dashboard/tests/plan/PlanSettingsForm.spec.tsx`
  - 저장 로직 모킹 시 결제 웹훅 호출 여부 검증
- **Playwright**
  - `tests/e2e/paymentsFlow.spec.ts` (Toss API 모킹 + redirect URL 주입으로 성공/취소/확인 실패 시나리오 검증, 실제 Toss 호출 없음)
  - Toss 위젯 실제 모킹 전략 확정 시 해당 테스트에 통합 예정

## 3. Manual Verification Script

1. `.env.local`에 Toss 성공/실패 redirect URL 설정, 백엔드 환경 변수 로드 후 `uvicorn` 실행
2. `pnpm dev`로 프런트 실행 → Settings에서 결제 성공 시나리오 수행
3. Toss 콘솔에서 테스트 결제 내역 확인 후 취소 케이스 재실행
4. PlanSummaryCard/PlanAlertOverview/PlanSettingsForm에서 플랜 정보 갱신 및 토스트 확인, `checkoutRequested` 자동 해제 여부 점검

## 4. Follow-up

- Toss 웹훅 서명 검증 및 checkoutRequested 해제 자동화
- Playwright용 Toss 위젯 모킹 전략 확정
- Admin Quick Action 실행 로그 및 알림 시나리오 추가
