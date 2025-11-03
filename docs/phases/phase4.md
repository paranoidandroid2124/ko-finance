# Phase 4 — Operations Console & Guardrails (완료)

## 목표
- LLM/LiteLLM 프로필과 시스템 프롬프트, Guardrail 정책을 Admin 콘솔에서 관리
- RAG 컨텍스트(소스·필터·유사도)를 운영자가 조정할 수 있도록 설정 화면 제공
- Celery 스케줄, RSS/섹터 매핑, API 키/관측 토글 등 운영 패널 구축
- Notification 채널 CRUD 및 대시보드 기본값/배너 편집 기능 추가

## 준비 사항
- Admin 전용 RBAC/감사 로그 설계 마무리
- Toss/플랜 기능에 대한 Phase 3 QA 자산을 기반으로 Admin smoke 테스트 확장
- LiteLLM/Guardrail 설정 저장소(파일 vs DB) 확정 및 마이그레이션 계획 수립

## 일정 메모
- Phase 3 종료 즉시 착수, 세부 일정은 PM과 조율 예정
- 도메인별 세부 스토리는 Phase 4 킥오프 시 별도 문서화

## 진행 현황 (2025-10-31 기준)
- Admin 콘솔 진입 가드를 위한 토큰 기반 로그인 카드를 구현했고, 저장된 토큰 자동 복구·초기화까지 지원해 운영자가 새 탭에서도 즉시 인증할 수 있습니다.
- `/api/v1/admin/llm/*`, `/admin/rag/*`, `/admin/ops/*` 라우터가 업로드 디렉터리 기반 저장소와 감사 로그에 연결되어 LLM 프로필·Guardrail·RAG 설정·운영 파이프라인을 읽고 쓰며, 관련 pytest(`tests/test_admin_management.py`, `tests/test_rag_api.py`)가 통과합니다.
- LLM & Guardrail 패널은 actor/변경 메모 입력, 감사 로그 다운로드, 토스트 패턴을 공유하며, LLM 프로필은 “현재 저장된 값 ↔ 저장 예정 값” 비교 카드와 복사 버튼으로 변경분을 한눈에 검토할 수 있습니다.
- RAG 재색인 패널은 실패 대기열 관리(상태 필터, Langfuse trace ID/URL), 즉시 재시도·제거, Judge `rag_mode`에 따른 사용자 토스트를 포함하고, Langfuse trace/span ID를 복사할 수 있는 UI를 제공합니다.
- Admin Ops 패널은 Celery 스케줄·Langfuse/API 키·알림 채널·뉴스 파이프라인을 한 화면에서 편집하며, 알림 채널 미리보기 결과를 복사할 수 있어 템플릿·메타데이터 재활용이 편리해졌습니다.
- UI & UX 패널에서 브랜드 색상, 기본 기간, 첫 화면, 환영 문구, 알림 배너를 조정할 수 있고, 모든 변경은 `audit_master.jsonl` 및 통합 감사 API(`/api/v1/admin/ops/audit/logs`)에 기록됩니다.
- Langfuse API 키 회전은 `/api/v1/admin/ops/api-keys/langfuse/rotate` 엔드포인트와 관리자 패널 “토큰 재발급” 버튼으로 자동화되어, 키 회전과 감사 로그 기록이 일관된 흐름으로 제공됩니다.

## 심화 UX 아이디어 (백로그)
- LLM 프로필 라인-by-라인 diff 하이라이트, 다중 프로필 비교, 저장 이력 타임라인
- 알림 템플릿 갤러리/샘플 메타 자동 생성, 프리뷰 공유 링크
- Langfuse 자동 재시도 모니터링 대시보드 및 Trace 비교 뷰
- 관리자 토큰 다중 환경 관리, 만료 안내 배너

## Phase 5 대비 메모
- 인프라: GCP Cloud Run, Cloud SQL, Secret Manager, 감사 로그 GCS/Cloud Logging 이관, Google Identity RBAC 준비
- 데이터 전략: 라이선스 검토, 의도 분류/threshold/fallback/Langfuse trace 확장, 재색인 히스토리 API 고도화
- 운영 파이프라인: Cloud Tasks/Workflows 전환, 저장소 추상화(로컬·클라우드 겸용)

## 테스트 & 배포 전략
- pytest에 Admin/LiteLLM/RAG/Ops 관련 통합 시나리오가 포함되어 있으며, 운영 smoke 테스트는 `pytest tests/test_admin_management.py`로 주기적으로 실행합니다.
- Phase 4 기능은 Feature Flag(`admin.phase4.llm`, `admin.phase4.rag`, `admin.phase4.ops`)로 제어하고, Staging에서 충분한 QA 후 Prod에 순차 롤아웃합니다.
