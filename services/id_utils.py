"""Shared helpers for coercing UUID inputs used across web/services layers."""

from __future__ import annotations

import uuid
from typing import Any, Optional, Tuple


def normalize_uuid(value: Any) -> Optional[uuid.UUID]:
    """Convert ``value`` into a UUID if possible."""
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def resolve_subject(user_id: Any, org_id: Any) -> Optional[Tuple[uuid.UUID, uuid.UUID]]:
    """
    Determine the (user_id, org_id) pair for entitlement accounting.

    When only one identifier is provided we scope usage to the same UUID for both
    dimensions to ensure per-tenant accounting remains deterministic.
    """

    normalized_user = normalize_uuid(user_id)
    normalized_org = normalize_uuid(org_id)

    if normalized_user is None and normalized_org is None:
        return None
    if normalized_user is None:
        normalized_user = normalized_org
    if normalized_org is None:
        normalized_org = normalized_user
    if normalized_user is None or normalized_org is None:
        return None
    return normalized_user, normalized_org


__all__ = ["normalize_uuid", "resolve_subject"]
