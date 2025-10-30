# Phase 5 — GCP Migration & Platform Hardening (예정)

## 목표
- FastAPI/Next.js 스택을 Google Cloud Run(+Cloud SQL)으로 이전하여 운영 자동화 기반 확보
- Secret Manager·Artifact Registry·Cloud Build 파이프라인을 도입해 설정·배포를 코드화
- Admin RBAC를 Google Identity(AAD/Workspace)와 연계하고 감사 로그를 중앙 수집
- Observability(Cloud Logging, Cloud Monitoring, Langfuse) 연계를 통해 Phase 4 기능 안정화

## 준비 사항
- 서비스 계정 설계 및 최소 권한 롤 검토 (API, Celery, Admin 콘솔 별도 역할)
- 데이터베이스 마이그레이션 전략 수립 (Cloud SQL → 기존 Postgres 스키마 이관 계획)
- 네트워크/도메인 설정 초안 (Cloud Armor, HTTPS Load Balancer, VPC 필요 여부 결정)

## 일정 메모
- Phase 4 기능 안정화 후 즉시 착수, 인프라 리스크를 고려해 2~3 스프린트 배정
- Cut-over 전후로 Staging/Production 이중 운영 기간을 최소 1주 확보
- IaC(Terraform 또는 Config Connector) 작성은 첫 스프린트에서 병렬 진행

## 상세 설계 프레임
- **P0 (스프린트 1)**: Secret Manager 통합, Cloud Build/Artifact Registry 파이프라인, IaC 기본 스택 배치
- **P1 (스프린트 2)**: Cloud Run 서비스/Cloud SQL 연결, Celery 워커 런타임(GCE/GKE) 결정, Admin RBAC Google OAuth 연동
- **P2 (스프린트 3)**: Observability 스택(Cloud Logging, Error Reporting, Langfuse) 확장, 롤백 전략/운영 플레이북 확정
- 모든 단계에서 Staging → Production 순차 배포와 체크리스트 기반 검증을 유지

### 클라우드 인프라 전환

#### 범위와 재사용 포인트
- 기존 Dockerfile과 `docker-compose.yaml`을 기준으로 Cloud Run/Cloud Build 베이스 이미지를 생성한다.
- Celery 워커는 Cloud Run Jobs 또는 GKE Autopilot 중 하나로 PoC하고, 공통 이미지 레지스트리는 Artifact Registry로 통일한다.
- 데이터 계층(Postgres, Redis)은 Cloud SQL/MemoryStore로 이전하되, Phase 4에서 정리한 설정 스키마(`admin_phase4`)를 그대로 마이그레이션한다.

#### 작업 항목
| 항목 | 내용 | 의존성 |
|------|------|--------|
| Cloud Build 파이프라인 | Git 태그/브랜치 기반 빌드, Artifact Registry 푸시 | Dockerfile 정합성 |
| Cloud Run 서비스 | API/Next.js 각각 배포, 최소 2개 리전 설정 검토 | Secret Manager·VPC |
| Cloud SQL 마이그레이션 | pg_dump/pg_restore, 마이그레이션 테스트 스크립트 작성 | Alembic 스키마 최신화 |
| Redis 대체 | MemoryStore 또는 Cloud Memorystore + VPC 커넥터 | Celery 구성 변경 |

### 비밀/설정 관리

#### 범위와 재사용 포인트
- Phase 4에서 설계한 Admin 설정 API는 Secret Manager 또는 전용 설정 테이블을 읽도록 추상화한다.
- 로컬 개발은 `.env`를 유지하되, `scripts/load_secrets.py`(신규)로 Secret Manager 값을 동기화하는 CLI를 제공한다.

#### 작업 항목
- Secret naming 컨벤션 정립 (`projects/{id}/secrets/ko-finance/{env}/{service}/{key}`)
- Secret Manager 갱신 시 GitOps/Cloud Deploy 파이프라인에 트리거 연결
- 중요 비밀 변경 시 감사 로그 테이블과 Cloud Audit Logs를 함께 기록

### RBAC & 감사 로그 통합

#### 범위와 재사용 포인트
- Phase 4에서 구축한 RBAC 스캐폴드를 Google Identity 기반 Single Sign-On으로 확장한다.
- 감사 로그는 Cloud Logging Export → BigQuery/Cloud Storage 아카이브로 이중화하고, Admin UI에서 조회 가능한 스냅샷 API를 유지한다.

#### 작업 항목
- OAuth 클라이언트 등록, 그룹/역할 매핑 규칙 정의 (`admin_ops`, `llm_admin`, `viewer`)
- 감사 로그 싱크 생성 (Cloud Logging → BigQuery), 데이터 지속 기간 정책 설정
- Admin 콘솔에서 BigQuery 질의를 캐시해 보여주는 API (필요 시 Cloud Functions 활용)

### Observability & 운영

#### 범위와 재사용 포인트
- Langfuse, Prometheus(선택 시 Managed Service), Cloud Monitoring 대시보드를 통합해 Phase 4 기능의 SLO를 정의한다.
- Celery/Cloud Run 로그는 Cloud Logging→Error Reporting으로 전송하고, Alerting 정책을 Playbook에 명시한다.

#### 작업 항목
- Cloud Monitoring 대시보드 자동화 (Terraform 모듈화)
- Error Reporting 알림 채널(Gmail/Slack) 등록
- Cut-over 전후 체크리스트: 롤백 시나리오, DB 백업/복원 절차, DNS 전환 계획

## QA & 배포 전략
- Staging에서 Phase 4 QA 스위트를 재사용하되, Secret Manager/Cloud Run 환경 변수 유효성 테스트를 추가한다.
- `pytest` + 특정 E2E(adminPhase4.spec.ts)만 실행해도 GCP 환경에서 필수 동작을 검증할 수 있도록 테스트 프로필을 분리한다.
- Cut-over 단계는 “Read-Only 모드 → 트래픽 이동 → 기능 확인 → 구환경 종료” 순서를 문서화하고, 실패 시 즉시 롤백하는 기준 시간을 정한다.
