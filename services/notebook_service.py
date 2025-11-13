"""Persistence helpers for the Research Notebook API."""

from __future__ import annotations

import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from core.env import env_int

logger = logging.getLogger(__name__)

MAX_NOTEBOOK_TITLE = 160
MAX_NOTEBOOK_SUMMARY = 400
MAX_HIGHLIGHT_LENGTH = 4000
MAX_ANNOTATION_LENGTH = 8000
MAX_TAGS = 16
MAX_SHARE_HINT = 160
MAX_ACTIVE_SHARES = 20
DEFAULT_LIST_LIMIT = 25
MAX_LIST_LIMIT = 100
MIN_SHARE_TTL_MINUTES = 10
MAX_SHARE_TTL_MINUTES = 60 * 24 * 30  # 30 days
DEFAULT_SHARE_TTL_MINUTES = 60 * 24 * 7  # 7 days
ALLOWED_SOURCE_KEYS = {
    "type",
    "label",
    "url",
    "deeplink",
    "snippet",
    "documentId",
    "chunkId",
    "page",
    "paragraph",
}

_PASSWORD_HASHER = PasswordHasher(
    time_cost=env_int("NOTEBOOK_SHARE_ARGON_TIME_COST", 2, minimum=1),
    memory_cost=env_int("NOTEBOOK_SHARE_ARGON_MEMORY_COST", 65536, minimum=8192),
    parallelism=env_int("NOTEBOOK_SHARE_ARGON_PARALLELISM", 1, minimum=1),
    hash_len=32,
    salt_len=16,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _trim(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _sanitize_color(value: Optional[str]) -> Optional[str]:
    text_value = _trim(value)
    if not text_value:
        return None
    lowered = text_value.lower()
    if lowered.startswith("#") and len(lowered) in (4, 7):
        hex_digits = lowered[1:]
        if all(ch in "0123456789abcdef" for ch in hex_digits):
            return lowered
        return None
    return None


def _safe_metadata(value: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    sanitized: Dict[str, Any] = {}
    for key, raw in value.items():
        if not isinstance(key, str):
            continue
        if isinstance(raw, (str, int, float, bool)) or raw is None:
            sanitized[key] = raw
        elif isinstance(raw, Mapping):
            sanitized[key] = dict(raw)
        elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
            sanitized[key] = list(raw)
    return sanitized


def _sanitize_source(value: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    sanitized: Dict[str, Any] = {}
    for key in ALLOWED_SOURCE_KEYS:
        raw = value.get(key)
        if raw is None:
            continue
        if isinstance(raw, str):
            trimmed = raw.strip()
            if trimmed:
                sanitized[key] = trimmed
        else:
            sanitized[key] = raw
    metadata = value.get("metadata")
    if isinstance(metadata, Mapping):
        sanitized["metadata"] = _safe_metadata(metadata)
    return sanitized


def _normalize_tags(values: Optional[Iterable[str]]) -> List[str]:
    normalized: List[str] = []
    if not values:
        return normalized
    for raw in values:
        if not isinstance(raw, str):
            continue
        token = raw.strip().lower()
        if not token:
            continue
        if token not in normalized and len(normalized) < MAX_TAGS:
            normalized.append(token)
    return normalized


def _clamp_limit(limit: Optional[int]) -> int:
    if not isinstance(limit, int):
        return DEFAULT_LIST_LIMIT
    return max(1, min(limit, MAX_LIST_LIMIT))


def _serialize_tags(value: Optional[Sequence[str]]) -> List[str]:
    if not value:
        return []
    return [token for token in value if isinstance(token, str)]


@dataclass(frozen=True)
class NotebookRecord:
    id: uuid.UUID
    org_id: uuid.UUID
    owner_id: uuid.UUID
    title: str
    summary: Optional[str]
    tags: List[str]
    cover_color: Optional[str]
    metadata: Mapping[str, Any]
    entry_count: int
    last_activity_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class NotebookEntryRecord:
    id: uuid.UUID
    notebook_id: uuid.UUID
    author_id: uuid.UUID
    highlight: str
    annotation: Optional[str]
    annotation_format: str
    tags: List[str]
    source: Mapping[str, Any]
    is_pinned: bool
    position: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class NotebookShareRecord:
    id: uuid.UUID
    notebook_id: uuid.UUID
    token: str
    created_by: uuid.UUID
    expires_at: Optional[datetime]
    password_protected: bool
    password_hint: Optional[str]
    access_scope: str
    revoked_at: Optional[datetime]
    last_accessed_at: Optional[datetime]
    created_at: datetime


class NotebookServiceError(RuntimeError):
    """Raised when notebook persistence fails."""


class NotebookNotFoundError(NotebookServiceError):
    """Raised when a notebook cannot be found within the org."""


class NotebookShareError(NotebookServiceError):
    """Raised when share link operations fail."""


class NotebookShareAccessError(NotebookServiceError):
    """Raised when share consumers fail authentication or expiry."""


def _row_to_notebook(row: Mapping[str, Any]) -> NotebookRecord:
    return NotebookRecord(
        id=row["id"],
        org_id=row["org_id"],
        owner_id=row["owner_id"],
        title=row["title"],
        summary=row.get("summary"),
        tags=_serialize_tags(row.get("tags")),
        cover_color=row.get("cover_color"),
        metadata=row.get("metadata") or {},
        entry_count=int(row.get("entry_count") or 0),
        last_activity_at=row.get("last_activity_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_entry(row: Mapping[str, Any]) -> NotebookEntryRecord:
    return NotebookEntryRecord(
        id=row["id"],
        notebook_id=row["notebook_id"],
        author_id=row["author_id"],
        highlight=row["highlight"],
        annotation=row.get("annotation"),
        annotation_format=row.get("annotation_format") or "markdown",
        tags=_serialize_tags(row.get("tags")),
        source=row.get("source") or {},
        is_pinned=bool(row.get("is_pinned")),
        position=int(row.get("position") or 0),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_share(row: Mapping[str, Any]) -> NotebookShareRecord:
    return NotebookShareRecord(
        id=row["id"],
        notebook_id=row["notebook_id"],
        token=row["token"],
        created_by=row["created_by"],
        expires_at=row.get("expires_at"),
        password_protected=bool(row.get("password_hash")),
        password_hint=row.get("password_hint"),
        access_scope=row.get("access_scope") or "view",
        revoked_at=row.get("revoked_at"),
        last_accessed_at=row.get("last_accessed_at"),
        created_at=row["created_at"],
    )


def list_notebooks(
    session: Session,
    *,
    org_id: uuid.UUID,
    query: Optional[str] = None,
    tags: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
) -> List[NotebookRecord]:
    filters = ["org_id = :org_id"]
    params: Dict[str, Any] = {"org_id": str(org_id), "limit": _clamp_limit(limit)}
    if query and query.strip():
        params["needle"] = f"%{query.strip()}%"
        filters.append("(title ILIKE :needle OR summary ILIKE :needle)")
    normalized_tags = _normalize_tags(tags)
    if normalized_tags:
        params["tag_filter"] = normalized_tags
        filters.append("tags @> :tag_filter")

    where_clause = " AND ".join(filters)
    rows = (
        session.execute(
            text(
                f"""
                SELECT id, org_id, owner_id, title, summary, tags, cover_color, metadata, entry_count,
                       last_activity_at, created_at, updated_at
                FROM notebooks
                WHERE {where_clause}
                ORDER BY COALESCE(last_activity_at, updated_at, created_at) DESC
                LIMIT :limit
                """
            ),
            params,
        )
        .mappings()
        .all()
    )
    return [_row_to_notebook(row) for row in rows]


def get_notebook(session: Session, *, notebook_id: uuid.UUID, org_id: uuid.UUID) -> NotebookRecord:
    row = (
        session.execute(
            text(
                """
                SELECT id, org_id, owner_id, title, summary, tags, cover_color, metadata, entry_count,
                       last_activity_at, created_at, updated_at
                FROM notebooks
                WHERE id = :id AND org_id = :org_id
                """
            ),
            {"id": str(notebook_id), "org_id": str(org_id)},
        )
        .mappings()
        .first()
    )
    if not row:
        raise NotebookNotFoundError("Notebook not found for this organisation.")
    return _row_to_notebook(row)


def create_notebook(
    session: Session,
    *,
    org_id: uuid.UUID,
    owner_id: uuid.UUID,
    title: str,
    summary: Optional[str],
    tags: Optional[Sequence[str]],
    cover_color: Optional[str],
    metadata: Optional[Mapping[str, Any]],
) -> NotebookRecord:
    safe_title = _trim(title)
    if not safe_title:
        raise NotebookServiceError("Notebook title is required.")
    if len(safe_title) > MAX_NOTEBOOK_TITLE:
        raise NotebookServiceError("Notebook title is too long.")
    safe_summary = _trim(summary)
    if safe_summary and len(safe_summary) > MAX_NOTEBOOK_SUMMARY:
        safe_summary = safe_summary[:MAX_NOTEBOOK_SUMMARY]
    normalized_tags = _normalize_tags(tags)
    safe_metadata = _safe_metadata(metadata)
    safe_color = _sanitize_color(cover_color)
    row = (
        session.execute(
            text(
                """
                INSERT INTO notebooks (org_id, owner_id, title, summary, tags, cover_color, metadata)
                VALUES (:org_id, :owner_id, :title, :summary, :tags, :cover_color, :metadata::jsonb)
                RETURNING id, org_id, owner_id, title, summary, tags, cover_color, metadata, entry_count,
                          last_activity_at, created_at, updated_at
                """
            ),
            {
                "org_id": str(org_id),
                "owner_id": str(owner_id),
                "title": safe_title,
                "summary": safe_summary,
                "tags": normalized_tags,
                "cover_color": safe_color,
                "metadata": safe_metadata,
            },
        )
        .mappings()
        .first()
    )
    session.commit()
    return _row_to_notebook(row)


def update_notebook(
    session: Session,
    *,
    notebook_id: uuid.UUID,
    org_id: uuid.UUID,
    title: Optional[str] = None,
    summary: Optional[str] = None,
    tags: Optional[Sequence[str]] = None,
    cover_color: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> NotebookRecord:
    assignments: List[str] = []
    params: Dict[str, Any] = {"id": str(notebook_id), "org_id": str(org_id)}
    if title is not None:
        safe_title = _trim(title)
        if not safe_title:
            raise NotebookServiceError("Notebook title cannot be empty.")
        if len(safe_title) > MAX_NOTEBOOK_TITLE:
            raise NotebookServiceError("Notebook title is too long.")
        assignments.append("title = :title")
        params["title"] = safe_title
    if summary is not None:
        safe_summary = _trim(summary)
        if safe_summary and len(safe_summary) > MAX_NOTEBOOK_SUMMARY:
            safe_summary = safe_summary[:MAX_NOTEBOOK_SUMMARY]
        assignments.append("summary = :summary")
        params["summary"] = safe_summary
    if tags is not None:
        assignments.append("tags = :tags")
        params["tags"] = _normalize_tags(tags)
    if cover_color is not None:
        assignments.append("cover_color = :cover_color")
        params["cover_color"] = _sanitize_color(cover_color)
    if metadata is not None:
        assignments.append("metadata = :metadata::jsonb")
        params["metadata"] = _safe_metadata(metadata)
    if not assignments:
        return get_notebook(session, notebook_id=notebook_id, org_id=org_id)

    set_clause = ", ".join(assignments)
    row = (
        session.execute(
            text(
                f"""
                UPDATE notebooks
                SET {set_clause}, updated_at = NOW()
                WHERE id = :id AND org_id = :org_id
                RETURNING id, org_id, owner_id, title, summary, tags, cover_color, metadata, entry_count,
                          last_activity_at, created_at, updated_at
                """
            ),
            params,
        )
        .mappings()
        .first()
    )
    if not row:
        session.rollback()
        raise NotebookNotFoundError("Notebook not found.")
    session.commit()
    return _row_to_notebook(row)


def delete_notebook(session: Session, *, notebook_id: uuid.UUID, org_id: uuid.UUID) -> None:
    result = session.execute(
        text("DELETE FROM notebooks WHERE id = :id AND org_id = :org_id"),
        {"id": str(notebook_id), "org_id": str(org_id)},
    )
    if result.rowcount == 0:
        session.rollback()
        raise NotebookNotFoundError("Notebook not found.")
    session.commit()


def list_entries(
    session: Session,
    *,
    notebook_id: uuid.UUID,
    org_id: uuid.UUID,
    tag_filter: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
) -> List[NotebookEntryRecord]:
    _ = get_notebook(session, notebook_id=notebook_id, org_id=org_id)
    filters = ["notebook_id = :notebook_id"]
    params: Dict[str, Any] = {"notebook_id": str(notebook_id), "limit": _clamp_limit(limit)}
    normalized_tags = _normalize_tags(tag_filter)
    if normalized_tags:
        filters.append("tags && :tag_filter")
        params["tag_filter"] = normalized_tags
    where_clause = " AND ".join(filters)
    rows = (
        session.execute(
            text(
                f"""
                SELECT id, notebook_id, author_id, highlight, annotation, annotation_format,
                       tags, source, is_pinned, position, created_at, updated_at
                FROM notebook_entries
                WHERE {where_clause}
                ORDER BY is_pinned DESC, position DESC, created_at DESC
                LIMIT :limit
                """
            ),
            params,
        )
        .mappings()
        .all()
    )
    return [_row_to_entry(row) for row in rows]


def _next_position(session: Session, notebook_id: uuid.UUID) -> int:
    value = session.execute(
        text(
            """
            SELECT COALESCE(MAX(position), 0) + 1
            FROM notebook_entries
            WHERE notebook_id = :notebook_id
            """
        ),
        {"notebook_id": str(notebook_id)},
    ).scalar_one()
    return int(value or 0)


def create_entry(
    session: Session,
    *,
    notebook_id: uuid.UUID,
    org_id: uuid.UUID,
    author_id: uuid.UUID,
    highlight: str,
    annotation: Optional[str],
    tags: Optional[Sequence[str]],
    source: Optional[Mapping[str, Any]],
    is_pinned: bool = False,
    position: Optional[int] = None,
    annotation_format: str = "markdown",
) -> NotebookEntryRecord:
    _ = get_notebook(session, notebook_id=notebook_id, org_id=org_id)
    safe_highlight = _trim(highlight)
    if not safe_highlight:
        raise NotebookServiceError("Highlight text is required.")
    if len(safe_highlight) > MAX_HIGHLIGHT_LENGTH:
        safe_highlight = safe_highlight[:MAX_HIGHLIGHT_LENGTH]
    safe_annotation = _trim(annotation)
    if safe_annotation and len(safe_annotation) > MAX_ANNOTATION_LENGTH:
        safe_annotation = safe_annotation[:MAX_ANNOTATION_LENGTH]
    safe_tags = _normalize_tags(tags)
    desired_position = position if isinstance(position, int) else None
    if desired_position is None:
        desired_position = _next_position(session, notebook_id)
    row = (
        session.execute(
            text(
                """
                INSERT INTO notebook_entries (
                    notebook_id, author_id, highlight, annotation, annotation_format,
                    tags, source, is_pinned, position
                )
                VALUES (
                    :notebook_id, :author_id, :highlight, :annotation, :annotation_format,
                    :tags, :source::jsonb, :is_pinned, :position
                )
                RETURNING id, notebook_id, author_id, highlight, annotation, annotation_format,
                          tags, source, is_pinned, position, created_at, updated_at
                """
            ),
            {
                "notebook_id": str(notebook_id),
                "author_id": str(author_id),
                "highlight": safe_highlight,
                "annotation": safe_annotation,
                "annotation_format": annotation_format or "markdown",
                "tags": safe_tags,
                "source": _sanitize_source(source),
                "is_pinned": bool(is_pinned),
                "position": desired_position,
            },
        )
        .mappings()
        .first()
    )
    session.commit()
    return _row_to_entry(row)


def update_entry(
    session: Session,
    *,
    notebook_id: uuid.UUID,
    org_id: uuid.UUID,
    entry_id: uuid.UUID,
    highlight: Optional[str] = None,
    annotation: Optional[str] = None,
    tags: Optional[Sequence[str]] = None,
    source: Optional[Mapping[str, Any]] = None,
    is_pinned: Optional[bool] = None,
    position: Optional[int] = None,
    annotation_format: Optional[str] = None,
) -> NotebookEntryRecord:
    _ = get_notebook(session, notebook_id=notebook_id, org_id=org_id)
    assignments: List[str] = []
    params: Dict[str, Any] = {"id": str(entry_id), "notebook_id": str(notebook_id)}

    if highlight is not None:
        safe_highlight = _trim(highlight)
        if not safe_highlight:
            raise NotebookServiceError("Highlight text cannot be empty.")
        if len(safe_highlight) > MAX_HIGHLIGHT_LENGTH:
            safe_highlight = safe_highlight[:MAX_HIGHLIGHT_LENGTH]
        assignments.append("highlight = :highlight")
        params["highlight"] = safe_highlight
    if annotation is not None:
        safe_annotation = _trim(annotation)
        if safe_annotation and len(safe_annotation) > MAX_ANNOTATION_LENGTH:
            safe_annotation = safe_annotation[:MAX_ANNOTATION_LENGTH]
        assignments.append("annotation = :annotation")
        params["annotation"] = safe_annotation
    if annotation_format is not None:
        assignments.append("annotation_format = :annotation_format")
        params["annotation_format"] = annotation_format or "markdown"
    if tags is not None:
        assignments.append("tags = :tags")
        params["tags"] = _normalize_tags(tags)
    if source is not None:
        assignments.append("source = :source::jsonb")
        params["source"] = _sanitize_source(source)
    if is_pinned is not None:
        assignments.append("is_pinned = :is_pinned")
        params["is_pinned"] = bool(is_pinned)
    if position is not None:
        assignments.append("position = :position")
        params["position"] = int(position)
    if not assignments:
        rows = (
            session.execute(
                text(
                    """
                    SELECT id, notebook_id, author_id, highlight, annotation, annotation_format,
                           tags, source, is_pinned, position, created_at, updated_at
                    FROM notebook_entries
                    WHERE id = :id AND notebook_id = :notebook_id
                    """
                ),
                params,
            )
            .mappings()
            .first()
        )
        if not rows:
            raise NotebookServiceError("Notebook entry not found.")
        return _row_to_entry(rows)

    set_clause = ", ".join(assignments)
    row = (
        session.execute(
            text(
                f"""
                UPDATE notebook_entries
                SET {set_clause}, updated_at = NOW()
                WHERE id = :id AND notebook_id = :notebook_id
                RETURNING id, notebook_id, author_id, highlight, annotation, annotation_format,
                          tags, source, is_pinned, position, created_at, updated_at
                """
            ),
            params,
        )
        .mappings()
        .first()
    )
    if not row:
        session.rollback()
        raise NotebookServiceError("Notebook entry not found.")
    session.commit()
    return _row_to_entry(row)


def delete_entry(session: Session, *, notebook_id: uuid.UUID, org_id: uuid.UUID, entry_id: uuid.UUID) -> None:
    _ = get_notebook(session, notebook_id=notebook_id, org_id=org_id)
    result = session.execute(
        text("DELETE FROM notebook_entries WHERE id = :id AND notebook_id = :notebook_id"),
        {"id": str(entry_id), "notebook_id": str(notebook_id)},
    )
    if result.rowcount == 0:
        session.rollback()
        raise NotebookServiceError("Notebook entry not found.")
    session.commit()


def list_shares(session: Session, *, notebook_id: uuid.UUID, org_id: uuid.UUID) -> List[NotebookShareRecord]:
    _ = get_notebook(session, notebook_id=notebook_id, org_id=org_id)
    rows = (
        session.execute(
            text(
                """
                SELECT id, notebook_id, token, created_by, expires_at, password_hash,
                       password_hint, access_scope, revoked_at, last_accessed_at, created_at
                FROM notebook_shares
                WHERE notebook_id = :notebook_id
                ORDER BY created_at DESC
                """
            ),
            {"notebook_id": str(notebook_id)},
        )
        .mappings()
        .all()
    )
    return [_row_to_share(row) for row in rows]


def _generate_share_token() -> str:
    return secrets.token_urlsafe(32)


def _hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def _verify_password(password_hash: str, password: str) -> bool:
    try:
        _PASSWORD_HASHER.verify(password_hash, password)
        return True
    except VerifyMismatchError:
        return False


def create_share_link(
    session: Session,
    *,
    notebook_id: uuid.UUID,
    org_id: uuid.UUID,
    created_by: uuid.UUID,
    expires_in_minutes: Optional[int],
    password: Optional[str],
    password_hint: Optional[str],
    access_scope: str = "view",
) -> NotebookShareRecord:
    _ = get_notebook(session, notebook_id=notebook_id, org_id=org_id)
    active_count = (
        session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM notebook_shares
                WHERE notebook_id = :notebook_id AND revoked_at IS NULL
                """
            ),
            {"notebook_id": str(notebook_id)},
        )
        .scalar_one()
    )
    if int(active_count or 0) >= MAX_ACTIVE_SHARES:
        raise NotebookShareError("Maximum active share links reached for this notebook.")

    ttl = expires_in_minutes if isinstance(expires_in_minutes, int) else DEFAULT_SHARE_TTL_MINUTES
    ttl = max(MIN_SHARE_TTL_MINUTES, min(ttl, MAX_SHARE_TTL_MINUTES))
    expires_at = _now() + timedelta(minutes=ttl) if ttl else None
    safe_password = _trim(password)
    hashed_password = _hash_password(safe_password) if safe_password else None
    safe_hint = _trim(password_hint)
    if safe_hint and len(safe_hint) > MAX_SHARE_HINT:
        safe_hint = safe_hint[:MAX_SHARE_HINT]
    normalized_scope = access_scope or "view"
    if normalized_scope not in {"view"}:
        raise NotebookShareError("Unsupported access scope.")

    attempts = 0
    while attempts < 3:
        token = _generate_share_token()
        try:
            row = (
                session.execute(
                    text(
                        """
                        INSERT INTO notebook_shares (
                            notebook_id, token, created_by, expires_at, password_hash,
                            password_hint, access_scope
                        )
                        VALUES (
                            :notebook_id, :token, :created_by, :expires_at, :password_hash,
                            :password_hint, :access_scope
                        )
                        RETURNING id, notebook_id, token, created_by, expires_at, password_hash,
                                  password_hint, access_scope, revoked_at, last_accessed_at, created_at
                        """
                    ),
                    {
                        "notebook_id": str(notebook_id),
                        "token": token,
                        "created_by": str(created_by),
                        "expires_at": expires_at,
                        "password_hash": hashed_password,
                        "password_hint": safe_hint,
                        "access_scope": normalized_scope,
                    },
                )
                .mappings()
                .first()
            )
            session.commit()
            record = _row_to_share(row)
            return record
        except IntegrityError:
            session.rollback()
            attempts += 1
            continue
    raise NotebookShareError("Failed to create a unique share link. Please retry.")


def revoke_share_link(session: Session, *, notebook_id: uuid.UUID, org_id: uuid.UUID, share_id: uuid.UUID) -> NotebookShareRecord:
    _ = get_notebook(session, notebook_id=notebook_id, org_id=org_id)
    row = (
        session.execute(
            text(
                """
                UPDATE notebook_shares
                SET revoked_at = NOW()
                WHERE id = :share_id AND notebook_id = :notebook_id
                RETURNING id, notebook_id, token, created_by, expires_at, password_hash,
                          password_hint, access_scope, revoked_at, last_accessed_at, created_at
                """
            ),
            {"share_id": str(share_id), "notebook_id": str(notebook_id)},
        )
        .mappings()
        .first()
    )
    if not row:
        session.rollback()
        raise NotebookShareError("Share link not found.")
    session.commit()
    return _row_to_share(row)


@dataclass(frozen=True)
class NotebookShareView:
    share: NotebookShareRecord
    notebook: NotebookRecord
    entries: List[NotebookEntryRecord]


def resolve_share_token(
    session: Session,
    *,
    token: str,
    password: Optional[str],
) -> NotebookShareView:
    safe_token = _trim(token)
    if not safe_token:
        raise NotebookShareAccessError("invalid_token")
    row = (
        session.execute(
            text(
                """
                SELECT
                    s.id AS share_id,
                    s.notebook_id AS share_notebook_id,
                    s.token AS share_token,
                    s.created_by AS share_created_by,
                    s.expires_at AS share_expires_at,
                    s.password_hash AS share_password_hash,
                    s.password_hint AS share_password_hint,
                    s.access_scope AS share_access_scope,
                    s.revoked_at AS share_revoked_at,
                    s.last_accessed_at AS share_last_accessed_at,
                    s.created_at AS share_created_at,
                    n.id AS notebook_id,
                    n.org_id,
                    n.owner_id,
                    n.title,
                    n.summary,
                    n.tags,
                    n.cover_color,
                    n.metadata,
                    n.entry_count,
                    n.last_activity_at,
                    n.created_at,
                    n.updated_at
                FROM notebook_shares s
                JOIN notebooks n ON n.id = s.notebook_id
                WHERE s.token = :token
                """
            ),
            {"token": safe_token},
        )
        .mappings()
        .first()
    )
    if not row:
        raise NotebookShareAccessError("not_found")

    share = NotebookShareRecord(
        id=row["share_id"],
        notebook_id=row["share_notebook_id"],
        token=row["share_token"],
        created_by=row["share_created_by"],
        expires_at=row.get("share_expires_at"),
        password_protected=bool(row.get("share_password_hash")),
        password_hint=row.get("share_password_hint"),
        access_scope=row.get("share_access_scope") or "view",
        revoked_at=row.get("share_revoked_at"),
        last_accessed_at=row.get("share_last_accessed_at"),
        created_at=row["share_created_at"],
    )
    if share.revoked_at:
        raise NotebookShareAccessError("revoked")
    if share.expires_at and share.expires_at <= _now():
        raise NotebookShareAccessError("expired")
    password_hash = row.get("share_password_hash")
    if password_hash:
        provided = _trim(password)
        if not provided:
            raise NotebookShareAccessError("password_required")
        if not _verify_password(password_hash, provided):
            raise NotebookShareAccessError("password_invalid")

    notebook = NotebookRecord(
        id=row["notebook_id"],
        org_id=row["org_id"],
        owner_id=row["owner_id"],
        title=row["title"],
        summary=row.get("summary"),
        tags=_serialize_tags(row.get("tags")),
        cover_color=row.get("cover_color"),
        metadata=row.get("metadata") or {},
        entry_count=int(row.get("entry_count") or 0),
        last_activity_at=row.get("last_activity_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
    entries = list_entries(
        session,
        notebook_id=notebook.id,
        org_id=notebook.org_id,
        limit=MAX_LIST_LIMIT,
    )
    try:
        session.execute(
            text(
                """
                UPDATE notebook_shares
                SET last_accessed_at = NOW()
                WHERE id = :share_id
                """
            ),
            {"share_id": str(share.id)},
        )
        session.commit()
    except SQLAlchemyError:  # pragma: no cover - best effort
        session.rollback()
        logger.warning("Failed to record last_accessed_at for share=%s", share.id)

    return NotebookShareView(share=share, notebook=notebook, entries=entries)


__all__ = [
    "NotebookEntryRecord",
    "NotebookNotFoundError",
    "NotebookRecord",
    "NotebookServiceError",
    "NotebookShareAccessError",
    "NotebookShareError",
    "NotebookShareRecord",
    "NotebookShareView",
    "create_entry",
    "create_notebook",
    "create_share_link",
    "delete_entry",
    "delete_notebook",
    "get_notebook",
    "list_entries",
    "list_notebooks",
    "list_shares",
    "resolve_share_token",
    "revoke_share_link",
    "update_entry",
    "update_notebook",
]
