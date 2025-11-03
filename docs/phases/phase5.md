# Phase 5 — GCP Migration & Platform Hardening (예정)

## 목표
- FastAPI/Next.js 서비스를 Google Cloud Run(+Cloud SQL)으로 이전해 운영 자동화 기반을 확보합니다.
- Secret Manager · Artifact Registry · Cloud Build 파이프라인을 도입해 설정·배포를 코드화합니다.
- Admin RBAC를 Google Identity(AAD/Workspace)와 연계하고 감사 로그를 중앙 수집합니다.
- Observability(Cloud Logging, Cloud Monitoring, Langfuse)를 통해 Phase 4 기능의 안정성을 높입니다.
- 데이터 커버리지 확장: OpenDART/공공데이터포털 EOD/내부 KRX 데이터를 Cloud 파이프라인으로 통합하고 향후 유료 피드 전환을 준비합니다.

## 준비 사항
- 서비스 계정·네트워크·보안 정책 설계 및 최소 권한 롤 검토 (API, Celery, Admin 콘솔 각각 검증)
- 데이터베이스 마이그레이션 수립 (Cloud SQL ↔ 기존 Postgres 스키마 이관 절차)
- 네트워크/도메인 구성 초안 (Cloud Armor, HTTPS Load Balancer, VPC 필요 여부 결정)
- KRX 데이터 상품/약관, 공시 API 라이선스/비용 비교 및 재배포 조건 파악
- 개인정보·전자금융 규정 준수 검토, 데이터 거버넌스 정책서 초안(보관 기간·파기·이중화 절차) 작성

## 일정 메모
- Phase 4 기능 안정화 후 착수, 인프라 리스크를 고려해 2~3 스프린트 배정
- Cut-over 전후로 Staging/Production 이중 운영 기간 최소 1주 확보
- IaC(Terraform 또는 Config Connector)는 첫 스프린트에서 병렬 진행해 이후 반복 배포에 활용

## 상세 설계 프레임
- **P0 (스프린트 1)**: Secret Manager 통합, Cloud Build/Artifact Registry 파이프라인, IaC 기본 스택 배치
- **P1 (스프린트 2)**: Cloud Run 서비스/Cloud SQL 연계, Celery 워커 런타임(GCE/GKE) 결정, Admin RBAC Google OAuth 연동
- **P2 (스프린트 3)**: Observability 스택(Cloud Logging, Error Reporting, Langfuse) 확장, 롤백/운영 플레이북 확정
- 모든 단계에서 Staging → Production 순차 배포와 체크리스트 기반 검증을 유지
- **사전 보강 스프린트**: Cloud 전환에 영향을 받는 UI/플로우 접근성/오퍼레이션 점검(비활성 버튼, 미연동 기능 등) 정리, 문서화 후 Phase 5 착수

### 클라우드 인프라 전환

#### 범위와 재사용 포인트
- 기존 Dockerfile과 `docker-compose.yaml`을 기반으로 Cloud Run/Cloud Build용 베이스 이미지를 생성
- Celery 워커는 Cloud Run Jobs 혹은 GKE Autopilot 중 하나로 PoC 후 결정, 공통 이미지는 Artifact Registry로 통일
- 데이터 계층(Postgres, Redis)을 Cloud SQL/MemoryStore로 이전하고, Phase 4에서 정리한 설정 스키마(`admin_phase4`)를 마이그레이션 계획에 포함
- 감사 로그 및 정적 파일은 GCS로 이관하고, Cloud Logging Sink를 통해 장기 보관 정책을 수립

#### 작업 항목 (예시)
| 작업 | 내용 | 의존성 |
|------|------|--------|
| Cloud Build 파이프라인 | Git 태그/브랜치 기반 빌드, Artifact Registry 푸시 | Dockerfile 정합성 |
| Cloud Run 서비스 | API/대시보드 각각 배포, 최소 2개 리전 설정 검토 | Secret Manager · VPC |
| Cloud SQL 마이그레이션 | pg_dump/pg_restore, 마이그레이션 테스트 스크립트 작성 | 연결 풀링/트래픽 컷오버 |
| Celery 워커 런타임 | Cloud Run Jobs vs GKE Autopilot 비교 테스트 | Redis/MemoryStore 연결 |
| Observability 통합 | Cloud Logging, Error Reporting, Langfuse 연동 | 서비스 계정/권한 |
| Cloud Tasks/Workflows 전환 | 기존 Celery 스케줄/알림 파이프라인을 관리형 서비스로 이전 | 업무 검증 |

### 데이터 커버리지 확장
- **공시/재무제표**: OpenDART와 XBRL 데이터를 Cloud Functions/Cloud Scheduler로 적재하고 GCS 장기 보관 + Cloud SQL 서브셋을 운영합니다.
- **EOD 시세**: 공공데이터포털 시세 API를 Cloud Scheduler로 일일 수집하여 GCS 저장, 대시보드에는 “일별 업데이트” 배지를 유지합니다.
- **KRX 실시간 피드**: 라이선스 옵션(General, Enterprise 등)과 발송 약관을 비교하고, Phase 5 내에 PoC 환경에서 스트리밍 파이프라인을 검증합니다.
- **데이터 품질/감시**: Cloud Logging + Langfuse 메타데이터를 연계하여 재색인 오류, API 실패를 실시간 감시하고 알림 채널에 통합합니다.

### 컴플라이언스 & 데이터 보호
- 개인정보 식별자와 금융 데이터 흐름을 재점검하고 Cloud Run↔Cloud SQL↔GCS 전 구간 암호화/접근 제어를 문서화합니다.
- Secret Manager와 감사 로그에 포함될 수 있는 민감 필드를 최소화하고, 가명 처리·마스킹 기준을 운영 정책에 추가합니다.
- GCP DPA, KRX/공시 API 재배포 약관, Toss 결제 위탁 규정을 기반으로 고객 고지/동의 절차를 업데이트합니다.
- RBAC/감사 로그 정책을 ISMS 기준에 맞춰 정기 점검 주기(분기/반기)와 책임자를 지정합니다.

### QA & 배포 전략
- pytest 스위트에 Cloud 환경 변수를 반영한 테스트를 추가하고, `pnpm test`(프런트)는 GCP 설정 변경 후에도 통과 여부를 확인합니다.
- 배포는 `admin.phase5.*` Feature Flag로 제어하고, Staging 전환 → 운영 전환 순으로 점진 롤아웃합니다.
- Cloud Build 배포 시 Slack/Webhook 알림을 연결해 운영팀이 변경 사항을 즉시 확인할 수 있게 합니다.
- Staging·Production 양쪽에 동일 트래픽을 미러링해 응답 차이를 비교하고, 주요 API·재색인·알림 시나리오를 체크리스트로 검증합니다.
- 데이터 이중화/컷오버 리허설, 비밀 회전 실패, 결제/환불 실패 등 비상 시나리오를 Tabletop/DR 드릴 형태로 실행합니다.

### 검증 체크리스트 (발췌)
- 인프라: Terraform 플랜 검토, Cloud Run 헬스체크, Cloud SQL 연결 풀 모니터링, VPC/방화벽 정책 점검
- 데이터: 마이그레이션 Dry-run(샘플 데이터), 감사 로그/GCS 보관 주기 확인, Langfuse 트레이스 완전성 확인
- 보안/법무: Secret Manager 권한 리뷰, 접근권한 부여/회수 절차 테스트, 개인정보 국외 이전 신고 여부 확인
- 운영: Slack/메일 알림 채널 동작, Cloud Monitoring 경보 임계값 테스트, 롤백 스크립트/가이드 최신화

### 리스크 & 대응
- **네트워크/보안**: Cloud Armor, VPC egress 정책 등을 통해 데이터 유출을 차단하고, Cloud SQL의 IAM DB Auth/비상 사용자 전략을 준비합니다.
- **데이터 마이그레이션**: 컷오버 전후 이중 쓰기 전략을 검토하고, 필요 시 읽기 전용 기간 또는 단계적 롤백 플랜을 마련합니다.
- **비용/라이선스**: Cloud Run/SQL/Logging 비용 추적을 위한 BQ Billing Export를 설정하고, KRX·공시 API 이용료 변동을 모니터링합니다.
