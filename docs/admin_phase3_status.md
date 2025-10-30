# Admin 기능 현황 (Phase 3 기준)

## 완료된 작업
- **Toss 웹훅 감사 로그 파이프라인**
  - DB 테이블(`payments_toss_webhook_events`)과 JSONL 백업 동시 저장
  - `/api/v1/admin/webhooks/toss/events` FastAPI 엔드포인트 도입
  - pytest(`tests/test_toss_webhook_store.py`, `tests/test_toss_webhook_audit.py`, `tests/test_toss_webhook_replay.py`, `tests/test_admin_api.py`) + Playwright로 플로우 검증
- **플랜 퀵 액션(Admin 전용)**
  - `/api/v1/admin/plan/quick-adjust`로 플랜 티어·권한·쿼터·checkout 상태 수정
  - `PlanQuickActionsPanel`에서 티어별 기본 권한 잠금 및 추가 권한 선택 지원
  - React Query 훅, Vitest 스펙(`web/dashboard/tests/admin/PlanQuickActionsPanel.spec.tsx`) 정비
- **Admin UI 구성**
  - `TossWebhookAuditPanel`과 퀵 액션을 상단에 배치해 운영 워크플로 정리
  - LLM/RAG/Guardrails 등 확장 도메인 카드 템플릿 구성

## 미구현 / 예정 작업
| 영역 | 상태 | 예정 페이즈 |
| --- | --- | --- |
| Toss 웹훅 재시도 QA | 엔드포인트/프런트 연동 완료, e2e 스펙 추가 작성 | Phase 3 QA 보강 |
| LLM & Prompt 관리 | 카드만 존재, LiteLLM/프롬프트 CRUD 필요 | Phase 3.5 (Admin 도메인 초안) |
| Guardrail 정책 편집 | 의도 필터·블록리스트 UI/API 미구현 | Phase 3.5 |
| RAG Context 설정 | 소스/필터/Similarity 편집 패널·API 미구현 | Phase 3.5 |
| Schedules & Tasks | Celery 스케줄 조회·트리거 API 없음 | Phase 4 |
| News & Sector Pipeline | RSS/섹터 매핑 관리 기능 미구현 | Phase 4 |
| Operations & Access | API 키, Langfuse 토글, 테스트 모드 제어 미구현 | Phase 4 |
| Notification Channels | 채널/템플릿 CRUD 미구현 | Phase 4 |
| UI & UX Settings | 대시보드 기본값/배너 편집 기능 미구현 | Phase 4 이후 |
| QA 자산 보강 | Storybook/운영 플레이북 업데이트 필요 | Phase 3 QA 보강 |

## QA & 문서 보강 메모 (Phase 3 잔여)
- Playwright `adminQuickActions.spec.ts`: 플랜 기본 권한 잠금, Toss 웹훅 재시도 버튼 검증
- Storybook/문서: Admin Quick Actions 스토리, Toss 웹훅 운영 가이드 초안
- 운영 문서 업데이트: “웹훅 재처리 절차”, “플랜 수동 조정 체크리스트”
