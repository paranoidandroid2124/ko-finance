"""Helper functions for interacting with MinIO storage."""

from __future__ import annotations

import logging
import mimetypes
import os
from datetime import timedelta
from pathlib import Path
from typing import Optional, Protocol, Union, cast

try:  # pragma: no cover - optional dependency
    from minio import Minio as _RuntimeMinio
except ImportError:  # pragma: no cover
    _RuntimeMinio = None

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class MinioClientProtocol(Protocol):
    """Subset of MinIO client methods used within the project."""

    def bucket_exists(self, bucket_name: str) -> bool:
        ...

    def make_bucket(self, bucket_name: str) -> None:
        ...

    def fput_object(
        self,
        bucket_name: str,
        object_name: str,
        file_path: str,
        *,
        content_type: Optional[str] = None,
    ) -> None:
        ...

    def fget_object(
        self,
        bucket_name: str,
        object_name: str,
        file_path: str,
    ) -> None:
        ...

    def presigned_get_object(
        self,
        bucket_name: str,
        object_name: str,
        *,
        expires: timedelta,
    ) -> str:
        ...


MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "kfinance-filings")
MINIO_SECURE = os.getenv("MINIO_SECURE", "true").lower() == "true"

_client: Optional[MinioClientProtocol] = None


def _init_client() -> Optional[MinioClientProtocol]:
    if _RuntimeMinio is None:
        return None
    if not (MINIO_ENDPOINT and MINIO_ACCESS_KEY and MINIO_SECRET_KEY):
        return None
    try:
        client = cast(
            MinioClientProtocol,
            _RuntimeMinio(
                MINIO_ENDPOINT,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
                secure=MINIO_SECURE,
            ),
        )
        logger.info("MinIO client initialised for %s.", MINIO_ENDPOINT)
        return client
    except Exception as exc:  # pragma: no cover - network/socket failures are logged
        logger.error("Failed to initialise MinIO client: %s", exc, exc_info=True)
        return None


def _client_instance() -> Optional[MinioClientProtocol]:
    global _client
    if _client is None:
        _client = _init_client()
    return _client


def is_enabled() -> bool:
    return _client_instance() is not None


def _ensure_bucket() -> None:
    client = _client_instance()
    if not client:
        return
    try:
        if not client.bucket_exists(MINIO_BUCKET):
            client.make_bucket(MINIO_BUCKET)
    except Exception as exc:  # pragma: no cover - propagated as log for ops review
        logger.error("Failed to ensure MinIO bucket '%s': %s", MINIO_BUCKET, exc, exc_info=True)


def upload_file(
    local_path: str,
    object_name: Optional[str] = None,
    *,
    content_type: Optional[str] = None,
) -> Optional[str]:
    client = _client_instance()
    if not client:
        return None

    path = Path(local_path)
    if not path.is_file():
        logger.warning("Cannot upload missing file to MinIO: %s", local_path)
        return None

    _ensure_bucket()
    object_key = object_name or path.name
    detected_type = content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    try:
        client.fput_object(
            bucket_name=MINIO_BUCKET,
            object_name=object_key,
            file_path=str(path),
            content_type=detected_type,
        )
        logger.info("Uploaded %s to bucket '%s'.", object_key, MINIO_BUCKET)
        return object_key
    except Exception as exc:  # pragma: no cover
        logger.error("MinIO upload failed: %s", exc, exc_info=True)
        return None


def download_file(object_name: str, destination_path: str) -> Optional[str]:
    client = _client_instance()
    if not client:
        return None

    destination = Path(destination_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        client.fget_object(
            bucket_name=MINIO_BUCKET,
            object_name=object_name,
            file_path=str(destination),
        )
        logger.info("Downloaded %s to %s.", object_name, destination)
        return str(destination)
    except Exception as exc:  # pragma: no cover
        logger.error("MinIO download failed: %s", exc, exc_info=True)
        return None


def _normalize_expiry(value: Union[int, float, timedelta]) -> timedelta:
    if isinstance(value, timedelta):
        seconds = int(value.total_seconds())
    else:
        try:
            seconds = int(float(value))
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive guard
            raise ValueError("expiry must be seconds as number or datetime.timedelta") from exc
    bound_seconds = max(1, min(seconds, 604800))
    return timedelta(seconds=bound_seconds)


def get_presigned_url(object_name: str, expiry_seconds: Union[int, float, timedelta] = 3600) -> Optional[str]:
    client = _client_instance()
    if not client:
        return None
    try:
        expires = _normalize_expiry(expiry_seconds)
        return client.presigned_get_object(
            bucket_name=MINIO_BUCKET,
            object_name=object_name,
            expires=expires,
        )
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to create MinIO presigned URL: %s", exc, exc_info=True)
        return None


__all__ = ["is_enabled", "upload_file", "download_file", "get_presigned_url"]
