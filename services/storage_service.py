"""Unified abstraction over object-storage providers (MinIO, GCS, ...)."""

from __future__ import annotations

from datetime import timedelta
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple, Union

from core.env import env_str

from services import minio_service

try:  # pragma: no cover - optional dependency
    from services import gcs_service
except ImportError:  # pragma: no cover
    gcs_service = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_ALLOWED_PROVIDERS = {"auto", "minio", "gcs"}
_PROVIDER_SETTING = env_str("STORAGE_PROVIDER", "auto").strip().lower()
if _PROVIDER_SETTING not in _ALLOWED_PROVIDERS:
    _PROVIDER_SETTING = "auto"


def _provider_candidates() -> Tuple[Tuple[str, Optional[object]], ...]:
    """Return candidate providers in priority order based on configuration."""

    if _PROVIDER_SETTING == "minio":
        return (("minio", minio_service), ("none", None))
    if _PROVIDER_SETTING == "gcs":
        return (("gcs", gcs_service), ("none", None))
    # Auto mode prefers MinIO to retain backwards compatibility.
    return (
        ("minio", minio_service),
        ("gcs", gcs_service),
        ("none", None),
    )


@lru_cache(maxsize=1)
def _resolve_provider() -> Tuple[str, Optional[object]]:
    for name, module in _provider_candidates():
        if module is None:
            continue
        try:
            if module.is_enabled():  # type: ignore[attr-defined]
                if name != "none":
                    logger.info("Using %s storage provider.", name)
                return name, module
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning("Storage provider '%s' availability check failed: %s", name, exc, exc_info=True)
    return "none", None


def provider_name() -> str:
    return _resolve_provider()[0]


def is_enabled() -> bool:
    return _resolve_provider()[1] is not None


def upload_file(
    local_path: str,
    object_name: Optional[str] = None,
    *,
    content_type: Optional[str] = None,
) -> Optional[str]:
    provider = _resolve_provider()[1]
    if provider is None:
        return None
    return provider.upload_file(local_path, object_name=object_name, content_type=content_type)  # type: ignore[attr-defined]


def download_file(object_name: str, destination_path: str) -> Optional[str]:
    provider = _resolve_provider()[1]
    if provider is None:
        return None
    if hasattr(provider, "download_file"):
        return provider.download_file(object_name, destination_path)  # type: ignore[attr-defined]
    logger.debug("Storage provider %s does not support download_file().", provider_name())
    return None


def get_presigned_url(
    object_name: str,
    expiry_seconds: Union[int, float, timedelta] = 3600,
) -> Optional[str]:
    provider = _resolve_provider()[1]
    if provider is None or not hasattr(provider, "get_presigned_url"):
        return None
    return provider.get_presigned_url(object_name, expiry_seconds=expiry_seconds)  # type: ignore[attr-defined]


def ensure_temp_copy(object_name: str, destination_dir: Path) -> Optional[Path]:
    """Download an object into the destination directory when supported."""

    destination_dir.mkdir(parents=True, exist_ok=True)
    result = download_file(object_name, str(destination_dir / Path(object_name).name))
    return Path(result) if result else None


def delete_object(object_name: str) -> bool:
    provider = _resolve_provider()[1]
    if provider is None or not hasattr(provider, "delete_object"):
        return False
    return bool(provider.delete_object(object_name))  # type: ignore[attr-defined]


__all__ = [
    "is_enabled",
    "provider_name",
    "upload_file",
    "download_file",
    "get_presigned_url",
    "delete_object",
    "ensure_temp_copy",
]
