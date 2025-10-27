# Phase 1 QA Checklist – Global Search & Snapshot Shell

## 1. Scope
- `/api/v1/search` aggregated results (filing, news, table, chart)
- Next.js dashboard search experience (tab switching, pagination, error states)
- Data integrity for source reliability and evidence counts
- Regression guard for existing dashboard components (no blocking UI regressions expected)

## 2. Test Matrix

### 2.1 API-Level (`pytest tests/test_search_api.py`)
- [x] `q=keyword` returns populated totals and per-type evidence counts.
- [x] `types=filing` filter returns only filings while totals report full dataset.
- [x] Tables/charts fallback gracefully when data absent (manually adjust fixtures).

### 2.2 Manual API Smoke
| Scenario | Steps | Expected |
| --- | --- | --- |
| Keyword search | `curl http://localhost:8000/api/v1/search?q=삼성전자` | JSON with results sorted by recency; totals per type. |
| Type filter | `?types=news&offset=6` | News-only payload, `total` matching returned array length (<= limit). |
| Empty query | `?` | Recent results (filing/news/table/chart if available). |
| No data fallback | request ticker without corp metrics | Table/charts omitted; totals reflect 0. |

### 2.3 Frontend (manual / playwright WIP)
| Scenario | Steps | Expected |
| --- | --- | --- |
| New query | Input keyword → press enter | Filings tab active; skeleton → results; totals update. |
| Tab switch | Click 뉴스/표/차트 | Data fetched lazily; previous results cached; tab badge counts match totals. |
| Load more | Scroll down / click “더 보기” (when count > 6) | Additional results appended without duplicates. |
| Error state | Temporarily stop API / simulate 500 | Red banner copy displayed; prior results retained. |
| Empty state | Query with no matches | Dashed border message prompting alternate query. |

### 2.4 Data Spot Check
- Compare backend counts with DB queries for one or two tickers (ensure totals match).
- Validate source reliability fallback by removing `source_reliability` on sample news row.
- 확인: CorpMetric observed_at optional 동작 (relative time 처리).
- *Not in scope*: Market/sector return KPI는 Phase 1 제외 → 현 단계에서는 placeholder 메시지 노출만 확인.

## 3. Tooling / Scripts
- `pytest tests/test_search_api.py`
- Optional: `uvicorn web.main:app --reload` + `pnpm dev` for manual UI.
- DB spot checks via `psql` or `sqlite` (depending on environment).

## 4. Outstanding Items
- [ ] Automate frontend tests (Storybook visual regression or Playwright) for tab pagination.
- [ ] Capture performance benchmarks (P95 latency target < 500ms for search endpoint).
- [ ] Monitor error rate once deployed; add logging for empty totals.

## 5. Contacts
- Backend aggregation: feomax
- Frontend search hub: feomax
- QA coordination: TBD (Phase 1 lead)
