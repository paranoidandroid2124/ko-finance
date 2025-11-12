-- Migration: unify alert_rules schema (trigger/frequency/cooled_until)
-- Applies to PostgreSQL

ALTER TABLE alert_rules
    ADD COLUMN IF NOT EXISTS trigger JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS frequency JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS cooled_until TIMESTAMPTZ NULL;

-- Backfill new columns from legacy fields when present.
UPDATE alert_rules
SET
    trigger = COALESCE(condition, '{}'::jsonb),
    frequency = jsonb_build_object(
        'evaluationIntervalMinutes', COALESCE(evaluation_interval_minutes, 5),
        'windowMinutes', COALESCE(window_minutes, 60),
        'cooldownMinutes', COALESCE(cooldown_minutes, 60),
        'maxTriggersPerDay', max_triggers_per_day
    ),
    cooled_until = throttle_until
WHERE trigger = '{}'::jsonb OR frequency = '{}'::jsonb;

ALTER TABLE alert_rules
    DROP COLUMN IF EXISTS condition,
    DROP COLUMN IF EXISTS evaluation_interval_minutes,
    DROP COLUMN IF EXISTS window_minutes,
    DROP COLUMN IF EXISTS cooldown_minutes,
    DROP COLUMN IF EXISTS max_triggers_per_day,
    DROP COLUMN IF EXISTS throttle_until;

-- Ensure defaults remain explicit for future inserts.
ALTER TABLE alert_rules
    ALTER COLUMN trigger SET DEFAULT '{}'::jsonb,
    ALTER COLUMN frequency SET DEFAULT '{}'::jsonb;
