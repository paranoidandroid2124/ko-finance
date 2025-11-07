"""Helper functions for interacting with Google Cloud Storage."""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path
from typing import Optional, Union

from core.env import env_int, env_str

try:  # pragma: no cover - optional dependency
    from google.cloud import storage as gcs_storage
except ImportError:  # pragma: no cover - library may be unavailable
    gcs_storage = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

GCS_BUCKET = env_str("GCS_BUCKET_NAME", "").strip()
SIGNED_URL_TTL_SECONDS = env_int("GCS_SIGNED_URL_TTL_SECONDS", 3600, minimum=60)

_CLIENT: Optional["gcs_storage.Client"] = None  # type: ignore[name-defined]
_BUCKET: Optional["gcs_storage.Bucket"] = None  # type: ignore[name-defined]


def _client_instance() -> Optional["gcs_storage.Client"]:  # type: ignore[name-defined]
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    if gcs_storage is None or not GCS_BUCKET:
        return None
    try:
        _CLIENT = gcs_storage.Client()
    except Exception as exc:  # pragma: no cover - runtime guard
        logger.error("Failed to initialise GCS client: %s", exc, exc_info=True)
        _CLIENT = None
    return _CLIENT


def _bucket_instance() -> Optional["gcs_storage.Bucket"]:  # type: ignore[name-defined]
    global _BUCKET
    if _BUCKET is not None:
        return _BUCKET
    client = _client_instance()
    if client is None:
        return None
    if not GCS_BUCKET:
        return None
    try:
        bucket = client.bucket(GCS_BUCKET)
        _BUCKET = bucket
        return bucket
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to access GCS bucket '%s': %s", GCS_BUCKET, exc, exc_info=True)
        return None


def is_enabled() -> bool:
    """Return True when GCS bucket configuration is available."""

    return _bucket_instance() is not None


def upload_file(
    local_path: str,
    object_name: Optional[str] = None,
    *,
    content_type: Optional[str] = None,
) -> Optional[str]:
    """Upload a file to the configured GCS bucket."""

    bucket = _bucket_instance()
    if bucket is None:
        return None

    path = Path(local_path)
    if not path.is_file():
        logger.warning("Cannot upload missing file to GCS: %s", local_path)
        return None

    object_key = object_name or path.name
    blob = bucket.blob(object_key)

    try:
        blob.upload_from_filename(str(path), content_type=content_type)
        logger.info("Uploaded %s to GCS bucket '%s'.", object_key, GCS_BUCKET)
        return object_key
    except Exception as exc:  # pragma: no cover
        logger.error("GCS upload failed: %s", exc, exc_info=True)
        return None


def download_file(object_name: str, destination_path: str) -> Optional[str]:
    """Download an object from GCS into the provided destination."""

    bucket = _bucket_instance()
    if bucket is None:
        return None

    destination = Path(destination_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        blob = bucket.blob(object_name)
        blob.download_to_filename(str(destination))
        logger.info("Downloaded %s from GCS bucket '%s' to %s.", object_name, GCS_BUCKET, destination)
        return str(destination)
    except Exception as exc:  # pragma: no cover
        logger.error("GCS download failed: %s", exc, exc_info=True)
        return None


def _normalize_expiry(value: Union[int, float, timedelta, None]) -> timedelta:
    if isinstance(value, timedelta):
        return value
    if isinstance(value, (int, float)):
        return timedelta(seconds=float(value))
    return timedelta(seconds=SIGNED_URL_TTL_SECONDS)


def get_presigned_url(
    object_name: str,
    expiry_seconds: Union[int, float, timedelta] = SIGNED_URL_TTL_SECONDS,
) -> Optional[str]:
    """Generate a time-limited signed URL for the specified object."""

    bucket = _bucket_instance()
    if bucket is None:
        return None
    try:
        blob = bucket.blob(object_name)
        expires = _normalize_expiry(expiry_seconds)
        return blob.generate_signed_url(expiration=expires)
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to create GCS signed URL: %s", exc, exc_info=True)
        return None


def delete_object(object_name: str) -> bool:
    bucket = _bucket_instance()
    if bucket is None:
        return False
    try:
        blob = bucket.blob(object_name)
        blob.delete()
        logger.info("Deleted %s from GCS bucket '%s'.", object_name, GCS_BUCKET)
        return True
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to delete GCS object %s: %s", object_name, exc, exc_info=True)
        return False


__all__ = ["is_enabled", "upload_file", "download_file", "get_presigned_url", "delete_object"]
