#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MIGRATIONS_DIR="$ROOT_DIR/ops/migrations"

# Ordered list of critical migrations for the current release.
MIGRATIONS=(
  "create_entitlement_service.sql"
  "create_audit_log_table.sql"
  "create_ingest_dlq.sql"
  "add_ingest_viewer_flags.sql"
  "add_light_rbac.sql"
  "update_alert_rule_schema.sql"
)

log() {
  printf '[migrations] %s\n' "$*"
}

build_psql_command() {
  if [[ -n "${DOCKER_POSTGRES_CONTAINER:-}" ]]; then
    local user="${POSTGRES_USER:-kfinance}"
    local db="${POSTGRES_DB:-kfinance_db}"
    PSQL_CMD=(docker exec -i "$DOCKER_POSTGRES_CONTAINER" psql -U "$user" -d "$db" -v ON_ERROR_STOP=1)
    return
  fi

  if [[ -n "${DATABASE_URL:-}" ]]; then
    PSQL_CMD=(psql "$DATABASE_URL" -v ON_ERROR_STOP=1)
    return
  fi

  log "ERROR: set DATABASE_URL or DOCKER_POSTGRES_CONTAINER before running this script."
  exit 1
}

apply_migration() {
  local file="$1"
  local path="$MIGRATIONS_DIR/$file"
  if [[ ! -f "$path" ]]; then
    log "ERROR: migration file not found: $path"
    exit 1
  fi

  log "Applying $file"
  "${PSQL_CMD[@]}" -f "$path"
}

main() {
  build_psql_command
  for migration in "${MIGRATIONS[@]}"; do
    apply_migration "$migration"
  done
  log "All migrations applied successfully."
}

main "$@"
