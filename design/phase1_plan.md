# Phase 1 Plan — Skeleton UI & Data Exposure

> Timebox: 2025-11-06 → 2025-11-19 · Owner: TBD · Status: Draft

## 1. Scope & Goals
- Stand up the revamped global search hub, company snapshot shell, and news insights lists using the new information architecture.
- Surface qualitative insights (출처 신뢰도, 감성 지표, 증거 개수 등) in the UI while deferring 시세/수익률 지표.
- Establish Tailwind/Storybook scaffolding that consumes motion tokens and design system primitives.
- Out-of-scope: Evidence panel rewrite, plan lock interactions beyond badges, alert configuration flows.

## 2. Deliverables
| Deliverable | Type | Target Path | Notes |
| --- | --- | --- | --- |
| GlobalSearchBar v2 | Component | web/dashboard/src/components/search/GlobalSearchBar.tsx | Command palette shortcut, autocomplete, filter pills |
| SearchResultTabs & Card set | Component | web/dashboard/src/components/search/SearchResults.tsx | Tabbed results with 메타 태그/잠금 뱃지 |
| Company snapshot shell updates | Component | web/dashboard/src/app/company/[ticker]/page.tsx | Hero panel, metric strip, placeholder timeline slot |
| News insight cards v2 | Component | web/dashboard/src/components/company/NewsSignalCards.tsx | Display avg sentiment, domains, top topics |
| Tailwind motion tokens | Frontend infra | web/dashboard/src/styles/motion.css & Tailwind config | Map motion_fast etc. to utility classes |
| Storybook token demo | Documentation | web/dashboard/src/stories/TokenPreview.stories.tsx | Show motion tokens + color/typography pairing |
| API field audit doc | Doc | design/data_requirements_phase1.md | Confirm availability of returns, sector deltas, reliability |

## 3. Workstreams
### 3.1 Design / UX
- Finalize low-fi sketches for search hub, company hero, news cards (attach to design/ux_modernization_wireframes.md).
- Specify card iconography, KPI threshold coloring, empty/loading states.
- Dependency: confirmation of motion tokens & color usage from design system owners.

### 3.2 Frontend Implementation
- Implement search components with React Query hooks, hooking into existing chatApi or new search endpoint stub.
- Update company page layout to align with wireframe; add metric strip skeleton placeholders until data arrives.
- Integrate Tailwind motion utilities (nimate-motion-fast, etc.) and ensure prefers-reduced-motion fallback.

### 3.3 Backend / Data
- (Removed) Extend snapshot endpoint to include market returns & sector deltas.
- Add source reliability flag to news response (web/routers/news.py, services/news_service).
- Provide temporary mock data for front-end to unblock while back-end still in flight (fixtures under 	ests/fixtures/phase1).

### 3.4 QA & Docs
- Create regression test list for search, company snapshot, news components (manual + automated).
- Add Storybook accessibility checks (axe) for new components.
- Update README.md with note on new search command palette shortcut.

## 4. Data Requirements
- Company snapshot: market_returns_1d, market_returns_5d, market_returns_20d, sector_return_delta, olatility_20d.
- News insights: source_reliability_score, deduplication_cluster_id, domain_diversity (existing) flagged required.
- Search endpoint: aggregated evidence counts per resource, ingest timestamps.
- Quality gates: ensure returns default to 
ull if insufficient history; reliability score normalized 0-1.

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
| Wireframes confirmed | 2025-11-07 | Design | Planned |
| Tailwind motion tokens merged | 2025-11-08 | Frontend | Planned |
| Snapshot API returns live | 2025-11-12 | Backend | Planned |
| Search hub UI complete (Storybook + page) | 2025-11-15 | Frontend | Planned |
| QA / accessibility review | 2025-11-18 | QA | Planned |

## 8. QA Checklist
- Functional: search tabs switching, card KPI calculations, company metric strip renders, news cards handle missing data.
- Accessibility: keyboard focus order, screen reader labels on KPI chips, reduced-motion fallbacks.
- Performance: initial search results within 1.5s (cached), company page LCP < 2.5s on desktop reference.
- Analytics/logging: fire search query event with query, ilter, esultCount; log reliability score availability.

## 9. Sign-offs
- Design | Product | Engineering | Compliance

---
- Notes: integrate with Phase 0 deliverables tracker once preliminary mocks attached.
