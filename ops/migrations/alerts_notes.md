# 2025-12-05 Alerts Schema Rollout Notes

- **Migration file**: `ops/migrations/20251205_create_alert_tables.sql`
- **Scope**: Introduces `alert_rules` / `alert_deliveries` tables and supporting enums `alert_status`, `alert_delivery_status`.

## 1. Pre-check
- Confirm database snapshot (`pg_dump` or managed snapshot) exists.
- Pause Celery workers and API traffic touching `/api/v1/alerts`.
- Ensure `.env` carries the new channel secrets (see `services/notification_service.py`).

## 2. Apply
```bash
psql "$DATABASE_URL" -f ops/migrations/20251205_create_alert_tables.sql
```

## 3. Verify
```sql
\d alert_rules
\d alert_deliveries
SELECT COUNT(*) FROM alert_rules;
SELECT enumlabel FROM pg_enum WHERE enumtypid = 'alert_status'::regtype;
```

## 4. Backfill / Seed
- Existing 텔레그램 알림이 있다면 `alert_rules`에 수동 INSERT 후 `channels` 필드를 `["telegram"]`으로 구성.
- 일일 발송 제한은 플랜별 default가 자동 적용되므로 NULL이면 서버에서 Plan 설정대로 대체됨.

## 5. Rollback
```sql
DROP TABLE IF EXISTS alert_deliveries;
DROP TABLE IF EXISTS alert_rules;
DROP TYPE IF EXISTS alert_delivery_status;
DROP TYPE IF EXISTS alert_status;
```
> Rollback 후 Celery beat에서 `alerts.evaluate_rules` 스케줄 비활성화 필요.

## 6. Post-deploy
- Celery 워커/beat 재가동, `alerts.evaluate_rules` 스케줄이 1분 주기로 실행되는지 로그 확인.
- Health query: `SELECT status, COUNT(*) FROM alert_deliveries GROUP BY 1;`
- Update `.env` on staging/production with:
  - `ALERT_EMAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`
  - `ALERT_SLACK_WEBHOOK_URL`
  - `PAGERDUTY_ROUTING_KEY`
  - `ALERT_REQUEST_TIMEOUT`, `ALERT_REQUEST_RETRIES` (optional tuning)

---

## 2025-11-12 Schema Unification (trigger/frequency/cooled_until)

- **Migration file**: `ops/migrations/update_alert_rule_schema.sql`
- **Scope**: Replaces legacy `condition`/interval columns with unified `trigger` JSON, `frequency` JSON, and `cooled_until` timestamp.

### Highlights
- New API contract uses `trigger` + `frequency` blocks while keeping `condition`/interval fields for backwards compatibility.
- Feature flags:
  - `ALERTS_ENABLE_MODEL` – toggles advanced Alert Center responses/audit logging.
  - `ALERTS_ENFORCE_RL` – enables EntitlementService-backed quota consumption.
- Global write rate-limit via Redis: configure `ALERTS_WRITE_RATE_LIMIT`, `ALERTS_WRITE_RATE_WINDOW_SECONDS`, and `ALERTS_RATE_LIMIT_REDIS_URL`.
- Audit log events emitted for create/update/delete and cooldown-blocked evaluations (`alerts.*` actions).

### Rollout checklist
1. Apply migration:
   ```bash
   psql "$DATABASE_URL" -f ops/migrations/update_alert_rule_schema.sql
   ```
2. Ensure web/API pods pick up new env vars & restart worker/beat.
3. Verify `/api/v1/alerts` responses include `trigger`, `frequency`, `cooledUntil`.
4. Monitor audit log table for `alerts.create/update/delete/cooldown_blocked` entries.

---

## 2025-11-14 Rule Compiler & Worker Snapshotting

- **Code**: `alerts/rule_compiler.py`, `services/alert_service.py`, `services/alert_metrics.py`.
- **DSL**: Alert triggers may now include `dsl` strings (e.g., `news ticker:005930 keyword:'buyback' window:24h`). Compiler normalizes keywords/entities/tickers/window/min sentiment into execution plans.
- **Worker state**: `alerts.evaluate_rules` persists `extras.alertWorkerState` (plan hash, event digest, window range, duplicate flag). Duplicate payloads are skipped before dispatch.
- **Metrics**:
  - `alert_rule_eval_latency` (Histogram, labels: `plan_tier`, `result`, captures seconds per evaluation — target p95 < 1s).
  - `alert_rule_duplicate_total` (Counter, labels: `plan_tier`, `cause`, measures blocked duplicates).
- **Operational checklist**:
  1. Restart Celery worker/beat after deploy to register the metrics collectors.
  2. Update Grafana dashboard to chart `histogram_quantile(0.95, sum(rate(alert_rule_eval_latency_bucket[5m])) by (le))`.
  3. Alert on duplicate ratio: `increase(alert_rule_duplicate_total[30m]) / increase(alert_rule_eval_latency_count[30m]) > 0.03`.
  4. Optional backfill to tag existing rules: `UPDATE alert_rules SET extras = jsonb_set(COALESCE(extras, '{}'), '{alertWorkerState}', '{"version":1}'::jsonb, true) WHERE NOT (extras ? 'alertWorkerState');`
