# File-Based State Migration Plan

Many legacy features still persist their state as JSON files inside the `uploads/` tree (e.g., plan settings, plan catalog cache, news summary cache). This document captures the path for moving those artifacts to durable storage without breaking existing workflows.

## Current Situation

| Component                    | File Path (default)                 | Consumers                                   | Risks                                               |
|-----------------------------|-------------------------------------|---------------------------------------------|-----------------------------------------------------|
| Plan settings / overrides   | `uploads/admin/plan_settings.json`  | `/api/v1/plan/*`, dashboard plan UI         | git dirty on tests, race conditions, hard to audit  |
| Plan catalog cache          | `uploads/admin/plan_catalog.json`   | catalog API, dashboard plan cards           | stale cache between instances, manual sync required |
| Plan config (presets)       | `uploads/admin/plan_config.json`    | admin plan tools                            | same as above                                       |
| News summary cache          | `uploads/news/summary_cache.json`   | `/api/v1/news/*`, dashboards                | concurrent writes can corrupt cache                 |
| Onboarding state/flags      | `uploads/admin/onboarding/*.json`   | onboarding API + dashboard                  | no locking, no auditing                             |

## Goals

1. **Eliminate git pollution**: CI and local tests should never modify tracked files.
2. **Centralize state**: production instances must read/write from PostgreSQL (or Cloud Storage) instead of app-local disks.
3. **Auditability**: every change should carry timestamps, actor metadata, and be queryable.

## Phased Migration

### Phase 1 – Temporary Mitigations (Done / In Progress)

- Redirect file paths to tmpfs during CI and pytest via `scripts/ci_tmp_env.sh`.
- Guard every file write with `filelock` to avoid corruption.
- Surface env vars (`PLAN_SETTINGS_FILE`, `PLAN_CATALOG_FILE`, etc.) in `.env.example` so developers can opt into tmp paths locally.

### Phase 2 – Dual Write / Read-Through Cache

1. **Define relational tables**:
   - `plan_settings_versions` (id, payload JSONB, updated_by, updated_at, checksum).
   - `plan_catalog_snapshots`, `plan_config_presets`.
   - `news_summary_cache` as a keyed table (signal_id, summary, source, generated_at).
   - `onboarding_progress` (user_id, checklist state, timestamps).
2. **Instrument services** so they read from DB first; optionally fall back to the file while we backfill data.
3. **Backfill** by loading the latest JSON into the new tables (one-off script under `scripts/migrations/`).
4. **Dual write** for a short period: persist to both DB + JSON until confidence is built.

### Phase 3 – Cutover & Clean-up

1. Flip feature flags to make DB the single source of truth.
2. Remove file persistence code and delete `uploads/admin/*.json` from runtime images.
3. Add migrations/tests that ensure records exist before APIs boot (fail fast if missing).
4. Update runbooks to reflect the new operational model.

## Open Questions

- **Storage choice for news summaries**: PostgreSQL is sufficient short term; consider Redis/KeyDB if latency becomes a problem.
- **Version retention**: Define pruning policy (e.g., keep last N plan settings, soft-delete older ones).
- **Access tooling**: Provide an admin UI or SQL view to inspect current plan/onboarding state once it lives in the DB.

## Next Steps

1. Finalize schemas and create Alembic migrations.
2. Implement read/write repositories for each state domain.
3. Schedule backfill + dual-write rollout (coordinate with ops to snapshot existing files).
4. Update CI to fail if any legacy file write happens (watch for changes under `uploads/admin` after tests).

Track progress in the engineering board under “State Storage Migration” epic.
