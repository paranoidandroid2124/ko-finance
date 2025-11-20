# Nuvien Help Center Kickoff

프런트엔드 우상단 프로필 메뉴와 설정 패널에 노출된 **도움말** 버튼(`web/dashboard/src/components/layout/UserMenu.tsx:132`, `web/dashboard/src/components/settings/SettingsOverlay.tsx:104-131`)이 사용자를 안내할 수 있도록, 전사 기능을 망라한 문서 설계 초안을 정의합니다. 이 문서는 `docs/help` 아래에서 실제 가이드를 작성하기 위한 기준이자 백로그로 사용합니다.

## 목표와 원칙
- **한 곳에서 찾기**: Auth·Dashboard·Watchlist·Labs·Billing까지 흩어진 정보를 단일 목차 아래로 통합합니다.
- **사용자 관점**: “무엇을 할 수 있고, 어떻게 해야 하며, 실패 시 어디를 확인할지”에 답하도록 How-to + FAQ 구성을 기본으로 합니다.
- **출처 연결**: 각 토픽은 실제 동작을 정의한 코드·API·운영 문서를 연결합니다.
- **점진 배포**: 우선순위 높은 시나리오부터 `docs/help/<slug>.md`에 작성한 뒤, 정적 사이트(예: docs.kfinance.co)로 퍼블리시합니다.

## 진입 경로 & 정보 아키텍처
| 위치 | 컴포넌트 | 링크 | 비고 |
| --- | --- | --- | --- |
| Top Bar 프로필 메뉴 | `web/dashboard/src/components/layout/UserMenu.tsx:132` | `https://docs.kfinance.co/help` | 글로벌 도움말 진입점 |
| Settings Overlay “도움말 센터” | `web/dashboard/src/components/settings/SettingsOverlay.tsx:104-131` | 동일 | 플랜·LightMem·알림 설정과 인접 |
| 향후: 알림/Watchlist 빈 상태 | `web/dashboard/src/app/watchlist/page.tsx` | (미정) | Rule Wizard 내부 툴팁 필요 |

Help Center 정보 구조는 다음 5개 허브 아래 개별 문서로 분기합니다.
1. **시작하기 & 계정** (Auth, 환경 준비)
2. **리서치 작업 흐름** (Dashboard, Filings, Company, Chat)
3. **감시 & 알림** (Watchlist, LightMem, Digest)
4. **데이터 인사이트 & Labs** (News, Sector Signals, Labs)
5. **플랜·결제·운영** (Plan, Billing, Admin/지원)

## 1차 문서 인벤토리
| 구분 | 주요 사용 사례 | 문서 형태 | 프론트/백엔드 포인트 | 기존 커버리지 & Gap |
| --- | --- | --- | --- | --- |
| 계정 & 온보딩 | 가입, 이메일 검증, 비밀번호 재설정, 공용/엔터프라이즈 SSO 문의 | How-to + FAQ | `web/routers/auth.py`, `web/dashboard/src/app/auth/*` | `docs/auth/email_password_design.md`에 API 설명은 있지만 사용자 가이드는 없음 |
| 대시보드 빠른 개요 | 홈 KPI, 글로벌 검색, 섹터 스캐터 해석법 | Walkthrough | `web/dashboard/src/app/page.tsx`, `hooks/useDashboardOverview.ts` | README 상단에만 간략 설명 |
| 공시 탐색 & PDF Evidence | 기간/감성 필터, 요약·핵심 사실, Chat 연계, PDF 뷰어 오픈 실패 시 대처 | How-to + Troubleshooting | `web/dashboard/src/app/filings/page.tsx`, `hooks/useFilings.ts`, `web/routers/filing.py` | 문서 부재 |
| Company Snapshot | 재무보드, Major Events, PlanLock가 걸린 Restatement/Fiscal Alignment 안내 | Feature guide | `web/dashboard/src/app/company/[ticker]/page.tsx`, `web/routers/company.py` | 없음 |
| Watchlist & Alert Rules | Rule Wizard, 채널 검증(Slack/Email/Webhook 등), LightMem와 Digest 전송, Slack/Email 템플릿 | How-to + FAQ | `web/dashboard/src/app/watchlist/page.tsx`, `lib/alertsApi.ts`, `web/routers/alerts.py` | README에 간단 언급뿐 |
| 뉴스 & 섹터 신호 | NewsFilterPanel, Topic Ranking, SectorHotspotScatter 해석법 | Walkthrough | `web/dashboard/src/app/news/page.tsx`, `hooks/useNewsInsights.ts` | 없음 |
| Research Copilot(Chat) | 세션 생성, 인용/하이라이트, LightMem, Guardrail 오류, 플랜별 쿼터 | How-to + Troubleshooting | `web/dashboard/src/app/chat/page.tsx`, `store/chatStore.ts`, `web/routers/rag.py` | 없음 |
| Labs (Digest/Event Study/Evidence) | 실험 기능 설명, 데이터 샘플, 플랜 잠금 | Overview + Warnings | `web/dashboard/src/app/labs/*`, `web/routers/event_study.py` | 없음 |
| 플랜 & 결제 | PlanSummaryCard, Trial 시작, Toss 결제 흐름, 실패 시 조치 | How-to | `web/dashboard/src/components/plan/*.tsx`, `web/routers/plan.py`, `web/routers/payments.py`, `services/plan_catalog_service.py` | README 일부 + ops 문서 파편 |
| 퍼블릭 미리보기 & 게스트 | `/public` 페이지 활용법, Rate Limit, 질문 실패 대응 | FAQ | `web/dashboard/src/app/public/page.tsx`, `web/routers/public.py` | 없음 |
| 운영/지원 채널 | Slack/Email 지원 경로, 장애시 제공해야 할 로그 | Runbook | `scripts/sync_audit_traces.py`, `docs/ops/*` | ops 문서에 산재, 사용자용 안내 부재 |

## 섹션별 상세 요구사항

### 1. 계정 & 온보딩
- **대상자**: 신규 사용자, 테스트 계정 발급자, 고객사 관리자
- **핵심 질문**
  - 이메일/비밀번호 가입 절차와 인증 메일 재발송 방법
  - 기존 소셜/사내 IdP 연동 여부, 지원 일정
  - 비밀번호 분실, 세션 잠금 해제 흐름
- **콘텐츠 제안**
  - `docs/help/account-getting-started.md` (How-to)  
    - 가입 → 이메일 인증 → 최초 로그인 체크리스트
    - `.env` 기반 로컬 로그인 시 주의점 (README 3장과 연결)
  - `docs/help/account-troubleshooting.md` (FAQ)  
    - `auth_tokens` rate limit, Argon2 오류 등 백엔드 에러 코드를 표로 정리
- **출처**
  - FastAPI 라우터: `web/routers/auth.py`
  - NextAuth 설정: `web/dashboard/src/lib/authOptions.ts`
  - 설계 문서: `docs/auth/email_password_design.md`

### 2. 대시보드 & 글로벌 검색
- **대상자**: 애널리스트, 세일즈 데모 담당자
- **필요 내용**
  - KPI 카드(최근 공시 수, 감성 지수, Alert 요약 등) 해석법
  - GlobalSearchBar → SearchResults 탭 구조 (공시/뉴스/테이블/차트) + 페이지네이션
  - SectorHotspotScatter / SectorSparkCard 읽는 방법과 데이터 갱신 주기(`useSectorSignals`)
- **콘텐츠 제안**
  - `docs/help/dashboard-overview.md` : 투어형 스크린샷 + “특정 탭이 비었을 때 확인할 항목”
  - `docs/help/search-guide.md` : 쿼리 구문, 감성 필터 표시, Infinite scroll 동작
- **출처**
  - `web/dashboard/src/app/page.tsx`
  - `hooks/useDashboardOverview.ts`, `hooks/useSearchResults.ts`
  - API: `web/routers/dashboard.py`, `web/routers/search.py`

### 3. 공시 탐색 & Evidence
- **대상자**: 심층 리서치 사용자, 감사/Compliance 팀
- **핵심 질문**
  - Filings 리스트의 기간(days)·감성 필터 기준
  - FilingDetailPanel에서 Summaries/Facts가 비거나 오류날 때 조치
  - “PDF 열기” 버튼이 막힐 때(사내 방화벽 등) 대안
  - “질문하기” → Chat 세션이 만들어지는 조건 (요약 필수)
- **콘텐츠 제안**
  - `docs/help/filings-explorer.md` (How-to) + 오류 FAQ
  - `docs/help/evidence-viewer.md` : EvidenceWorkspace, diff, 하이라이트 잠금 (PlanLock) 소개
- **출처**
  - `web/dashboard/src/app/filings/page.tsx`, `components/filings/*`
  - 백엔드: `web/routers/filing.py`, `web/routers/rag.py` (evidence diff)

### 4. Company Snapshot
- **대상자**: 커버리지 애널리스트, 세일즈
- **핵심 질문**
  - KeyMetrics/FinancialStatements 데이터 출처 (DART vs 내부 모델)
  - Restatement Radar, Fiscal Alignment, Evidence Bundle가 왜 잠겨있는지 (PlanLock)
  - 최근 본 회사/추천 섹션 로컬 스토리지 동작
- **콘텐츠 제안**
  - `docs/help/company-snapshot.md`
    - 위젯별 데이터 설명 + 플랜별 접근 표
    - “데이터가 없습니다” 빈 상태 원인 체크리스트
- **출처**
  - `web/dashboard/src/app/company/[ticker]/page.tsx`
  - API: `web/routers/company.py`

### 5. Watchlist · Alerts · LightMem
- **대상자**: 리스크/트레이딩 팀, 운영자
- **핵심 질문**
  - Watchlist Radar 필터(기간, 감성, 정렬, 그룹) 의미
  - Rule Wizard 단계 + allowed 채널(Slack/Email/Telegram/Webhook/PagerDuty) 입력 형식
  - Digest 전송 시 즐겨찾기/최근 대상 관리(localStorage) 흐름
  - LightMem 설정이 막혔을 때(Free 플랜) 에러 메시지 대응
- **콘텐츠 제안**
  - `docs/help/watchlist-rules.md` (Step-by-step)
  - `docs/help/alerts-channels.md` (채널 검증 규칙, 실패 로그 수집법)
  - `docs/help/lightmem-personalization.md` (개념, 플랜별 허용 범위, 개인정보 FAQ)
- **출처**
  - FE: `web/dashboard/src/app/watchlist/page.tsx`, `components/watchlist/*`, `components/settings/UserLightMemSettingsCard.tsx`
  - API: `web/routers/alerts.py`, `web/routers/user_settings.py`
  - Helpers: `web/dashboard/src/lib/alertsApi.ts`

### 6. 뉴스 & 섹터 인사이트
- **대상자**: 모니터링·커뮤니케이션 담당자
- **핵심 질문**
  - NewsFilterPanel 필터 옵션 및 기본값
  - Topic Ranking/NewsSignal와 SectorHotspotScatter 연계
  - 데이터 비었을 때 RSS/ingest 상태 확인법
- **콘텐츠 제안**
  - `docs/help/news-insights.md`
  - `docs/help/sector-signals.md`
- **출처**
  - `web/dashboard/src/app/news/page.tsx`, `components/news/*`, `components/sectors/*`
  - API: `web/routers/news.py`, `web/routers/sectors.py`

### 7. Research Copilot (Chat)
- **대상자**: 리서처, 세일즈 데모
- **핵심 질문**
  - 세션 생성/저장 위치(`store/chatStore.ts` zustand)와 보관 정책
  - RAG 모드, 인용, 하이라이트 맵핑, LightMem warm-start 동작
  - Guardrail/Judge 오류 메시지(`rag.py`) 해석, 재시도 방법
  - PlanLock/Quota (chatRequestsPerDay) 초과 시 흐름
- **콘텐츠 제안**
  - `docs/help/chat-howto.md` (워크플로)
  - `docs/help/chat-troubleshooting.md` (에러 코드 표 + self-check 의미)
  - 샘플 질문/대답 아카이브
- **출처**
  - FE: `web/dashboard/src/app/chat/page.tsx`, `components/chat/*`
  - API: `web/routers/rag.py`, `web/routers/chat.py`

### 8. Labs & 실험 기능
- **대상자**: 얼리어답터, 내부 세일즈
- **내용**
  - Digest Lab: Daily/Weekly 옵션, sample 데이터 사용 여부
  - Event Study Lab: 이벤트 타입/시장/시총 필터, 시그니처 계산식
  - Event Study Export: 보고서 PDF·ZIP 다운로드 흐름, `reports.event_export` + `timeline.full` 엔타이틀먼트(Pro 이상) 필요, RBAC 오류 메시지 대응, presigned URL 만료 정책
  - Evidence Lab: 환경변수 `NEXT_PUBLIC_ENABLE_LABS`, PlanUpgrade 콜백
- **콘텐츠 제안**
  - `docs/help/labs-overview.md`
  - 각 실험별 미리보기/제한 사항 경고
- **출처**
  - `web/dashboard/src/app/labs/*`
  - API: `web/routers/event_study.py`, `hooks/useDigestPreview.ts`, `useCompanyTimeline.ts`

### 9. 플랜, Trial, 결제
- **대상자**: 구매 의사결정자, 내부 매니저
- **핵심 질문**
  - PlanSummaryCard: quota/entitlement 의미, trial countdown
  - PlanAlertOverview: 잔여 슬롯/채널 정보 확인법
  - PricingPage: plan_catalog.json 기반 카드 관리, CTA 흐름
  - Toss 결제 성공/실패/웹훅 처리, 업그레이드 반영 시간
- **콘텐츠 제안**
  - `docs/help/plan-and-billing.md`
  - `docs/help/payments-toss.md` (명세 + 실패 대응)
- **출처**
  - FE: `components/plan/*`, `app/pricing/page.tsx`
  - API: `web/routers/plan.py`, `web/routers/payments.py`
  - Service: `services/plan_catalog_service.py`

### 10. 퍼블릭 프리뷰 & 게스트 접근
- **대상자**: 비로그인 사용자, 세일즈 캠페인
- **내용**
  - `/public` 페이지 구성 (공시 리스트 + 간단 챗)
  - Public API rate limit(시간당 5회) 및 에러 메시지
  - 로그인/가입 CTA 위치
- **콘텐츠 제안**
  - `docs/help/public-preview.md`
- **출처**
  - `web/dashboard/src/app/public/page.tsx`
  - API: `web/routers/public.py`

### 11. 운영 & 지원
- **대상자**: 고객지원, SRE, 세일즈 엔지니어
- **내용**
  - 장애 시 수집해야 할 항목 (요청 ID, 사용자, timestamp)
  - Slack/Email/전화 등 escalation 경로
  - 감사 로그 (`scripts/sync_audit_traces.py`), `docs/ops/*` 링크
- **콘텐츠 제안**
  - `docs/help/support-runbook.md`
- **출처**
  - Ops 문서: `docs/ops/*`, `docs/policies/*`
  - 스크립트: `scripts/sync_audit_traces.py`

## 작성 우선순위 & 마일스톤
1. **Critical onboarding**: 계정/플랜/Watchlist (사용자 문의 다발 구간) → 1주 내 초안
2. **Daily workflow**: Dashboard, Filings, Chat → 2주차
3. **Labs & Advanced**: Company, Labs, Public → 3주차
4. **Operations**: Support/Runbook → 4주차 (내부 전용)

각 문서는 다음 템플릿을 따릅니다.
- 소개 & 대상자
- 빠른 시작 (3단계 이내)
- 심화 사용법 (필터/옵션 표)
- 자주 묻는 질문 (에러 메시지 중심)
- 관련 API & 로그 확인 포인트
- 추가 문의 채널

## 다음 단계 체크리스트
- [ ] `docs/help/account-getting-started.md` 초안 작성
- [ ] `docs/help/watchlist-rules.md`에 Rule Wizard 캡처 추가
- [ ] `docs/help/chat-howto.md`에 Guardrail 에러 사례 수집
- [ ] mdx/정적 사이트 빌드 파이프라인 설계 (`docs` 디렉터리 → docs.kfinance.co)
- [ ] 프런트엔드 Help 링크를 환경변수 혹은 내부 경로로 교체하는 로드맵 수립

---
문의: #product-documentation (Slack) / product@kfinance.co  
Maintainer: @docs-team (2025.11 기준)
