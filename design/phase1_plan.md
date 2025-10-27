# Phase 1 Plan — Skeleton UI & Data Exposure

> Timebox: 2025-11-06 → 2025-11-19 · Owner: TBD · Status: Complete (updated 2025-10-27)

✅ Phase 1 deliverables were implemented in the dashboard; the details below reflect final code locations and outstanding follow-ups.

## 1. Scope & Goals
- Stand up the revamped global search hub, company snapshot shell, and news insights lists using the new information architecture.
- Surface qualitative insights (출처 신뢰도, 감성 지표, 증거 개수 등) in the UI while deferring 시세/수익률 지표.
- Establish Tailwind/Storybook scaffolding that consumes motion tokens and design system primitives.
- Out-of-scope: Evidence panel rewrite, plan lock interactions beyond badges, alert configuration flows.

## 2. Deliverables
| Deliverable | Type | Target Path | Status | Notes |
| --- | --- | --- | --- | --- |
| GlobalSearchBar v2 | Component | web/dashboard/src/components/search/GlobalSearchBar.tsx | ✅ Shipped | Command palette shortcut, autocomplete, filter pills |
| SearchResultTabs & Card set | Component | web/dashboard/src/components/search/SearchResults.tsx | ✅ Shipped | Tabbed results with 메타 태그/잠금 뱃지 |
| Company snapshot shell updates | Component | web/dashboard/src/app/company/[ticker]/page.tsx | ✅ Shipped | Hero panel, metric strip, placeholder timeline slot |
| News insight cards v2 | Component | web/dashboard/src/components/company/NewsSignalCards.tsx | ✅ Shipped | 평균 감성, 도메인 다양성, 토픽 칩 노출 |
| Tailwind motion tokens | Frontend infra | web/dashboard/src/styles/motion.css & Tailwind config | ✅ Shipped | Motion utilities consumed by search/snapshot components |
| Storybook token demo | Documentation | web/dashboard/src/stories/TokenPreview.stories.tsx | ✅ Shipped | Motion tokens + 색상/타이포 미리보기 |
| API field audit doc | Doc | design/data_requirements_phase1.md | ✅ Shipped | Delivered vs. deferred KPI/신뢰도 항목 기록 |

## 3. Workstreams
### 3.1 Design / UX (완료)
- Low-fi 스케치 기반 레이아웃을 `design/ux_modernization_wireframes.md`에 반영했으며 추가 하이파이 작업은 Phase 2에서 이어집니다.
- 카드 아이콘, KPI 임계값, 로딩/빈 상태 카피를 확정했습니다.
- 모션 토큰·팔레트 적용이 디자인 시스템과 정합성 검토를 통과했습니다.

### 3.2 Frontend Implementation (완료)
- React Query 기반 검색 컴포넌트와 커맨드 팔레트 단축키를 구현했습니다.
- 회사 스냅샷 페이지는 지표/이벤트/뉴스 레이아웃을 지원하며 플레이스홀더 스켈레톤을 포함합니다.
- Tailwind 모션 유틸리티 및 prefers-reduced-motion 대응을 주요 컴포넌트에 적용했습니다.

### 3.3 Backend / Data (완료 · 일부 보류)
- 뉴스 응답에 출처 신뢰도를 포함하고, 프론트엔드 차단용 목 데이터를 유지합니다.
- 시장/섹터 수익률 KPI는 범위 밖으로 결정되어 Phase 2 이후 재검토합니다.

### 3.4 QA & Docs (완료)
- 검색/스냅샷 관련 회귀 테스트를 `web/dashboard/tests`에 추가했습니다.
- Storybook 스토리에 접근성 토글(모션 토큰 프리뷰 등)을 구성했습니다.
- README 및 온보딩 노트에 커맨드 팔레트 단축키를 명시했습니다.

## 4. Data Requirements
- Company snapshot: market_returns_1d, market_returns_5d, market_returns_20d, sector_return_delta, volatility_20d (deferred; UI shows placeholders).
- News insights: source_reliability_score, deduplication_cluster_id, domain_diversity (delivered).
- Search endpoint: aggregated evidence counts per resource, ingest timestamps (delivered).
- Quality gates: ensure returns default to null if insufficient history; reliability score normalized 0-1.

## 5. Plan Lock Mapping
| Feature | Free | Pro | Enterprise |
| --- | --- | --- | --- |
| Result card KPI row | ✓ | ✓ | ✓ |
| "Add to Compare" action | ✕ (locked badge) | ✓ | ✓ |
| "Set Alert" action | ✕ | ✓ | ✓ |
| Export button | ✕ | ✕ (teaser) | ✓ |
| Command palette shortcuts | ✓ | ✓ | ✓ |

## 6. Risks & Mitigations
- Missing market return data in snapshot → Mitigation: fallback placeholder copy + backlog ticket for data service.
- Search API latency → Mitigation: cache recent queries, implement optimistic loading skeletons.
- Accessibility regressions with new motion utilities → Mitigation: run prefers-reduced-motion audit & axe checks early.

## 7. Milestones & Checkpoints
| Milestone | Expected Date | Owner | Status |
| --- | --- | --- | --- |
| Wireframes confirmed | 2025-11-07 | Design | ✅ Completed |
| Tailwind motion tokens merged | 2025-11-08 | Frontend | ✅ Completed |
| Snapshot API returns live | 2025-11-12 | Backend | ⚠️ Deferred (market/sector KPI excluded) |
| Search hub UI complete (Storybook + page) | 2025-11-15 | Frontend | ✅ Completed |
| QA / accessibility review | 2025-11-18 | QA | ✅ Completed |

## 8. QA Checklist
- [x] Functional: search 탭 전환, KPI 계산, 회사 지표 스트립, 뉴스 카드 빈/로딩 상태.
- [x] Accessibility: 키보드 포커스 순서, KPI 칩 스크린리더 레이블, 모션 축소 대응.
- [x] Performance: 초기 검색 결과 ≤1.5초(캐시 기준), 회사 페이지 LCP < 2.5초.
- [x] Analytics/logging: 검색 쿼리/필터/결과 수 로깅, 출처 신뢰도 수집.

## 9. Sign-offs
- Design | Product | Engineering | Compliance

---
- Notes: keep Phase 0 tracker aligned for remaining hi-fi sketches and deferred KPI data work.
