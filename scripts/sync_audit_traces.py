"""CLI entrypoint for syncing audit & reindex logs to BigQuery / GCS."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.env_utils import load_dotenv_if_available, require_env_vars  # noqa: E402

load_dotenv_if_available()
require_env_vars(
    [
        "BIGQUERY_PROJECT_ID",
        "GCS_BUCKET_NAME",
    ],
    context="sync_audit_traces",
)

from services import log_sync_service  # noqa: E402  (after sys.path tweak)


def _print_result(label: str, payload: Dict[str, Any]) -> None:
    summary = json.dumps(payload, ensure_ascii=False)
    print(f"{label}: {summary}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync audit logs and reindex traces to BigQuery/GCS.")
    parser.add_argument("--skip-archive", action="store_true", help="Skip uploading archives to object storage.")
    parser.add_argument("--skip-bigquery", action="store_true", help="Skip streaming rows into BigQuery.")
    args = parser.parse_args()

    archive = not args.skip_archive
    stream = not args.skip_bigquery

    audit_result = log_sync_service.sync_audit_logs(archive=archive, stream=stream)
    _print_result("audit", audit_result)

    reindex_result = log_sync_service.sync_reindex_logs(archive=archive, stream=stream)
    _print_result("reindex", reindex_result)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:  # pragma: no cover - CLI convenience
        sys.exit(1)
