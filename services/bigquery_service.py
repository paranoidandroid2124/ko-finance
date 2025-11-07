"""Utility wrapper for Google BigQuery interactions."""

from __future__ import annotations

import logging
from typing import Iterable, List, Mapping, Optional, Sequence

from core.env import env_int, env_str

try:  # pragma: no cover - optional dependency
    from google.cloud import bigquery  # type: ignore
except ImportError:  # pragma: no cover
    bigquery = None  # type: ignore

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

PROJECT_ID = env_str("BIGQUERY_PROJECT_ID", "").strip()
DEFAULT_LOCATION = env_str("BIGQUERY_LOCATION", "asia-northeast3").strip()
STREAMING_TIMEOUT = env_int("BIGQUERY_STREAM_TIMEOUT_SECONDS", 30, minimum=5)

_CLIENT: Optional["bigquery.Client"] = None  # type: ignore[name-defined]


def _client() -> Optional["bigquery.Client"]:  # type: ignore[name-defined]
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    if bigquery is None or not PROJECT_ID:
        return None
    try:
        _CLIENT = bigquery.Client(project=PROJECT_ID, location=DEFAULT_LOCATION or None)
    except Exception as exc:  # pragma: no cover - guard for missing credentials
        logger.error("Failed to initialise BigQuery client: %s", exc, exc_info=True)
        _CLIENT = None
    return _CLIENT


def is_enabled() -> bool:
    """Return True when the BigQuery client can be initialised."""

    return _client() is not None


def ensure_table(
    *,
    dataset: str,
    table: str,
    schema: Iterable["bigquery.SchemaField"],  # type: ignore[name-defined]
    partition_field: Optional[str] = None,
) -> bool:
    """Create the dataset/table when missing, returning True on success."""

    client = _client()
    if client is None or bigquery is None:
        logger.debug("BigQuery client unavailable; ensure_table skipped.")
        return False

    dataset_ref = bigquery.Dataset(f"{client.project}.{dataset}")
    try:
        client.get_dataset(dataset_ref)
    except Exception:
        try:
            dataset_ref.location = DEFAULT_LOCATION or None
            client.create_dataset(dataset_ref)
            logger.info("Created BigQuery dataset %s.", dataset_ref.full_dataset_id)
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to create dataset %s: %s", dataset, exc, exc_info=True)
            return False

    table_ref = bigquery.Table(dataset_ref.table(table), schema=schema)
    if partition_field:
        table_ref.time_partitioning = bigquery.TimePartitioning(field=partition_field)

    try:
        client.get_table(table_ref)
        return True
    except Exception:
        try:
            client.create_table(table_ref)
            logger.info("Created BigQuery table %s.%s.", dataset, table)
            return True
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to create BigQuery table %s.%s: %s", dataset, table, exc, exc_info=True)
            return False


def stream_rows(
    *,
    dataset: str,
    table: str,
    rows: Iterable[Mapping[str, object]],
) -> List[str]:
    """Stream JSON rows into BigQuery. Returns list of error messages."""

    client = _client()
    if client is None or bigquery is None:
        return ["BigQuery client unavailable"]

    table_id = f"{client.project}.{dataset}.{table}"
    rows_list = list(rows)
    if not rows_list:
        return []

    try:
        errors = client.insert_rows_json(
            table_id,
            rows_list,
            timeout=STREAMING_TIMEOUT,
        )
    except Exception as exc:  # pragma: no cover
        logger.error("BigQuery streaming insert failed: %s", exc, exc_info=True)
        return [str(exc)]

    flattened = []
    for error_entry in errors or []:
        err = error_entry.get("errors") if isinstance(error_entry, Mapping) else None
        if not err:
            continue
        for item in err:
            reason = item.get("reason")
            message = item.get("message")
            flattened.append(f"{reason}: {message}")
    if flattened:
        logger.warning("BigQuery streaming insert returned errors: %s", flattened)
    return flattened


def run_query(
    sql: str,
    *,
    parameters: Optional[Sequence["bigquery.ScalarQueryParameter"]] = None,  # type: ignore[name-defined]
) -> List[Mapping[str, object]]:
    """Execute a query and return rows as dictionaries."""

    client = _client()
    if client is None or bigquery is None:
        raise RuntimeError("BigQuery client unavailable")

    job_config = bigquery.QueryJobConfig()
    if parameters:
        job_config.query_parameters = list(parameters)

    try:
        query_job = client.query(sql, job_config=job_config)
        results = query_job.result()
    except Exception as exc:  # pragma: no cover
        logger.error("BigQuery query failed: %s", exc, exc_info=True)
        raise

    rows: List[Mapping[str, object]] = []
    for row in results:
        rows.append(dict(row))
    return rows


__all__ = ["is_enabled", "ensure_table", "stream_rows", "run_query"]
