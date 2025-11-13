# Ingest Reliability Runbook (DART Pipelines)

## 1. Viewer Fallback Legal Guard

- Primary flow downloads OpenDART ZIP bundles; failure paths trigger the viewer scraper **only** when the per-issuer feature flag allows it.
- Global toggles live in `.env`:
  - `INGEST_VIEWER_FALLBACK=true|false` enables/disables the viewer fallback globally.
  - `LEGAL_LOG=true|false` gates whether legal metadata is persisted to `audit_logs`.
  - `DART_ROBOTS_TTL_SECONDS` (default `3600`) controls the robots metadata cache/window.
- Issuer-specific overrides are stored in `ingest_viewer_flags` and should be managed via the CLI:
  ```bash
  python scripts/ingest_viewer_flags.py list
  python scripts/ingest_viewer_flags.py disable 00123456 --reason "Robots hold (LG legal case)" --updated-by ops@ko-finance
  python scripts/ingest_viewer_flags.py enable 00123456 --updated-by ops@ko-finance
  python scripts/ingest_viewer_flags.py clear-cache  # force-refresh cached flags
  ```
  The CLI wraps the same table used by migrations and automatically invalidates the in-process cache (`viewer_fallback_state`).
- Robots.txt and ToS evaluations are cached per viewer path for the TTL above; use `LEGAL_LOG=false` or reduce `DART_ROBOTS_TTL_SECONDS` if you need to suppress or tighten the logging window temporarily.
- Every fallback attempt records `audit_logs.action = 'ingest.viewer_fallback'` with extended metadata:
  - `extra` now includes `issuer`, `viewer_path`, `robots_checked`, `robots_checked_at`, `tos_checked`, `tos_version`, and `feature_flags_snapshot`.
  - `extra.blocked = true` plus `extra.block_reason` when the issuer flag or global toggle denies fallback.
  - `feature_flags.viewer_fallback`, `feature_flags.viewer_fallback_env`, and `feature_flags.viewer_fallback_flag` capture the decision state.
  - Failures record `action='ingest.viewer_fallback_failed'` with the same metadata + `extra.error`.

## 2. Celery Retry + Dead-letter Queue

- `m1.seed_recent_filings` and `m1.process_filing` now use exponential backoff (default 30s base, capped at 10m) with `INGEST_TASK_MAX_RETRIES` (default 4). Override via environment variables:
  - `INGEST_TASK_MAX_RETRIES`
  - `INGEST_TASK_RETRY_BASE_SECONDS`
  - `INGEST_TASK_RETRY_MAX_SECONDS`
- When `m1.process_filing` exhausts retries:
  1. A row is inserted into `ingest_dead_letters` (`ops/migrations/create_ingest_dlq.sql`).
  2. Gauge metric `ingest_dlq_entries{status="pending"}` updates.
  3. `audit_logs` receives `action='ingest.dlq'` with task name, retries, corp_code/ticker, and the DLQ row id.
- Use the DLQ table to requeue manually:
  ```sql
  UPDATE ingest_dead_letters
  SET status = 'requeued', next_run_at = NOW()
  WHERE id = '<uuid>';
  ```
  Then enqueue a manual Celery task referencing the stored payload (e.g., `m1.process_filing.delay(letter.payload->>'filing_id')`).

## 3. Backfill Command (Idempotent)

- Script: `python scripts/ingest_backfill.py --start-date 2024-10-01 --end-date 2024-10-07 --chunk-days 2`
  - Respects `seed_recent_filings` idempotent inserts (Postgres `ON CONFLICT DO NOTHING`).
  - Optional `--corp-code` narrows scope to a single issuer.
  - Emits Prometheus metric `ingest_backfill_duration_seconds`.

## 4. Observability

- Dashboard definition: `configs/grafana/ingest_reliability_dashboard.json`
  - Panels:
    1. Seed success rate (`ingest_pipeline_result_total`).
    2. Time since last error (`time() - ingest_pipeline_last_error_timestamp`).
    3. Error rate by source (`ingest_pipeline_errors_total`).
    4. Top exceptions (table view).
    5. `m1.process_filing` p95 latency (`histogram_quantile` on `ingest_pipeline_latency_seconds_bucket`).
    6. DLQ pending gauge (`ingest_dlq_entries`).
- Metrics emitted from code:
  - `ingest_pipeline_result_total{stage, result}`
  - `ingest_pipeline_errors_total{stage, source, exception}`
  - `ingest_pipeline_latency_seconds_bucket{stage}`
  - `ingest_pipeline_last_success_timestamp{stage}`
  - `ingest_pipeline_last_error_timestamp{stage}`
  - `ingest_pipeline_retries_total{task}`
  - `ingest_dlq_entries{status}`
  - `ingest_backfill_duration_seconds`

## 5. Smoke Checklist

1. **Fallback flag test**  
   - Insert a temporary `ingest_viewer_flags` row disabling fallback for a test corp_code.  
   - Trigger `m1.seed_recent_filings` for that issuer and confirm `audit_logs.extra.blocked = true`.
2. **DLQ path**  
   - Force `m1.process_filing` failure (e.g., corrupt file) until retries exceed `INGEST_TASK_MAX_RETRIES`.  
   - Verify `ingest_dead_letters` row + Grafana DLQ panel increments + `audit_logs` entry.
3. **Backfill**  
   - Run the CLI over a 1-day window; confirm metrics via `ingest_backfill_duration_seconds` and zero duplicate inserts (`SELECT COUNT(*) FROM filings WHERE filed_at::date = ...`).

Keep this document close to the on-call playbook; it complements the ingestion alerts surfaced in Grafana/Telegram.
