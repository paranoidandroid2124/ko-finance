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
  - `ALERT_EMAIL_FROM`, `SENDGRID_API_KEY`
  - `ALERT_SLACK_WEBHOOK_URL`
  - `PAGERDUTY_ROUTING_KEY`
  - `ALERT_REQUEST_TIMEOUT`, `ALERT_REQUEST_RETRIES` (optional tuning)

