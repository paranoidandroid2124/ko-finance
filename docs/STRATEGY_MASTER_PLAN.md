# 🧭 KO-FINANCE: Strategic Master Plan & Product Vision
> **Version:** 2.0.0 (The "Generative UI" Pivot)  
> **Last Updated:** 2025-11-19  
> **Author:** Product Strategy Team  
> **Mission:** Bloomberg의 깊이를, ChatGPT의 쉬움으로 제공한다.

---

## 1. 전략적 피벗 (Strategic Pivot)
### 1.1 핵심 문제 진단 (The Problem)
기존 금융 SaaS(S&P CapIQ, Refinitiv)와 초기 우리의 접근 방식은 **"메뉴 기반의 전문가 도구"**였다.
- **현실:** 사용자는 수많은 메뉴(`공시`, `분석`, `뉴스`) 앞에서 길을 잃는다.
- **문제:** 킬러 기능(`이벤트 스터디`)이 깊숙한 뎁스(Depth)에 숨겨져 있어 접근성이 떨어진다.
- **결과:** 높은 기능성에도 불구하고, 초기 온보딩 장벽이 너무 높다.

### 1.2 새로운 방향: "Chat as a Commander"
우리는 **"하이브리드 인터페이스(Hybrid Interface)"**로 전환한다.
- **개념:** 채팅창은 단순한 질의응답 도구가 아니라, **전체 앱을 제어하는 지휘자(Commander)**다.
- **변화:** 사용자가 메뉴를 찾아가는 것이 아니라, **대화가 기능을 호출(Call)하여 사용자 앞으로 가져온다.**
- **UX 철학:** "판단은 AI가(Routing), 검증은 UI로(Overlay)."

---

## 2. 경쟁 우위 및 차별화 (Competitive Edge)

| 비교 항목 | 전통적 강자 (S&P CapIQ, Bloomberg) | 일반 AI 챗봇 (ChatGPT, Perplexity) | **KO-FINANCE (To-Be)** |
| :--- | :--- | :--- | :--- |
| **접근성** | ❌ **최악** (교육 없이는 사용 불가) | ✅ **최상** (자연어 대화) | ✅ **최상** (자연어 + 자동 UI) |
| **데이터 깊이** | ✅ **최상** (모든 Raw Data 보유) | ❌ **낮음** (환각, 텍스트 요약 위주) | ✅ **상** (공시 원문 + 퀀트 연산) |
| **분석 기능** | ✅ **강력** (스크리너, 백테스트) | ❌ **불가** (단순 계산 오류 잦음) | ✅ **강력** (서버사이드 정밀 연산) |
| **사용자 경험** | "데이터를 찾으러 가야 함" | "글자만 읽어야 함" | **"말하면 차트와 분석 툴이 뜸"** |

### 🧬 우리의 Winning Point
> **"Bloomberg Terminal 기능을 ChatGPT처럼 쓴다."**
> 경쟁사는 UI를 뜯어고치기엔 너무 무겁고, AI 스타트업은 금융 데이터를 다루기엔 깊이가 얕다. 우리는 그 **틈새(Gap)**를 파고든다.

---

## 3. 핵심 기능 포트폴리오 (Feature Portfolio)

### 3.1 킬러 기능 (Deep Tools) - *유료화 핵심*
1.  **⚗️ 이벤트 스터디 (Event Study):** "실적발표 직후 3일간 주가 추이" 등 정량적 패턴 분석. (Overlay UI)
2.  **📑 지능형 공시 뷰어:** 단순 PDF 열람이 아닌, AI가 찾아준 해당 문단으로 하이라이트 이동. (Side Panel)
3.  **📊 퀀트 스크리너:** 자연어로 "영업이익률 20% 이상이면서 저평가된 바이오 주식 찾아줘" 실행.

### 3.2 기반 기능 (Base Essentials) - *무료/미끼*
1.  **💬 AI 마켓 브리핑:** 장 마감 후 시황 요약, 뉴스 큐레이션.
2.  **🏢 기업 개요(Snapshot):** 시세, 재무제표 요약, 주요 주주 현황.
3.  **🚨 규제/컴플라이언스 필터:** 매수/매도 추천 방지 및 출처 명시.

### 3.3 제거/숨김 대상 (Deprecation)
- **복잡한 GNB(메뉴바):** 상단/좌측의 복잡한 메뉴 트리를 제거하고, 채팅창 위주 홈 화면으로 개편. 모든 기능은 '숨겨진 도구'로 전환.

---

## 4. 수익화 전략 (Monetization Strategy)

### 4.1 타겟 세그먼트 & Pricing
1.  **Starter (무료/가입형):** 
    - 뉴스 검색, 시세 조회, 일일 5회 AI 대화.
    - *목적:* 트래픽 확보 및 리드 수집.
2.  **Pro (월 29,900원 ~ 49,900원):** 
    - **이벤트 스터디 무제한**, 심층 공시 분석, 광고 제거.
    - *타겟:* 개인 전업 투자자, 주니어 애널리스트.
3.  **Enterprise (Contact Us):** 
    - 전용 클라우드(보안), API 연동, 팀 공유 기능.
    - *타겟:* 자산운용사 리서치팀, VC/PE.

### 4.2 업셀링 매커니즘 (The "Teaser" Flow)
- 무료 유저가 "이벤트 스터디" 요청 시:
    1.  AI: "분석을 실행할 수 있습니다."
    2.  UI: **흐릿하게 처리된(Blurred) 결과 그래프**를 3초간 보여줌.
    3.  Action: "Pro 플랜에서 정확한 수치와 전체 기간을 확인하세요." (잠금 아이콘)

---

## 5. 보안 및 규제 (Compliance & Security)

### 5.1 투자자문업 리스크 회피 (The "Analyst Tool" Rule)
- **원칙:** AI는 **"판단(Decision)"**하지 않고 **"정리(Organize)"**한다.
- **Safe:** "과거 데이터를 보면 평균 3% 상승했습니다." (Fact)
- **Unsafe:** "따라서 지금 매수하는 것을 추천합니다." (Opinion -> **불법**)
- **조치:** System Prompt 및 Output Regex Filter로 '추천', '매수', '목표가' 단어 원천 차단.

### 5.2 데이터 보안
- **세션 분리:** 사용자 A의 분석 데이터가 사용자 B의 RAG 결과에 섞이지 않도록 `Tenant ID` 철저 분리.
- **감사 추적(Audit Log):** AI가 어떤 문서를 근거로 답변했는지 출처(Source Link) 강제 표시.

---

## 6. 종합 로드맵 (Execution Roadmap)

### 📅 Phase 1: 기반 구축 (0~2개월)
*   **목표:** "말 귀를 알아듣고 도구를 꺼내는" 라우터 완성.
*   **Core Task:**
    - `Semantic Router` 미들웨어 구축 (의도 분류).
    - `Overlay UI` 아키텍처 구현 (채팅 위젯화).
    - `Event Study` 엔진 최적화 (Redis 캐싱).
*   **KPI:** 의도 분류 정확도 90% 이상, 도구 로딩 시간 < 1.5초.

### 📅 Phase 2: 고도화 및 유료화 (3~6개월)
*   **목표:** 사용자 경험 개선 및 결제 모델 탑재.
*   **Core Task:**
    - `LightMem` 연동 (문맥 기억: "아까 그거랑 비교해줘").
    - **Paywall (Teaser)** 기능 적용.
    - 모바일 웹 뷰 최적화.
*   **KPI:** 무료 -> 유료 전환율(CVR) 3% 달성.

### 📅 Phase 3: 통합 인텔리전스 & 워크플로우 자동화 (6~9개월)
*   **목표:** “궁금할 때만 쓰는 도구”에서 “이거 없으면 퇴근 못 하는 플랫폼”으로 진화.
*   **핵심 미션:** 텍스트 정성 분석 + 능동 알림 + 보고서 자동화를 연결해, 질문·알림·산출물까지 하나의 흐름으로 제공.

#### 3대 축 (Text · Push · Output)
1. **🧠 Text Intelligence (Deep Search & Evidence)**
    - 기능: 지능형 공시/뉴스 Evidence Workspace, RAG 기반 “해당 문단만 발췌” 검색, 차트 급락 지점과 뉴스/공시의 인과관계 매핑.
    - 기술 과제: Vector DB(Chroma/Pinecone) 도입, PDF 파서·OCR 고도화, 증거 하이라이트/앵커 저장 구조 정비.
2. **🔔 Proactive Signals (Watchdog System)**
    - 기능: 복합 조건 알림(예: RSI+수급 변화)과 키워드 감시(“횡령/유상증자/소송” 등장 시 즉시 경보)로 Pull→Push 전환.
    - 기술 과제: 백엔드 스케줄러(Celery/Redis) 확립, Slack·Telegram·Email Webhook 파이프라인, 알림 정책 저장/서명.
3. **📄 One-Click Reporting (Last Mile)**
    - 기능: Overlay 결과를 한 번에 PDF/Excel로 내보내고 AI 코멘트·뉴스 요약을 묶어 상신용 브리핑 자동 생성.
    - 기술 과제: 서버사이드 렌더러(Puppeteer/ReportLab) 선택, 시계열 Raw Data Export(OHLCV+CAR) API, 템플릿화된 코멘터리 생성기.

#### Phase 3 실행 로드맵 (우선순위)
| 순서 | 작업명 | 목표 결과물 | 비즈니스 임팩트 |
| :--- | :--- | :--- | :--- |
| 1 | 뉴스/공시 RAG 파이프라인 | 채팅 질문 시 관련 문단 하이라이트+출처 제공 | 신뢰성 확보, 모든 워크플로우의 베이스 |
| 2 | Alert/Signal 센터 | 관심 종목 조건 충족 시 Slack/메일/텔레그램 Push | 재방문·리텐션 증대 |
| 3 | PDF/Excel Report Export | “분석 결과 다운로드” 버튼 + 자동 브리핑 | 상사 보고·엔터프라이즈 Lock-in |

> **시니어 코멘트:** Phase 3의 첫 단추는 **뉴스/공시 데이터 파이프라인**이다. Evidence Workspace/RAG, Alert, Report 모두 동일 소스를 재사용하므로, 벡터·OCR·정규화 스키마 설계에 즉시 착수한다.

---

## 7. 결론 (Summary)
우리는 더 이상 "검색 엔진"을 만들지 않는다. 우리는 금융 전문가의 **"AI 비서(Agent)"**를 만든다.
사용자가 할 일은 오직 하나, **"궁금한 것을 물어보는 것"** 뿐이다. 나머지는 시스템이 알아서 화면을 구성한다.

---

## 8. ✔️ 다음 작업 (Next Steps)

### 8.1 Legacy UI / Component Teardown
| 범주 | 영향 아티팩트 | 조치 | 메모 |
| :--- | :--- | :--- | :--- |
| **구(舊) React(MUI) 대시보드** | `web/frontend/src/App.js`, `web/frontend/src/components/NewsSignals.js` | 저장소 분리 또는 제거 | Chat Commander 철학과 맞지 않는 테이블·필터 기반 UX, API 호출 중복. |
| **GNB & Shell** | `web/dashboard/src/components/layout/{AppShell.tsx,SideNav.tsx,TopBar.tsx,UserMenu.tsx,AppFooter.tsx}` | 폐기 후 Chat 홈으로 대체 | 사이드바 라우트(`/watchlist`, `/news` 등) 전면 제거, Commander 진입점만 남김. |
| **메뉴형 페이지 묶음** | `web/dashboard/src/app/{page.tsx,watchlist,news,filings,company,search,tables,viewer,workspace}` | “숨겨진 도구” 패턴으로 전환 또는 삭제 | 각 화면의 데이터 훅(`hooks/useDashboardOverview`, `hooks/useSectorSignals` 등)도 함께 정리. |
| **Labs / Event Study 스택** | `web/dashboard/src/app/event-study`, `/labs/event-study`, `components/event-study/*`, `hooks/useEventStudy.ts` | Overlay 모듈로 이관 | Chat→Tool 호출만 허용, `/labs` 경로 제거, `EventStudyExportButton`를 Paywall-aware CTA로 묶기. |
| **결제/플랜** | `web/dashboard/src/app/{pricing,payments}`, `components/plan/*`, `web/routers/{plan.py,payments.py}` | Paywall 모듈로 재구성 | Commander가 paywall 상태를 안내하고, UI는 흐릿 처리된 그래프/CTA만 노출. |
| **Admin·Onboarding·Explorer** | `web/dashboard/src/app/{admin,alerts,digest,boards,onboarding,tables,legal}`, `components/sectors/*`, `components/table-explorer/*` | 내부툴 전환 또는 제거 | 일부는 Ops 콘솔(별도 repo)로 이동, 나머지는 슬래시 명령으로만 접근. |

- `web/dashboard/src/components/tools/ToolOverlay.tsx`와 `src/store/toolStore.ts`는 상기 정리 후 **Commander Overlay** 전용으로 재작성한다 (도구 ID/파라미터 체계 통합, paywall 상태/teaser UI까지 포함).
- 제거 대상 코드 경로는 우선 lint-ignore → feature flag → 완전 삭제 순으로 단계적 정리하여 배포 리스크 최소화한다.

### 8.2 Router Prompt & Tool Registry Rebuild
1. **Prompt 재설계 (`llm/prompts/query_intent.py`):** 기존 pass/semi/block 분류를 폐기하고, 아래 JSON 스키마를 강제한다.  
   ```jsonc
   {
     "intent": "event_study|disclosure_viewer|quant_screener|snapshot|market_briefing|compliance_block|small_talk",
     "confidence": 0.0-1.0,
     "tool_call": {
       "name": "event_study.query",
       "arguments": {
         "ticker": "005930",
         "eventType": "earnings",
         "window": {"start": -3, "end": 3}
       }
     },
     "ui_container": "overlay|side_panel|inline_card",
     "paywall": "free|starter|pro|enterprise",
     "requires_context": ["lightmem.summary","tenant.snapshot"],
     "safety": {"block": false, "reason": "..."}
   }
   ```
   - System 지침에 “판단은 AI, 검증은 UI”·금지어(매수/추천 등)를 재강조하고, paywall/teaser 분기 로직까지 포함한다.
2. **Tool Registry 모듈화:** `llm/tool_registry.py`(신규) 또는 `services/tool_registry.py`에 **단일 소스**로 아래 정보를 정의한다.  
   - `tool_id`, `llm_call_name`, `ui_container`, `paywall_tier`, `teaser_behavior`, `api_contract_ref`, `memory_slots`.  
   - Dashboard는 이 레지스트리를 읽어 `store/toolStore`와 `ToolOverlay` 구성을 동적으로 렌더한다.
3. **Router×LightMem 통합:** Phase 2에서 계획한 `LightMem`을 `requires_context` 필드와 연결하여, “아까 그거” 요청 시 자동으로 이전 turn payload를 삽입/갱신.  
   - `hooks/useChatController.ts`(Commander driver)에서 router 응답을 받아 `ToolOverlay` 호출 + LightMem 업데이트를 동시에 처리한다.
4. **gRPC/API 브릿지 검증:** `web/routers/tools.py`를 멀티 도구 entrypoint로 확장하고, `/api/v1/tools/:slug`를 Commander intent와 1:1 매핑한다. guardrail 실패 시 `compliance_block` intent로 즉시 회선 차단.

### 8.3 Chat → Tool API Contract
| Tool | Endpoint & Method | Request 본문 (핵심) | Response 핵심 필드 | UI / Paywall |
| :--- | :--- | :--- | :--- | :--- |
| **Event Study Overlay** | `POST /api/v1/tools/event-study` | `ticker`, `event_type`, `window`(start/end), `teaser`(bool) | `summary.samples`, `summary.win_rate`, `chart_data[]`, `history[]`, `teaser`(true→blur) | Overlay · **Pro** (Starter는 `teaser=true` 자동) |
| **Disclosure Viewer** | `POST /api/v1/tools/disclosure-viewer` → service: `web/routers/filing.py` | `receipt_no`, `section`(enum), `highlight_query`, `tenant_id` | `document_url`, `page`, `highlight_range`, `citations[]`, `source_links[]` | Side Panel · Starter+, inline CTA에서 Pro 심층 이동 |
| **Quant Screener** | `POST /api/v1/tools/quant-screener` (신규, `services/screener_service.py`) | `filters[]`(metric/operator/value), `universe`, `limit`, `sort` | `items[]`(ticker, name, metrics{}), `queryEcho`, `runtime_ms` | Overlay · Pro, Starter는 top 3 & blur |
| **Company Snapshot** | `GET /api/v1/company/{identifier}/snapshot` (`web/routers/company.py:132`) | Path `identifier`, opt. `metrics` query | `price`, `financials`, `holders`, `insights`, `lastUpdated`, `sources[]` | Inline Card · Free (full detail에 Pro 배지) |
| **AI Market Briefing** | `GET /api/v1/reports/daily-brief?date=YYYY-MM-DD` (`web/routers/reports.py:156`) | `date`, optional `channel` | `headline`, `summary`, `attachments.pdf_url`, `sources[]` | Inline Card/Carousel · Free, PDF 다운로드는 Starter+ |
| **Compliance Guard** | `POST /api/v1/tools/compliance/check` (신규, wraps regex guard) | `session_id`, `prompt`, `draft_output`, `tenant_id` | `allowed`(bool), `violations[]`(keyword, span), `replacement_hint` | Invisible system tool · 모든 플랜 |

#### Contract 확장 메모
- 각 응답에 `audit` 객체(`tenant_id`, `trace_id`, `source_doc_ids`, `generated_at`)를 포함해 5.2절 감사 추적 요건을 만족한다.
- Paywall 처리: `paywall` 필드와 Commander 응답을 동기화해 Overlay에서 `blurred_preview`(그래프/표 일부)와 CTA copy를 일관되게 노출.
- LightMem hookup: 도구 응답마다 `memory_write` 섹션을 추가해 “최근 비교 기준” 등 누적 맥락을 보존한다.
