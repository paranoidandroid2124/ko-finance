# Ingest Reliability Runbook (DART Pipelines)

## 1. Viewer Fallback Legal Guard

- Primary flow downloads OpenDART ZIP bundles; failure paths trigger the viewer scraper **only** when the per-issuer feature flag allows it.
- Feature flags live in `ingest_viewer_flags` (see `ops/migrations/add_ingest_viewer_flags.sql`):
  - `fallback_enabled = true` (default) permits viewer scraping.
  - `reason`/`updated_by` capture audit context (e.g., `"Legal hold for AAA Corp"`).
- Toggle example:
  ```sql
  INSERT INTO ingest_viewer_flags (corp_code, fallback_enabled, reason, updated_by)
  VALUES ('00123456', false, 'Robots hold (LG legal case)', 'ops@ko-finance')
  ON CONFLICT (corp_code)
  DO UPDATE SET fallback_enabled = EXCLUDED.fallback_enabled,
                reason = EXCLUDED.reason,
                updated_by = EXCLUDED.updated_by,
                updated_at = NOW();
  ```
- Every fallback attempt records `audit_logs.action = 'ingest.viewer_fallback'` with:
  - `extra.viewer_url`, `robots_allowed`, `robots_checked_at`, `tos_version`.
  - `extra.blocked = true` when the issuer feature flag disables fallback.
  - `feature_flags.viewer_fallback` mirrors the flag state for later filtering.

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
