# Phase 2 Plan — Evidence Panel & RAG Integration

> Timebox: 2025-11-20 → 2025-12-04 · Owner: TBD · Status: Draft

## 1. Scope & Goals
- Rebuild the evidence panel with paragraph highlights, PDF inline viewing, and update tracking.
- Synchronize event timeline interactions with charts and evidence state (bi-directional linking).
- Enrich RAG responses with self-check metadata, chunk anchors, and inline previews.
- Out-of-scope: Alert engine, plan upgrade billing, enterprise API export.

## 2. Deliverables
| Deliverable | Type | Target Path | Notes |
| --- | --- | --- | --- |
| EvidencePanel v2 | Component | web/dashboard/src/components/evidence/EvidencePanel.tsx | Paragraph highlights, PDF iframe, diff badges |
| TimelineSparkline | Component | web/dashboard/src/components/company/TimelineSparkline.tsx | Dual-axis sentiment + price sparkline |
| RAG response schema update | API/Schema | schemas/api/rag.py, web/routers/rag.py | Include self_check, nchor, source_reliability |
| Backend evidence enrichment | Service | services/vector_service.py, services/chat_service.py | Provide paragraph IDs, anchor context |
| Storybook interaction demos | Documentation | stories/EvidencePanel.stories.tsx | With motion tokens + reduced motion toggles |
| QA scenario matrix | Doc | design/qa_phase2_matrix.md | Mapping of edge cases (missing anchors, large PDFs) |

## 3. Workstreams
### 3.1 Design / UX
- Deliver high-fi mockups for evidence panel states (loading, populated, diff, locked exports).
- Define timeline hover/focus behaviour, chart annotations, tooltip content.
- Dependency: confirmation of PDF viewer approach (native embed vs third-party).

### 3.2 Frontend Implementation
- Build reusable highlight component leveraging IntersectionObserver for scroll sync.
- Implement timeline & chart linking (React state + d3/ECharts configuration) with debounce for performance.
- Integrate Framer Motion for panel transitions and lock tooltips.

### 3.3 Backend / Data
- Update RAG pipeline to return paragraph anchors (page_number, section, quote) and reliability scores.
- Store evidence snapshots for diffing (Postgres table versioning or MinIO object).
- Extend Celery tasks to compute market impact metrics consumed by timeline sparkline.

### 3.4 QA & Docs
- Automated tests for RAG response schema (pytest) and evidence retrieval.
- Visual regression tests via Storybook Chromatic (or alternative) for panel states.
- Update runbook with evidence troubleshooting steps (missing anchors, PDF fetch failure).

## 4. Data Requirements
- RAG response: 	urn_id, chunk_id, page_number, section, quote, self_check.score, self_check.verdict, source_reliability.
- Evidence diff store: previous snapshot hash, updated timestamp, author/process reference.
- Timeline data: sentiment_z, price_close, olume, event_type for time-series alignment.

## 5. Plan Lock Mapping
| Feature | Free | Pro | Enterprise |
| --- | --- | --- | --- |
| Evidence paragraph viewing | ✓ | ✓ | ✓ |
| Highlight annotations | ✓ | ✓ | ✓ |
| PDF inline viewer | ✕ (open in new tab) | ✓ | ✓ |
| Evidence diff comparison | ✕ | ✓ | ✓ |
| Export evidence bundle | ✕ | ✕ | ✓ |

## 6. Risks & Mitigations
- Large PDFs impacting performance → Mitigation: lazy load PDF, fallback download link.
- Anchor mismatch between RAG chunks and PDF → Mitigation: validation job comparing anchors, fallback to highlight disabled state.
- Chart performance with large datasets → Mitigation: virtualize data, cap to 365 days, implement down-sampling.

## 7. Milestones & Checkpoints
| Milestone | Expected Date | Owner | Status |
| --- | --- | --- | --- |
| High-fi evidence panel delivered | 2025-11-22 | Design | Planned |
| RAG schema changes merged | 2025-11-26 | Backend | Planned |
| Evidence panel MVP in Storybook | 2025-11-29 | Frontend | Planned |
| Timeline/chart sync complete | 2025-12-01 | Frontend | Planned |
| End-to-end QA (chat→evidence) | 2025-12-03 | QA | Planned |

## 8. QA Checklist
- Functional: highlight navigation, PDF rendering, diff view toggles, timeline selection updates evidence & chart.
- Accessibility: keyboard shortcuts for highlight navigation, descriptive aria labels, high contrast diff indicators.
- Performance: panel open animation < 320ms, RAG response size < 200KB, timeline render < 100ms for 1-year data.
- Analytics/logging: log evidence view events with nchor, erdict, plan; track diff usage.

## 9. Sign-offs
- Design | Product | Engineering | Compliance

## 10. Week 1 Foundation Outputs
- UX, schema, logging decisions are captured in `design/phase2_w1_foundation.md`.
- Mockup exports (dev-only) live in `docs/mockups/phase2/`; do not bundle with production builds.
- RAG fixtures for stories/tests reside in `fixtures/evidence/`.

---
- Notes: coordinate with legal on PDF embedding license restrictions before rollout.
