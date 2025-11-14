#!/usr/bin/env bash
set -euo pipefail

# Ensure ephemeral state files land in tmpfs paths during CI/test runs.
ROOT="${CI_STATE_ROOT:-/tmp/kofinance_state}"
PLAN_DIR="$ROOT/plan"
NEWS_DIR="$ROOT/news"

mkdir -p "$PLAN_DIR" "$NEWS_DIR"

export PLAN_SETTINGS_FILE="${PLAN_SETTINGS_FILE:-$PLAN_DIR/plan_settings.json}"
export PLAN_CONFIG_FILE="${PLAN_CONFIG_FILE:-$PLAN_DIR/plan_config.json}"
export PLAN_CATALOG_FILE="${PLAN_CATALOG_FILE:-$PLAN_DIR/plan_catalog.json}"
export NEWS_SUMMARY_CACHE_PATH="${NEWS_SUMMARY_CACHE_PATH:-$NEWS_DIR/summary_cache.json}"

touch "$PLAN_SETTINGS_FILE" "$PLAN_CONFIG_FILE" "$PLAN_CATALOG_FILE" "$NEWS_SUMMARY_CACHE_PATH"

exec "$@"
