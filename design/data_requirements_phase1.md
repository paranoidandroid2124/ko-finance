# Phase 1 Data Requirements – Search & Snapshot

## 1. Overview
- **Scope**: Phase 1 covers the global search hub, company snapshot shell, and news insight cards.
- **Goal**: Document the data fields that must exist to power the UI and track their delivery state.
- **Status**: ✅ search aggregation fields wired (filings/news/tables/charts). ✅ placeholders documented. 🔄 QA/Storybook polishing in progress.

## 2. API Endpoints & Fields

### 2.1 `GET /api/v1/search`
| Field | Source | Notes | Status |
| --- | --- | --- | --- |
| `results[].type` | aggregation service | `filing`, `news`, `table`, `chart` | ✅ |
| `results[].evidenceCounts.filings` | Filing corpus | grouped by corp/ticker | ✅ |
| `results[].evidenceCounts.news` | NewsSignal ticker counts | requires ticker tagging | ✅ |
| `results[].evidenceCounts.tables` | CorpMetric aggregates | metric count per corp | ✅ |
| `results[].evidenceCounts.charts` | NewsWindowAggregate | article_count per window | ✅ |
| `results[].sourceReliability` | weighted ticker reliability | falls back to NewsSignal average | ✅ |
| `results[].latestIngestedAt` | filed_at / observed_at / computed_for | relative time label | ✅ |
| `totals.{type}` | aggregation service | used for tab counts & pagination | ✅ |

### 2.2 Company Snapshot (Phase 1 placeholder strategy)
| Field | Source | Notes | Status |
| --- | --- | --- | --- |
| `market_returns_{1d,5d,20d}` | De-scoped | Paid market data excluded; UI shows placeholder copy | ❌ |
| `sector_return_delta` | De-scoped | Same as above | ❌ |
| `volatility_20d` | De-scoped | Same as above | ❌ |
| `news_signals[].source_reliability` | NewsWindowAggregate | available for ticker scope | ✅ |

### 2.3 News Insight Cards
| Field | Source | Notes | Status |
| --- | --- | --- | --- |
| `avg_sentiment` | NewsWindowAggregate | ticker scope | ✅ |
| `domain_diversity` | NewsWindowAggregate | ensure pipeline keeps field | ✅ |
| `top_topics` | NewsWindowAggregate.top_topics | array of topic/count | ✅ |
| `latest_ingested_at` | NewsWindowAggregate.computed_for | freshness label | ✅ |

## 3. Data Quality Checklist
- [x] Search totals match DB counts (spot check per ticker).
- [x] Source reliability falls back gracefully when no override exists.
- [ ] KPI market return fields present *(excluded in Phase 1 – revisit if free source identified)*.
- [ ] Sector delta field populated *(excluded in Phase 1 – same condition)*.
- [x] Table metrics hide badge when no CorpMetric records.
- [x] Chart entries handle null corp_name and scope appropriately.

## 4. Dependencies & Actions
- Paid market data is out of scope for Phase 1. Re-open items once a free/open feed is confirmed.
- Maintain news ticker tagging quality → affects chart/tab counts and reliability averages.
- Monitor `/api/v1/search` P95 latency after table/chart joins; add caching if >500ms.

## 5. Revision History
- **2025-10-27**: Initial draft (feomax).
- **2025-10-27**: Updated to mark market/sector KPI as de-scoped (feomax).
