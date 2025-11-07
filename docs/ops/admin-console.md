# 운영 콘솔 인증 & GCP 분리 메모

## 현행 정리
- Phase 4 대비로 /api/v1/admin/llm/*, /admin/rag/*, /admin/ops/* 라우터와 스키마 골격을 추가해 LLM·RAG·셀러리/비밀 제어 계약을 선반영했습니다.
- FastAPI `require_admin_session` 의존성이 `Authorization: Bearer <token>` 또는 `admin_session_token` 쿠키를 통해 운영 세션을 검증합니다.
- `/api/v1/admin/session` 엔드포인트를 통해 프런트엔드가 관리자 세션 상태를 조회하고, 세션 정보는 Next.js 대시보드의 `useAdminSession` 훅으로 전달됩니다.
- Plan Quick Actions 및 Toss 웹훅 감사 패널은 새 훅을 이용해 권한이 없을 때 따뜻한 안내를 보여주고, 재시도 버튼을 잠급니다.
- RAG 재색인 패널에 실패 큐·상태 필터·검색 입력을 추가해 Langfuse trace ID까지 메타로 기록하며, 실패 항목을 큐에서 바로 재시도하거나 정리할 수 있습니다.
- Guardrail 평가 UI는 평가 시각과 감사 로그 다운로드 링크를 함께 노출하고, `/api/v1/admin/llm/audit/logs` 파일이 즉시 최신 평가를 반영하도록 표준화했습니다.
- Langfuse API 키 회전은 `/api/v1/admin/ops/api-keys/langfuse/rotate` 엔드포인트로 자동화되어 운영 패널의 “토큰 재발급” 버튼에서 키를 새로 발급하고 감사를 남깁니다.

## GCP 전환 시 TODO
1. **도메인 분리**
   - `admin.kfinance.example` 서브도메인을 Cloud Run / Cloud Load Balancer에서 별도 라우팅.
   - 관리 콘솔 전용 TLS 인증서와 IP 제한(Cloud Armor) 적용.
2. **세션/인증 고도화**
   - Google Identity 또는 IAP를 사용해 관리자 SSO 적용, LiteLLM/Langfuse 권한과 연동.
   - IAP 승인 후 FastAPI는 `X-Goog-Authenticated-User-Email` 헤더로 운영자 식별.
3. **비밀/구성 관리**
   - `ADMIN_API_TOKENS`는 Secret Manager로 이전하고, Cloud Run 런타임에 버전화된 비밀을 주입.
   - 운영 토큰 변경 시 Slack/Langfuse 알림을 위해 Pub/Sub 트리거 설계.
4. **감사 로깅**
   - 관리자 API 호출 메타데이터를 Cloud Logging + BigQuery로 내보내 Guardrail 튜닝 추적.
   - Langfuse와 연동해 관리자 액션(플랜 조정, 웹훅 재시도)을 세션별로 기록.
5. **배포/테스트**
   - `pnpm test --filter admin` 등 프런트 전용 테스트 스위트를 구축해 운영 콘솔 UI 회귀 방지.
   - GitHub Actions에서 Admin API pytest + Vitest를 분리 실행하고, 실패 시 Slack으로 알림.

## 단기 후속 액션
- 토큰 로그인 UI (쿠키 설정) 초안 작성 → 운영팀이 브라우저에서 직접 토큰을 입력해 세션을 개설할 수 있도록 준비.
- 관리자 세션 훅을 활용한 Admin 페이지 E2E (Playwright) 시나리오 작성.
- `terraform/` 혹은 `ops/` 폴더에 Cloud Run 이중 서비스(메인 API, Admin API) 샘플 정의 초안 추가.

## 감사 로그 & 재색인 Trace BigQuery/GCS 싱크
- **필요 설정**
  - `BIGQUERY_PROJECT_ID`, `BIGQUERY_LOCATION`(기본 `asia-northeast3`)
  - `BIGQUERY_AUDIT_DATASET`, `BIGQUERY_AUDIT_TABLE`, `BIGQUERY_REINDEX_TABLE`
  - `GCS_BUCKET_NAME`, `GCS_AUDIT_ARCHIVE_PREFIX`, `GCS_REINDEX_ARCHIVE_PREFIX`
  - `STORAGE_PROVIDER=gcs` 또는 `auto` (GCS 우선 적용)
- **실행 스크립트**
  ```bash
  python scripts/sync_audit_traces.py               # BigQuery + GCS 동시 실행
  python scripts/sync_audit_traces.py --skip-archive  # BigQuery 전용
  python scripts/sync_audit_traces.py --skip-bigquery # GCS 아카이브 전용
  ```
- `.state/` 폴더에 offset을 저장하므로 반복 실행 시 신규 로그만 동기화됩니다. 로그 파일이 재생성되면 offset이 자동으로 리셋됩니다.
- BigQuery 테이블이 없다면 스크립트가 자동으로 생성하며, `timestamp` 필드를 기준으로 시간 파티셔닝합니다.
- GCS 아카이브 파일은 `compliance/audit`·`compliance/reindex` (환경 변수 수정 가능) 경로에 `*.jsonl`로 업로드됩니다.
- 모든 CLI 스크립트는 `core.env_utils.load_dotenv_if_available()`로 `.env`를 자동 로드하며, `require_env_vars([...])`가 필수 환경 변수 누락 시 즉시 오류를 발생시킵니다. Secret Manager를 통해 환경 변수를 주입한 배포 환경에서는 `.env`가 없어도 안전하게 동작합니다.

### SLA 모니터링 대시보드
- Admin 콘솔 > RAG 패널에 **BigQuery 기반 SLA 추세** 카드와 **최근 SLA 초과 목록**이 추가되었습니다.
- `scripts/sync_audit_traces.py`가 BigQuery 및 GCS로 재색인 로그를 싱크해야 그래프·목록이 채워집니다. (연동이 끊기면 패널 상단에 BigQuery 구성 안내가 표시됩니다.)
- 재색인 실행·큐 재시도·큐 삭제 시 React Query가 `ADMIN_RAG_SLA_SUMMARY_KEY`를 자동 무효화해 최신 통계를 불러옵니다.
- SLA 카드의 만족률·p95 지표는 BigQuery 값을 우선 사용하고, 동기화가 되지 않은 경우 기존 SQLite 요약(임시)으로 폴백합니다.
