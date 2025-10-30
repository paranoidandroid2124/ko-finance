# Phase 4 — Operations Console & Guardrails (예정)

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

## 상세 설계 프레임
- **P0 (스프린트 1)**: LLM·Guardrail 설정 읽기/쓰기 API, 기본 Admin 패널, RBAC 스캐폴드
- **P1 (스프린트 2)**: RAG 컨텍스트 관리 API·UI, 벡터 재색인 트리거 연동, 감사 로그 확대
- **P2 (스프린트 3)**: Operations 패널(스케줄·API 키·알림), Langfuse/관측 토글, 배너 편집
- 모든 도메인 공통으로 Admin RBAC/감사/배포 전략은 단일 스토리로 묶어 동시 진행

### LLM & Guardrail 콘솔

#### 범위와 재사용 포인트
- 현행 LiteLLM 라우팅 파일(`litellm_config.yaml`), LLM 서비스 모듈(`llm/llm_service.py`), 가드레일 헬퍼(`llm/guardrails.py`)를 단일 소스로 묶는다.
- Admin UI 구조는 `web/dashboard/src/app/admin/page.tsx`의 `SectionCard` 패턴을 재활용해 탭 기반 상세 패널을 추가한다.
- 레거시 YAML 기반 설정을 Postgres 테이블로 이관하거나, 파일 저장 시에도 `uploads/admin` 경로에 버전 정보와 감사 메타데이터를 함께 남긴다.

#### API 제안
| 엔드포인트 | 메서드 | Payload/응답 | 비고 |
|-----------|--------|--------------|------|
| `/api/v1/admin/llm/profiles` | GET | `{ "profiles": [...] }` | LiteLLM 모델 라우팅, 재시도, 시간제한 정보 조회 |
| `/api/v1/admin/llm/profiles/{name}` | PUT | `{"model": "...", "settings": {...}}` | YAML→DB 마이그레이션 이후 단일 레코드 업서트 |
| `/api/v1/admin/llm/prompts/system` | GET/PUT | `{"channel": "chat|rag|self_check", "prompt": "...", "updatedBy": ...}` | 시스템 프롬프트 버전 관리, 최근 5개 이력 반환 |
| `/api/v1/admin/guardrails/policies` | GET/PUT | `{"intentRules": [...], "blocklist": [...], "userFacingCopy": {...}}` | `llm/guardrails.py`의 검사 기준을 JSON 스키마화 |
| `/api/v1/admin/guardrails/evaluate` | POST | `{"sample": "...", "channels": [...]}` | LiteLLM judge 모델을 호출해 미리보기, 5초 타임아웃 |

#### UI 흐름
- **탭 구조**: “모델 프로필 · 시스템 프롬프트 · 가드레일 정책” 세 탭으로 나누고, 각 탭마다 수정 전/후 비교 카드와 “안전하게 저장하기” CTA 버튼을 둔다.
- **폼 패턴**: `PlanSettingsForm.tsx`에서 사용한 로컬 상태→저장 미확인 경고 토스트를 재사용해 저장 전 사용자에게 안내한다.
- **미리보기**: Guardrail 정책 저장 전 샘플 문장을 입력해 `guardrails.evaluate`를 호출, 결과를 `ChatMessageBubble` 스타일로 보여주어 Phase 3와 말투를 일관화한다.
- **버전 타임라인**: 최근 5개 변경 이력을 `TossWebhookAuditPanel`과 같은 로그 테이블 UI로 표기, 감사 로그 링크를 제공한다.

#### 우선순위
- P0-1: 읽기 API, 시스템 프롬프트 저장, Guardrail 정책 CRUD, admin RBAC 통합
- P1: 샘플 평가 실행, LiteLLM 재시도/한계값 편집, 다중 환경 프로필(스테이징/프로덕션) 스위치
- P2: 프롬프트 회귀 테스트 자동화 훅(Trigger `parse.tasks.run_prompt_regression`), Langfuse 연동 토글

### RAG Context 관리

#### 범위와 재사용 포인트
- 현재 RAG 파이프라인은 `services/vector_service.py`, `services/rag_shared.py`, `parse/tasks.py`에서 소스·필터·벡터 재색인을 담당한다.
- Phase 3 Plan 설정 UI에서 사용한 `Quota` 입력 컴포넌트를 변형해 Top-K, 유사도 컷오프, 기본 필터를 편집하도록 확장한다.
- 재사용 가능한 Celery 태스크: `parse.tasks.queue_vector_backfill`, `parse.tasks.seed_news_feeds` 등 이름을 통일해 Admin 호출용 래퍼를 제공한다.

#### API 제안
| 엔드포인트 | 메서드 | Payload/응답 | 비고 |
|-----------|--------|--------------|------|
| `/api/v1/admin/rag/sources` | GET/PUT | `{"sources": [{"id": "...", "enabled": true, "label": "..."}]}` | DART, RSS, 내부 PDF 등 소스 토글 |
| `/api/v1/admin/rag/filters` | GET/PUT | `{"defaultFilters": {"company": [...], "sector": [...]}}` | 쿼리 전처리용 기본 필터 |
| `/api/v1/admin/rag/similarity` | GET/PUT | `{"topK": 8, "minScore": 0.62}` | `PlanQuickActionsPanel`의 RAG Top-K를 기반으로 전역 기본값 설정 |
| `/api/v1/admin/rag/reindex` | POST | `{"scope": "all|filings|news", "note": "...", "actor": "..."}` | Celery 작업 큐잉 → 진행 상태 Polling URL 반환 |
| `/api/v1/admin/rag/history` | GET | `{ "runs": [{ "id": "...", "scope": "...", "status": "...", "startedAt": ... }]}` | `uploads/admin/rag_reindex.jsonl` 또는 DB 테이블에서 조회 |

#### UI 흐름
- **소스 토글 카드**: `PlanTierPreview` 스타일을 참고해 소스별 토글과 설명을 보여주고, “따뜻한 사회적 기업” 말투로 “이 자료를 고객에게 보여드릴까요?” 안내 문구를 노출한다.
- **필터 & 임계값 폼**: `AlertBuilder`에서 사용한 슬라이더·토글 컴포넌트를 활용해 Top-K·유사도 슬라이더를 구현한다.
- **재색인 패널**: `QuickActionCard` 디자인을 재활용해 버튼 클릭 시 `reindex` API 호출, 프로그레스 상태는 `useAsyncAction` 훅(신규)으로 표시한다.
- **감사 로그 연동**: 재색인 실행 시 `/uploads/admin/rag_reindex.jsonl` 또는 DB 로그를 링크로 제공하고, 실패 시 Guardrail 경고 톤과 동일한 알림을 띄운다.

#### 우선순위
- P0-1: 소스/필터/임계값 읽기·쓰기 API, UI 기본 폼, 재색인 POST → Celery 태스크 호출
- P1: 재색인 진행률 폴링(벡터 인덱스 크기·남은 큐), 필터 프리셋 가져오기(API `GET /plan/context` 연계)
- P2: 메트릭스(Answer 정확도, RAG 경고) 대시보드 탭, Langfuse/Prometheus 통계 뱃지 표시

### Operations 패널

#### 범위와 재사용 포인트
- Celery 스케줄 정보는 `parse/celery_app.py`와 beat 설정을 읽어와 `parse.tasks.inspect_schedules`(신규) 같은 서비스 함수에서 캡슐화한다.
- 뉴스/섹터 매핑은 `parse/tasks.py`의 `seed_news_feeds`, `aggregate_news` 태스크를 Admin에서 큐잉하는 래퍼를 제공한다.
- Notification 채널 CRUD는 `/api/v1/alerts/channels` 라우터를 재사용하되, Admin 패널에서 채널별 토큰·상태·최근 전송 내역을 표시한다.
- API 키·Langfuse 토글은 `.env` 기반이므로 Key Vault(예: Postgres `admin_feature_flags` 테이블)로 이관한 뒤 Feature Flag 서비스(`services/plan_service.py` 패턴)와 공유한다.

#### API 제안
| 엔드포인트 | 메서드 | Payload/응답 | 비고 |
|-----------|--------|--------------|------|
| `/api/v1/admin/ops/schedules` | GET | `{ "jobs": [{ "id": "...", "task": "...", "interval": "...", "status": "active" }]}` | Celery beat inspect 결과, 읽기 전용 |
| `/api/v1/admin/ops/schedules/{id}/trigger` | POST | `{"actor": "...", "note": "..."}` | 특정 태스크 수동 실행, result job id 반환 |
| `/api/v1/admin/ops/news-pipeline` | GET/PUT | `{"rssFeeds": [...], "sectorMappings": {...}, "sentiment": {"threshold": 0.6}}` | RSS 소스와 섹터 매핑 관리, `parse.tasks.seed_news_feeds`와 연동 |
| `/api/v1/admin/ops/api-keys` | GET/PUT | `{"langfuse": {"enabled": true, "apiKey": "..."}, "externalApis": [...]}` | `.env` 의존 키를 안전 저장소로 이동 후 관리 |
| `/api/v1/admin/ops/notification-channels` | GET/PUT | `{"channels": [...]}` | 기존 `/api/v1/alerts/channels`를 Admin 권한으로 확장, 토큰 마스킹 |
| `/api/v1/admin/ui/banners` | GET/PUT | `{"banner": {"enabled": true, "message": "...", "audience": "all|admin"}}` | 대시보드 상단 배너 문구를 친근한 톤으로 편집 |
| `/api/v1/admin/ops/run-history` | GET | `{ "runs": [{ "id": "...", "task": "...", "status": "...", "startedAt": "...", "actor": "..."}]}` | Celery 실행 기록 및 Admin 수동 실행 감사 로그 |

#### UI 흐름
- **스케줄 & 작업 카드**: `TossWebhookAuditPanel` 레이아웃을 재사용해 최근 실행, 다음 실행 예정 시각을 표기하고 수동 실행 버튼을 둔다.
- **뉴스·섹터 설정 폼**: `AlertBuilder`의 다중 입력 필드 패턴을 활용해 RSS URL, 키워드 태그를 등록한다. 변경 시 “현장의 소식을 우리 고객에게 먼저 전해볼까요?”와 같은 안내 문구를 노출한다.
- **API 키 & 토글 패널**: `PlanQuickActionsPanel`의 2열 폼을 재활용해 Langfuse, Sentry, Slack 웹훅 토글을 제공하고, 저장 시 비밀 값은 다시 표시하지 않는다.
- **Notification 채널 관리**: 기존 채널 리스트를 읽어오되 Admin 전용으로 마지막 전송 결과, 실패 로그 링크를 표시한다.
- **배너 편집기**: Markdown 미리보기(`renderRagEvidence` 컴포넌트의 프리뷰 패턴)로 배너 문구를 살펴보고, 고객 친화 문구 추천을 Guardrail judge로 체크한다.

#### 우선순위
- P0-1: 스케줄 조회/트리거 API, 뉴스 파이프라인 큐잉, Langfuse 토글 저장소 확보
- P1: Notification 채널 Admin 편집, 배너 편집 UI, API 키 암호화 저장 레이어
- P2: 실행 이력 대시보드, Slack/Email 알림 연동, 유지보수 모드 토글

### 공통 고려 사항
- **RBAC**: Admin 전용 그룹(`role=admin_ops`)을 `schemas/api/admin.py`에 추가하고, 라우터에 `Depends(ensure_admin_role)` 가드를 둔다. 프런트는 `useSession` 확장으로 권한을 확인한다.
- **감사 로그**: 모든 변경 API는 `services/audit_log.py`(신규)에서 JSONL + DB dual-write를 수행하며, Actor/Change Note는 Phase 3 Plan Quick Actions와 동일 힌트를 사용해 입력받는다.
- **스키마 관리**: 새 설정 테이블 생성 시 Alembic 마이그레이션 + seed 스크립트를 포함해 CI에서 `pytest tests/test_admin_api.py -k phase4` 스모크를 추가한다.
- **배포 전략**: Phase 4 초기에는 읽기 전용 모드로 배포하고, QA 후 쓰기 기능을 순차 활성화한다. 각 도메인 별로 Feature Flag(`admin.phase4.llm`, `admin.phase4.rag`, `admin.phase4.ops`)를 두어 점진적 롤아웃을 지원한다.
- **QA & 모니터링**: pytest에 Guardrail/RAG/Operations 전용 테스트 케이스를 추가하고, Playwright는 `adminPhase4.spec.ts`로 세 도메인을 순회한다. Langfuse 토글, 재색인 트리거 등은 Staging에서만 실행하도록 보호 스위치를 둔다.
