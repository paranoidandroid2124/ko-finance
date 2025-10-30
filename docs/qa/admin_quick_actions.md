# Admin Quick Actions QA 가이드 (Phase 3)

## 1. 자동 검증
- **Pytest**  
  ```bash
  pytest tests/test_toss_webhook_store.py tests/test_toss_webhook_audit.py tests/test_toss_webhook_replay.py tests/test_admin_api.py
  ```
  > Toss 웹훅 저장/감사/재처리 로직과 Admin API 응답을 확인합니다.
- **Playwright**  
  ```bash
  pnpm exec playwright test web/dashboard/tests/e2e/adminQuickActions.spec.ts
  ```
  > Admin 페이지 진입 → 플랜 기본 권한 잠금 → 웹훅 재시도 버튼 호출 흐름을 검증합니다.

## 2. 수동 확인 체크리스트
| 항목 | 절차 | 기대 결과 |
|------|------|-----------|
| 플랜 퀵 액션 기본 값 | Admin 대시보드 → `플랜 퀵 액션` | 현재 플랜 요약 정보와 Checkout 상태가 API와 일치 |
| 플랜 티어 변경 | `적용할 플랜 티어` 를 Free/Pro/Enterprise 로 전환 | 티어별 기본 권한이 잠김 상태로 유지, 추가 권한만 토글 가능 |
| 플랜 저장 | 변경 후 “플랜 조정 적용” | 저장 성공 토스트, `PlanSummaryCard`/`PlanTierPreview`에 변경 반영 |
| Toss 감사 로그 | `Toss 웹훅 감사 로그` 패널 | 최신 이벤트 목록 / 재시도 버튼 노출 |
| 웹훅 재시도 | 이벤트 `재시도` 클릭 → 성공 토스트 확인 | `payments_toss_webhook_events`에 `replay_*` 기록, 플랜 업그레이드/checkout 해제 반영 |

## 3. 운영 메모
- **실패 대응**  
  - 재시도 실패 시 감사 로그에 `replay_*` 결과가 저장되므로, `uploads/admin/toss_webhook_audit.jsonl` 또는 DB 테이블에서 원인을 확인합니다.
  - 재처리 전에는 `transmissionId`·`orderId`가 유효한지 Toss 콘솔에서 확인하세요.
- **플랜 수동 조정**  
  - Actor/Change Note를 반드시 채워 운영 로그를 남기고, 저장 후 `/uploads/admin/plan_settings.json`에 이력이 기록되는지 확인합니다.
- **문서 업데이트**  
  - 신규 웹훅 이벤트 타입이 추가되면 `services/payments/toss_webhook_utils.py` 와 QA 문서를 동시 업데이트합니다.
