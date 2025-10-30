# Phase 3 Plan - Pro/Enterprise Feature Enablement

> Timebox: 2025-12-05 ~ 2025-12-19 · Owner: TBD · Status: Draft

## Status Update (2025-11-03)
- 알림/플랜 백엔드 끈을 1차로 묶어 QA 파란불을 켰어요.
  * `models/alert.py`와 `ops/migrations/20251205_create_alert_tables.sql`이 규칙·발송 테이블을 만들고, `ops/migrations/20251205_alerts_notes.md`로 배포 런북도 챙겨뒀어요.
  * `services/alert_service.py`, `services/alert_channel_registry.py`, `schemas/api/alerts.py`, `web/routers/alerts.py`가 플랜별 슬롯·채널 검증과 CRUD 흐름을 한곳에서 처리합니다.
  * `services/plan_service.py`, `web/deps.py`, `web/routers/plan.py`가 요청마다 PlanContext를 만들어주고, 클라이언트가 `/api/v1/plan/context`를 통해 같은 정보를 받게 되었어요.
- 프런트에서는 플랜 스토어와 락 UX가 살아나고 있어요.
  * `web/dashboard/src/store/planStore.ts`와 `web/dashboard/src/components/plan/PlanProvider.tsx`가 플랜 컨텍스트를 초기화하고, `web/dashboard/src/components/ui/PlanLock.tsx`가 업그레이드 안내 문구를 친근하게 다듬었습니다.
  * `web/dashboard/src/components/alerts/AlertBuilder.tsx`, `ChannelEditor.tsx`, `planMessaging.ts`, `useAlertBuilderState.ts`, `useAlertChannels.ts`가 플랜별 메시지·채널 토글 로직을 공유하도록 정리됐어요.
  * `web/dashboard/src/components/ui/AlertBell.tsx`, `AlertBellPanel.tsx`, `AlertBellTrigger.tsx`, `useAlertBellController.ts`로 벨 인터랙션을 분리해 핀·포커스·토스트 흐름이 부드러워졌습니다.
- Settings/Admin에서는 플랜 경험을 바로 미리보기할 수 있게 됐어요.
  * `web/dashboard/src/components/plan/PlanSummaryCard.tsx`, `PlanAlertOverview.tsx`, `PlanTierPreview.tsx`가 플랜/알림 한도 카드와 티어 미리보기를 제공하고, Settings·Admin 페이지(`web/dashboard/src/app/settings/page.tsx`, `.../admin/page.tsx`)에 적용됐습니다.
  * PlanLock/AlertBell 패널·Alert Bell 트리거 카피를 사회적 기업 톤으로 재작성해 업그레이드 CTA와 소식 안내가 자연스러워졌고, 업그레이드 버튼은 토스페이먼츠 결제 플로우를 예고합니다.
- QA 자산도 든든하게 쌓였습니다.
  * Storybook: `web/dashboard/src/components/alerts/__stories__/AlertBuilder.stories.tsx`, `ChannelCard.stories.tsx`, `PlanMessaging.stories.tsx`, `web/dashboard/stories/PlanLock.stories.tsx`로 플랜·상태별 화면을 캡처했어요.
  * 테스트: `web/dashboard/src/testing/fixtures/alerts.ts`, `web/dashboard/tests/alerts/AlertBuilderFlows.spec.tsx`, `planStore.spec.ts`, `PlanSummaryCard.spec.tsx`, `PlanAlertOverview.spec.tsx`, `web/dashboard/tests/e2e/alertBuilder.spec.ts`, `alertsPlan.spec.ts`가 알림·플랜 기본기를 검증합니다.
- 남은 퍼즐은 이렇게 준비 중이에요.
  * Settings/Admin에서 플랜 기본값을 실제로 저장할 수 있도록 PATCH API와 UI 편집 흐름(`planStore` 업데이트, 토스트) 연결이 필요합니다.
  * PlanLock 업그레이드 CTA는 토스페이먼츠 결제 플로우와 연동 예정이며, 결제 페이지/웹훅 처리가 아직 남아 있어요.
  * Admin 퀵 액션(큐 재처리, 플랜 토글, 모니터링)과 RBAC/감사 로그, 알림 채널 비밀값 배포는 다음 단계에서 구현합니다.

## Status Update (2025-10-30)
- 긴급 리팩터링 세트를 모두 마무리했습니다. 이제 파이프라인이 흔들려도 다시 일으켜 세울 수 있는 안전망이 생겼어요.
  * `parse/tasks.py::process_filing`은 단계별 성공/실패 로그와 트랜잭션 재구성 기능을 갖춰, 실패 시 체크포인트부터 재실행할 수 있습니다.
  * LLM/RAG 증거 정규화 로직을 `services/rag_shared.py`로 통합해 `web/routers/rag.py`와 `services/vector_service.py`가 훨씬 간결해졌고, API 디버깅 난이도가 낮아졌습니다.
  * 테스트 환경을 PostgreSQL 기준으로 통일하고 `.env`·`.env.local`을 정리했습니다. `tests/conftest.py` 픽스처 개편과 fitz 스텁 덕분에 pytest 53개 항목이 모두 통과했습니다.
- 권장 레벨 리팩터링도 완료했습니다. 알림 경험이 훨씬 또렷해졌어요.
  * `AlertBuilder`는 `useAlertBuilderState`와 `ChannelEditor`로 분리해 830여 줄짜리 단일 구조에서 벗어났습니다. 리셋/채널 로직이 모듈화돼 테스트와 확장이 쉬워졌습니다.
  * `AlertBell`은 `useAlertBellController`, `AlertBellTrigger`, `AlertBellPanel`로 역할을 나눠 핀·포커스·빌더 토글을 부드럽게 제어합니다.
  * `services/alert_service.py::evaluate_due_alerts`를 규칙 조회→평가→발송 단계로 정리하고, `_fetch_active_rules`, `_process_rule`, `_dispatch_rule_notifications`가 각 역할을 책임집니다.
  * 뉴스 윈도우 집계는 `services/aggregation/news_statistics.py` 헬퍼를 재사용해 `parse/tasks.py::tally_news_window`와 길이별 윈도우 메트릭이 동일 로직을 공유합니다.
- 참고 레벨 과제도 정리했습니다.
  * `tests/setupTests.ts`에 `resetChatStores`를 노출해 채팅 스토어 리셋 유틸을 한 곳에서 재사용하고, 관련 테스트를 모두 갱신했습니다.
  * `/alerts/channels/schema` 엔드포인트와 `useAlertChannelSchema` 훅을 추가해 프런트/백엔드가 같은 검증 규칙·메타데이터를 공유합니다.
  * `llm/llm_service.py`에 `_run_json_prompt` 등 공용 헬퍼를 도입해 모델 호출/응답 검증 패턴을 단일화했습니다.
- 자동화·운영 안정화도 병행했습니다.
  * `ingest/dart_seed.py`는 `IntegrityError`를 잡아 중복 삽입을 건너뛰고, Docker Compose에는 Postgres healthcheck와 서비스 의존 조건을 넣어 초기 기동 실패를 줄였습니다.
  * Flower 대시보드를 추가해 Celery 큐 적체를 바로 확인할 수 있게 했고, `scripts/init_db.py`에 DB 재시도 로직을 넣었습니다.
- 다음 단계로 Settings/Admin을 Phase 3 범위에 편입했습니다.
  * Settings 페이지에서 플랜 정보·알림 기본값을 직접 다룰 수 있도록 API와 UI를 연결합니다.
  * Admin 콘솔은 별도 도메인으로 분리하고, 큐 모니터링·플랜 토글·재처리 툴을 MVP 범위에 담을 예정입니다.

## Status Update (2025-10-28)
- 전체 Phase 3 진행률은 약 35%입니다. 3A 기반 작업은 거의 마무리됐고, 3B 알림 플랜 자산 설계를 본격적으로 준비하고 있어요.
- **3B 스토리북·테스트 자산**
  * AlertBuilder·ChannelCard·planMessaging에는 아직 Storybook·RTL·Playwright 커버리지가 없어 우선순위를 정리했고, 필요한 목데이터/스토어 리셋 요구사항을 정의했습니다.
  * Storybook(web/dashboard/src/components/alerts/__stories__), RTL 테스트(web/dashboard/tests/alerts), Playwright(web/dashboard/tests/e2e) 디렉터리 구조를 점검해 재사용 가능한 유틸 초안을 작성했습니다.
  * 다음 단계는 AlertBuilder 상태(기본·편집·플랜 잠김·채널 제한)별 스토리, ChannelCard 채널 타입·에러 시나리오, planMessaging 플랜별 안내 스토리를 실제 자산으로 채우는 일입니다.
- **테스트 & QA 인프라**
  * 테스트 환경 API 모킹 전략(MSW vs 하드코드 fetch)을 비교 중이며, CI 명령(pnpm storybook, pnpm test, Playwright)을 어떻게 연계할지 영향도를 검토하고 있습니다.
  * design/phase3_plan.md와 QA 체크리스트에 스토리북·테스트 자산 섹션을 친근한 카피로 업데이트할 예정입니다.

## Status Update (2025-10-29)
- 권장 리팩터링 4건에 대해 현황 조사를 마쳤고 메모를 축적했습니다.
  * AlertBuilder는 834줄짜리 단일 컴포넌트에서 벗어나기 위해 상태/채널 로직을 분리했고, 테스트 작성이 쉬운 구조로 정리했습니다.
  * AlertBell은 패널 열림 제어, 빌더 모달, 세션 전환, 텔레메트리, 토스트를 분리해 훅 중심으로 재구성했습니다.
  * services/alert_service.py의 evaluate_due_alerts는 규칙 조회→평가→발송 단계를 나눠 _fetch_active_rules, _process_rule, _dispatch_rule_notifications로 역할을 분리했습니다.
  * parse/tasks.py::tally_news_window와 services/aggregation/news_metrics.py 간 중복 계산을 
ews_statistics.py 헬퍼로 통합했습니다.
- AlertBuilder 리팩터링과 AlertBell 재정비, 알림 평가 파이프라인 모듈화, 뉴스 집계 중복 제거 등 진행 현황을 기록했습니다.

## Status Update (2025-12-05 ~ 2025-12-18)
- 12/05: Phase 3 진행률 45%. 알림 백엔드 작업 75%, AlertBuilder/AlertBell UI refinements 진행 중.
- 12/10: Celery 인프라 구축 100%, 알림 백엔드 100%, 프런트 Alert Builder & Bell 60%, Storybook/QA 자산 20%.
- 12/15: Alert Builder & Bell 85%, Storybook/RTL/Playwright 40%, QA & Docs 35%.
- 12/18: 알림 프런트 100%, Storybook/테스트 55%, QA & Docs 45%. 남은 TODO는 Storybook 마무리·QA 자산·release note·Playwright 시나리오.

## 1. Scope & Goals
- 플랜 잠금(락 컴포넌트), Peer 비교 내보내기, 증빙 보존 등 Phase 1-2 준비 항목을 Phase 3에서 완성합니다.
- 플랜별 업그레이드 모달, 락 CTA, Plan Messaging 등 친근한 UX를 제공해 업그레이드 전환을 돕습니다.
- Alert Builder/Alert Bell을 중심으로 Pro/Enterprise 알림 경험을 강화합니다.
- Settings/Admin 기능을 Phase 3 범위에 포함해 운영 환경까지 정비합니다.

## 2. Execution Backlog
| Work Item | Track | Key Files | Notes |
| --- | --- | --- | --- |
| Storybook/테스트 자산 | Frontend QA assets | web/dashboard/src/components/alerts/__stories__, web/dashboard/tests/alerts, web/dashboard/tests/e2e | 진행 중 (2025-10-29) - AlertBuilder·ChannelCard·planMessaging stories/RTL/Playwright 자산 보강 (PlanSummaryCard/PlanAlertOverview spec 추가 완료) |
| Peer comparison export | Component/API | web/dashboard/src/components/company/PeerTable.tsx, web/routers/companies.py | CSV export & 감사 로깅 |
| Notification worker tasks | Backend | parse/tasks.py, services/notification_service.py | Email/Slack/Webhook/PagerDuty 채널 발송, beat 잡 TBD (2025-12-05) |
| Evidence snapshot retention pipeline | Backend/Data | services/evidence_service.py, parse/tasks.py, infra (Cloud Scheduler/Run) | 90일 초과 스냅샷 정리, GCS 보존, DSAR 삭제 처리 |
| Analytics events | Instrumentation | web/dashboard/src/lib/analytics.ts | 업그레이드 클릭, 락 뷰 트래킹 |
| Documentation update | Doc | design/phase3_release_notes.md | 플랜 매트릭스 & 기능 요약 반영 |
| Settings 페이지 (플랜/알림 기본값) | Frontend + API | web/dashboard/src/app/settings/*, services/plan_service.py, web/routers/plan.py | UI 카드/미리보기 적용 (2025-11-03), 저장 PATCH/토스페이먼츠 결제 연동 준비 |
| Admin 콘솔 (별도 도메인) | Admin/Infra | web/admin/*(신규), services/admin_*, docker-compose.yaml | 플랜 카드/미리보기 적용, 큐 모니터링·플랜 토글·재처리 툴 MVP 및 RBAC/감사 로그 구현 예정 |
| Flows 결제 연동 | Payments | web/dashboard/src/components/ui/PlanLock.tsx, services/payments/*(TBD) | 토스페이먼츠 결제 페이지/웹훅 설계 및 업그레이드 버튼 연결 |

## 3. Workstreams
### 3.1 Design / UX
- 플랜별 업그레이드 모달, 가격 비교 배너, 락 아이콘 카피를 확정합니다.
- Alert Builder 플로우(스텝퍼 vs 단일 모달), 성공 토스트, 에러 처리 UX를 다듬습니다.
- 락 상태 툴팁에 친근한 가치 제안 문구를 제공합니다.

### 3.2 Frontend Implementation
- 플랜 컨텍스트 SSR 하이드레이션, 알 수 없는 플랜 시 Free fallback.
- 락 컴포넌트를 검색 카드, 증빙 패널, Peer 테이블 버튼에 연결합니다.
- Alert Builder 모달 검증/채널 관리/플랜 제한을 구현하고 Storybook 및 테스트를 보강합니다.
- Settings 페이지에 플랜 요약·알림 한도 카드와 티어 미리보기(`PlanTierPreview`)를 적용하고, 플랜 기본값 저장 PATCH·토스페이먼츠 결제 플로우를 연결합니다.
- Admin 콘솔 전용 번들을 준비하고, 큐/알림 상태 모니터링 + 플랜 토글/재처리 퀵 액션을 토스페이먼츠 결제 정보와 함께 제공합니다.

### 3.3 Backend / Data
- 알림 스키마 정의(트리거, 임계값, 채널, 플랜 티어) 및 마이그레이션(ops/migrations/20251205_create_alert_tables.sql).
- API(POST/GET /alerts)에 플랜/쿼터 가드를 적용하고 로깅을 강화합니다.
- Email/Slack/Webhook/PagerDuty 채널 어댑터를 통합하고 백오프 로직을 마련합니다.
- 증빙 보존 작업(플랜별 정책 윈도 계산, GCS 이동, 만료/DSAR 삭제)을 자동화합니다.
- 저장소 사용량 대시보드와 모니터링을 도입합니다.
- Settings/Admin 전용 API와 RBAC·감사 로그·독립 도메인 라우팅을 설계합니다.

### 3.4 QA & Docs
- 플랜 스위치 테스트 시나리오(Free/Pro/Enterprise)로 UI 가이드를 검증합니다.
- 알림 생성·발화·사용자 수신 엔드투엔드 테스트를 수행합니다.
- 문서 업데이트: 가격표, 기능 사용 가능 매트릭스, 알림 사용 가이드에 Phase 3 내용을 반영합니다.
- 증빙 보존 SOP와 DSAR 런북을 문서화합니다.
- 알림 마이그레이션 노트(ops/migrations/20251205_alerts_notes.md)를 QA 회귀 자산과 연결합니다.

## 4. Data Requirements
- Alerts: target_type(filing/news/sector), trigger_metric, operator, threshold, cooldown_minutes, channel.
- Plan store: plan_tier, expires_at, entitlements 배열.
- Export audit: user_id, plan_tier, export_type, timestamp, row_count.
- Evidence retention: snapshot_urn_id, snapshot_hash, created_at, plan_tier, storage_location, expires_at, deletion_processed_at.

## 5. Plan Lock Mapping
| Feature | Free | Pro | Enterprise |
| --- | --- | --- | --- |
| Alert builder | 제한 | 이메일 허용 | 이메일 + Webhook 허용 |
| Peer CSV export | 제한 | 최대 100행 | 전체 행 |
| Evidence bundle export | 제한 | 허용 | 허용 |
| Upgrade modal | 업그레이드 CTA | 관리 화면 | 관리 화면 |
| Analytics usage dashboard | 제한 | 허용 | 허용 |

## 6. Risks & Mitigations
- 알림 과다로 인한 이탈 → 기본 쿨다운·합리적 임계값 제공, 저장 전 미리보기.
- 플랜 정보 불일치(백엔드 vs 프런트) → API 단일 소스 유지, 불일치 시 Free fallback, 로깅 강화.
- 락 UI 피로감 → 인라인 가치 요약, 문서 링크 제공, 탐색 차단 최소화.
- 보존 정책 미준수 → 구성으로 정책 고정, 모니터링과 정기 점검 수행.

## 7. Milestones & Checkpoints
| Milestone | Expected Date | Owner | Status |
| --- | --- | --- | --- |
| Upgrade UX finalized | 2025-12-07 | Design | In Progress (PlanLock 카피·배지 준비됨) |
| Plan store integrated | 2025-12-09 | Frontend | In Progress (컨텍스트 API·스토어 연결 완료) |
| Alert schema & API ready | 2025-12-12 | Backend | In Review (CRUD 라우터·검증 병합) |
| Lock components applied across app | 2025-12-15 | Frontend | In Progress (PlanLock/AlertBell 재구성) |
| Evidence retention job live (prune + archive) | 2025-12-16 | Backend/Data | Planned |
| Alert E2E test pass | 2025-12-18 | QA | In Progress (Playwright 스켈레톤 준비) |

## 8. QA Checklist
- Functional: 락 배지 노출, 업그레이드 모달 분석 이벤트, 플랜별 알림 생성·발화 확인.
- Accessibility: 락 툴팁 가독성, Alert Builder 폼 포커스 복원, 스크린리더 안내 멘트 점검.
- Performance: 알림 생성 API < 500ms, 락 애니메이션 < 220ms, 플랜 변경 시 리렌더 최소화.
- Data retention: 스냅샷 정리 회귀, GCS 업로드, DSAR 삭제 엔드투엔드 검증.
- Analytics/logging: 업그레이드 CTA 클릭 이벤트, 알림 발화 이벤트(트리거 메타데이터 포함), 내보내기 감사 로그.
- Regression assets: Alert Builder Storybook(생성/잠금/복제), ChannelCard Storybook(에러 케이스), planMessaging RTL, AlertBell 포커스 RTL, Alerts plan Playwright 스켈레톤.

## 9. Sign-offs
- Design | Product | Engineering | Compliance

---

### Settings & Admin 추가 범위 (Phase 3)
- Settings 페이지: 플랜 정보·알림 기본값을 UI에서 수정할 수 있도록 API와 연동하고, 플랜 잔여 슬롯/만료일을 표기합니다.
- Admin 콘솔: 별도 도메인으로 분리해 큐 모니터링·플랜 토글·재처리 툴을 제공하고 RBAC/감사 로그를 정비합니다.
- 인프라: Docker Compose 및 배포 스크립트에 Flower·healthcheck를 추가하고 운영 모니터링 지표를 정리합니다.

