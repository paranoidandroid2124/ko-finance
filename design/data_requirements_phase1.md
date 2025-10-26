# Phase 1 Data Requirements

> Tracks backend/API changes required to support Phase 1 UI upgrades.  
> Updated: 2025-10-25

## 1. Company Snapshot Endpoint (`GET /api/v1/companies/{identifier}/snapshot`)
| Field | Status | Notes |
| --- | --- | --- |
| ~~`market_returns_1d`~~ | Removed | 시세 연동 범위에서 제외. |
| ~~`market_returns_5d`~~ | Removed | 시세 연동 범위에서 제외. |
| ~~`market_returns_20d`~~ | Removed | 시세 연동 범위에서 제외. |
| ~~`sector_return_delta`~~ | Removed | 시세 연동 범위에서 제외. |
| ~~`volatility_20d`~~ | Removed | 시세 연동 범위에서 제외. |
| `sector_code` | Partial | `useCompanySnapshot` exposes `ticker` / `corpCode` only; need taxonomy join. |

- Quality rules: return `null` if insufficient historical prices; populate `sector_code` using canonical taxonomy.

## 2. Search Aggregation Endpoint (`GET /api/v1/search`)
| Field | Status | Notes |
| --- | --- | --- |
| `results[].evidence_counts` | Missing | Search components do not exist yet; backend endpoint also absent. |
| `results[].latest_ingested_at` | Missing | Requires ingestion metadata. |
| `results[].source_reliability` | Missing | Search aggregation endpoint still TBD. |
| `results[].event_returns` | Missing | Need joined market data. |

- TODO: confirm endpoint path and authentication model.

## 3. News Window Insights (`GET /api/v1/news/windows`)
| Field | Status | Notes |
| --- | --- | --- |
| `items[].source_reliability` | Heuristic | Populated via `services.reliability.source_reliability`. |
  - Overrides can be applied via `SOURCE_RELIABILITY_OVERRIDE_PATH` or `SOURCE_RELIABILITY_OVERRIDES_JSON`.
| `items[].deduplication_cluster_id` | Missing | No dedupe metadata in current responses. |
| `items[].domain_diversity` | Present | Already mapped via `useCompanySnapshot`. |
| `items[].top_topics` | Present | Ensure casing normalization (currently lower-case). |

## 4. Derived Metrics Backfill Tasks
- (Removed) Ensure Celery task computing returns runs nightly and writes to snapshot cache.
- Add monitoring for missing market data (fallback to `null` and log warning).
- Provide fixture dataset for frontend development located at `tests/fixtures/phase1`.

## 5. Open Questions / Follow-ups
- Do we expose raw price series for sparkline (Phase 2 dependency) or keep aggregated metrics only?
- Reliability score source of truth — news fetcher vs downstream model?
- Authentication/plan gating: does search endpoint return locked actions metadata?

---
- Owner: TBD  
- Next review: align with backend team before 2025-11-06 kickoff.
