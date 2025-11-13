"""SCIM v2 helper functions for Users/Groups resources."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.env import env_bool, env_int
from services.audit_log import audit_rbac_event
from services.rbac_service import ROLE_ORDER

logger = logging.getLogger(__name__)

SCIM_CORE_USER = "urn:ietf:params:scim:schemas:core:2.0:User"
SCIM_CORE_GROUP = "urn:ietf:params:scim:schemas:core:2.0:Group"
SCIM_LIST_RESPONSE = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
SCIM_ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"
SCIM_EXTENSION_SCHEMA = "urn:scim:schemas:extension:kfinance:1.0:User"

PLAN_TIERS = {"free", "pro", "enterprise"}
USER_ROLES = {"user", "admin"}

SCIM_MAX_PAGE_SIZE = env_int("SCIM_MAX_PAGE_SIZE", 100, minimum=1)
SCIM_AUTO_PROVISION_ORG = env_bool("SCIM_AUTO_PROVISION_ORG", False)


class ScimError(RuntimeError):
    """Raised when SCIM requests are invalid."""

    def __init__(self, status_code: int, detail: str, scim_type: Optional[str] = None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.scim_type = scim_type


@dataclass(frozen=True)
class ScimListResult:
    resources: List[Dict[str, Any]]
    total: int
    start_index: int


def list_scim_users(session: Session, *, start_index: int, count: int) -> ScimListResult:
    offset = max(start_index - 1, 0)
    limit = min(max(count, 1), SCIM_MAX_PAGE_SIZE)
    total = session.execute(text('SELECT COUNT(*) FROM "users"')).scalar_one()
    rows = (
        session.execute(
            text(
                """
                SELECT id, email, name, plan_tier, role, signup_channel, email_verified_at, locked_until
                FROM "users"
                ORDER BY LOWER(email) ASC
                OFFSET :offset
                LIMIT :limit
                """
            ),
            {"offset": offset, "limit": limit},
        )
        .mappings()
        .all()
    )
    resources = [_serialize_user_resource(session, row) for row in rows]
    return ScimListResult(resources=resources, total=total, start_index=start_index)


def get_scim_user(session: Session, user_id: uuid.UUID) -> Dict[str, Any]:
    row = (
        session.execute(
            text(
                """
                SELECT id, email, name, plan_tier, role, signup_channel, email_verified_at, locked_until
                FROM "users"
                WHERE id = :id
                """
            ),
            {"id": str(user_id)},
        )
        .mappings()
        .first()
    )
    if not row:
        raise ScimError(404, "User not found.", "resourceNotFound")
    return _serialize_user_resource(session, row)


def create_scim_user(session: Session, payload: Mapping[str, Any]) -> Dict[str, Any]:
    email = _extract_email(payload)
    active = bool(payload.get("active", True))
    display_name = payload.get("displayName") or (payload.get("name") or {}).get("formatted")
    extension = payload.get(SCIM_EXTENSION_SCHEMA) or {}
    plan_tier = _normalize_plan_tier(extension.get("planTier"))
    app_role = _normalize_user_role(extension.get("role"))
    groups = payload.get("groups") or []
    slug_targets = _collect_extension_slugs(extension)
    org_ids = _resolve_org_targets(session, groups, slug_targets, extension.get("orgId"))
    now = datetime.now(timezone.utc)
    with session.begin():
        existing = (
            session.execute(
                text('SELECT id FROM "users" WHERE LOWER(email) = :email'),
                {"email": email.lower()},
            )
            .mappings()
            .first()
        )
        if existing:
            raise ScimError(409, "User already exists.", "uniqueness")
        row = (
            session.execute(
                text(
                    """
                    INSERT INTO "users" (email, name, signup_channel, plan_tier, role, email_verified_at, failed_attempts, locked_until)
                    VALUES (:email, :name, 'scim', :plan_tier, :role, :now, 0, NULL)
                    RETURNING id
                    """
                ),
                {
                    "email": email,
                    "name": display_name,
                    "plan_tier": plan_tier,
                    "role": app_role,
                    "now": now,
                },
            )
            .mappings()
            .first()
        )
        user_id = row["id"]
        _apply_active_flag(session, user_id, active)
        for org_id in org_ids or []:
            _upsert_membership(session, org_id, user_id, extension.get("rbacRole"))
    return get_scim_user(session, uuid.UUID(str(user_id)))


def patch_scim_user(session: Session, user_id: uuid.UUID, payload: Mapping[str, Any]) -> Dict[str, Any]:
    operations = payload.get("Operations")
    changes = payload
    if isinstance(operations, list):
        merged: Dict[str, Any] = {}
        for operation in operations:
            op = (operation.get("op") or "").lower()
            if op not in {"replace", "add"}:
                continue
            value = operation.get("value")
            if isinstance(value, Mapping):
                merged.update(value)
        changes = merged or payload
    extension = changes.get(SCIM_EXTENSION_SCHEMA) or {}
    groups = changes.get("groups")
    active = changes.get("active")
    plan_tier = extension.get("planTier")
    app_role = extension.get("role")
    with session.begin():
        row = (
            session.execute(
                text('SELECT id FROM "users" WHERE id = :id'),
                {"id": str(user_id)},
            )
            .mappings()
            .first()
        )
        if not row:
            raise ScimError(404, "User not found.", "resourceNotFound")
        updates: Dict[str, Any] = {}
        if plan_tier:
            updates["plan_tier"] = _normalize_plan_tier(plan_tier)
        if app_role:
            updates["role"] = _normalize_user_role(app_role)
        if changes.get("displayName"):
            updates["name"] = changes["displayName"]
        if updates:
            assignments = ", ".join(f'{column} = :{column}' for column in updates)
            stmt = text(f'UPDATE "users" SET {assignments} WHERE id = :id')
            session.execute(stmt, {**updates, "id": str(user_id)})
        if active is not None:
            _apply_active_flag(session, str(user_id), bool(active))
        if groups is not None or extension:
            target_org_ids = _resolve_org_targets(
                session,
                groups or [],
                _collect_extension_slugs(extension),
                extension.get("orgId"),
            )
            if target_org_ids is not None:
                session.execute(
                    text("DELETE FROM user_orgs WHERE user_id = :user_id"),
                    {"user_id": str(user_id)},
                )
                for org_id in target_org_ids:
                    _upsert_membership(session, org_id, str(user_id), extension.get("rbacRole"))
    return get_scim_user(session, user_id)


def delete_scim_user(session: Session, user_id: uuid.UUID) -> None:
    with session.begin():
        row = (
            session.execute(
                text('SELECT id FROM "users" WHERE id = :id'),
                {"id": str(user_id)},
            )
            .mappings()
            .first()
        )
        if not row:
            raise ScimError(404, "User not found.", "resourceNotFound")
        _apply_active_flag(session, str(user_id), False)


def list_scim_groups(session: Session, *, start_index: int, count: int) -> ScimListResult:
    offset = max(start_index - 1, 0)
    limit = min(max(count, 1), SCIM_MAX_PAGE_SIZE)
    total = session.execute(text("SELECT COUNT(*) FROM orgs")).scalar_one()
    rows = (
        session.execute(
            text(
                """
                SELECT id, name, slug, status, default_role
                FROM orgs
                ORDER BY LOWER(name) ASC
                OFFSET :offset
                LIMIT :limit
                """
            ),
            {"offset": offset, "limit": limit},
        )
        .mappings()
        .all()
    )
    resources = [_serialize_group_resource(session, row) for row in rows]
    return ScimListResult(resources=resources, total=total, start_index=start_index)


def get_scim_group(session: Session, group_id: uuid.UUID) -> Dict[str, Any]:
    row = (
        session.execute(
            text(
                """
                SELECT id, name, slug, status, default_role
                FROM orgs
                WHERE id = :id
                """
            ),
            {"id": str(group_id)},
        )
        .mappings()
        .first()
    )
    if not row:
        raise ScimError(404, "Group not found.", "resourceNotFound")
    return _serialize_group_resource(session, row)


def create_scim_group(session: Session, payload: Mapping[str, Any]) -> Dict[str, Any]:
    name = (payload.get("displayName") or "").strip()
    if not name:
        raise ScimError(400, "displayName is required.", "invalidValue")
    slug = payload.get("externalId") or payload.get("slug") or name
    members = payload.get("members") or []
    with session.begin():
        org_id = uuid.uuid4()
        session.execute(
            text(
                """
                INSERT INTO orgs (id, name, slug, status, default_role, metadata)
                VALUES (:id, :name, :slug, 'active', 'viewer', CAST(:metadata AS JSONB))
                """
            ),
            {
                "id": str(org_id),
                "name": name,
                "slug": _slugify(slug),
                "metadata": json.dumps({"provisionedBy": "scim"}),
            },
        )
        for member in members:
            user_id = member.get("value")
            if not user_id:
                continue
            try:
                member_id = uuid.UUID(str(user_id))
            except (TypeError, ValueError):
                continue
            _upsert_membership(session, org_id, str(member_id), member.get("type"))
    return get_scim_group(session, org_id)


def patch_scim_group(session: Session, group_id: uuid.UUID, payload: Mapping[str, Any]) -> Dict[str, Any]:
    operations = payload.get("Operations")
    target = payload
    if isinstance(operations, list):
        merged: Dict[str, Any] = {}
        for operation in operations:
            if (operation.get("op") or "").lower() != "replace":
                continue
            value = operation.get("value")
            if isinstance(value, Mapping):
                merged.update(value)
        target = merged or payload
    with session.begin():
        row = (
            session.execute(
                text("SELECT id FROM orgs WHERE id = :id"),
                {"id": str(group_id)},
            )
            .mappings()
            .first()
        )
        if not row:
            raise ScimError(404, "Group not found.", "resourceNotFound")
        if target.get("displayName"):
            session.execute(
                text("UPDATE orgs SET name = :name WHERE id = :id"),
                {"name": target["displayName"], "id": str(group_id)},
            )
        if target.get("members") is not None:
            session.execute(text("DELETE FROM user_orgs WHERE org_id = :id"), {"id": str(group_id)})
            for member in target.get("members") or []:
                user_id = member.get("value")
                if not user_id:
                    continue
                try:
                    parsed = uuid.UUID(str(user_id))
                except (TypeError, ValueError):
                    continue
                _upsert_membership(session, group_id, str(parsed), member.get("type"))
    return get_scim_group(session, group_id)


def _serialize_user_resource(session: Session, row: Mapping[str, Any]) -> Dict[str, Any]:
    membership_rows = (
        session.execute(
            text(
                """
                SELECT uo.org_id, uo.role_key, o.name
                FROM user_orgs uo
                JOIN orgs o ON o.id = uo.org_id
                WHERE uo.user_id = :user_id
                  AND uo.status = 'active'
                """
            ),
            {"user_id": row["id"]},
        )
        .mappings()
        .all()
    )
    groups = [
        {
            "value": str(m["org_id"]),
            "display": m["name"],
            "type": m["role_key"],
            "$ref": f"/scim/v2/Groups/{m['org_id']}",
        }
        for m in membership_rows
    ]
    active = row.get("locked_until") is None
    meta = _scim_meta("User")
    return {
        "schemas": [SCIM_CORE_USER, SCIM_EXTENSION_SCHEMA],
        "id": str(row["id"]),
        "userName": row["email"],
        "displayName": row.get("name"),
        "active": active,
        "emails": [{"value": row["email"], "type": "work", "primary": True}],
        "groups": groups,
        "meta": meta,
        SCIM_EXTENSION_SCHEMA: {
            "planTier": row.get("plan_tier"),
            "role": row.get("role"),
        },
    }


def _serialize_group_resource(session: Session, row: Mapping[str, Any]) -> Dict[str, Any]:
    members = (
        session.execute(
            text(
                """
                SELECT user_id, role_key
                FROM user_orgs
                WHERE org_id = :org_id
                  AND status = 'active'
                """
            ),
            {"org_id": row["id"]},
        )
        .mappings()
        .all()
    )
    return {
        "schemas": [SCIM_CORE_GROUP],
        "id": str(row["id"]),
        "displayName": row["name"],
        "members": [
            {
                "value": str(member["user_id"]),
                "type": member["role_key"],
                "$ref": f"/scim/v2/Users/{member['user_id']}",
            }
            for member in members
        ],
        "meta": _scim_meta("Group"),
    }


def _scim_meta(resource_type: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "resourceType": resource_type,
        "created": now,
        "lastModified": now,
        "version": f"W/\"{int(datetime.now(timezone.utc).timestamp())}\"",
        "location": None,
    }


def _extract_email(payload: Mapping[str, Any]) -> str:
    user_name = payload.get("userName")
    if user_name:
        return user_name.strip().lower()
    emails = payload.get("emails") or []
    for email in emails:
        value = (email or {}).get("value")
        if value:
            return str(value).strip().lower()
    raise ScimError(400, "userName or emails[0].value is required.", "invalidValue")


def _collect_extension_slugs(extension: Mapping[str, Any]) -> List[str]:
    slugs: List[str] = []
    if not extension:
        return slugs
    if extension.get("orgSlug"):
        slugs.append(str(extension["orgSlug"]))
    if extension.get("orgSlugs"):
        slugs.extend([str(item) for item in extension["orgSlugs"] if item])
    return slugs


def _resolve_org_targets(
    session: Session,
    groups: Sequence[Mapping[str, Any]],
    slug_targets: Sequence[str],
    explicit_org: Optional[str],
) -> Optional[List[uuid.UUID]]:
    targets: List[uuid.UUID] = []
    identifiers: List[str] = []
    for group in groups:
        value = group.get("value")
        if value:
            identifiers.append(str(value))
    if explicit_org:
        identifiers.append(str(explicit_org))
    for candidate in identifiers:
        parsed = _maybe_uuid(candidate)
        if parsed:
            targets.append(parsed)
        else:
            slug = candidate
            org_id = _lookup_org_by_slug(session, slug)
            if org_id:
                targets.append(org_id)
            elif SCIM_AUTO_PROVISION_ORG:
                targets.append(_create_org(session, slug))
    for slug in slug_targets:
        if slug:
            org_id = _lookup_org_by_slug(session, slug)
            if org_id:
                targets.append(org_id)
            elif SCIM_AUTO_PROVISION_ORG:
                targets.append(_create_org(session, slug))
    return targets or None


def _apply_active_flag(session: Session, user_id: str, active: bool) -> None:
    lock_value = None if active else datetime.max.replace(tzinfo=timezone.utc)
    session.execute(
        text(
            """
            UPDATE "users"
            SET locked_until = :locked_until
            WHERE id = :id
            """
        ),
        {"locked_until": lock_value, "id": user_id},
    )


def _upsert_membership(session: Session, org_id: uuid.UUID, user_id: str, role: Optional[str]) -> None:
    normalized_role = _normalize_rbac_role(role)
    session.execute(
        text(
            """
            INSERT INTO user_orgs (org_id, user_id, role_key, status, invited_by, invited_at, accepted_at)
            VALUES (:org_id, :user_id, :role_key, 'active', :user_id, NOW(), NOW())
            ON CONFLICT (org_id, user_id) DO UPDATE SET
                role_key = EXCLUDED.role_key,
                status = 'active',
                accepted_at = COALESCE(user_orgs.accepted_at, EXCLUDED.accepted_at),
                updated_at = NOW()
            """
        ),
        {"org_id": str(org_id), "user_id": user_id, "role_key": normalized_role},
    )
    audit_rbac_event(
        action="rbac.membership.upsert",
        actor=user_id,
        org_id=org_id,
        target_id=user_id,
        extra={"role": normalized_role, "source": "scim"},
    )


def _normalize_plan_tier(value: Optional[str]) -> str:
    candidate = (value or "enterprise").strip().lower()
    return candidate if candidate in PLAN_TIERS else "enterprise"


def _normalize_user_role(value: Optional[str]) -> str:
    candidate = (value or "user").strip().lower()
    return candidate if candidate in USER_ROLES else "user"


def _normalize_rbac_role(value: Optional[str]) -> str:
    candidate = (value or "viewer").strip().lower()
    return candidate if candidate in ROLE_ORDER else "viewer"


def _slugify(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = "".join(ch if ch.isalnum() else "-" for ch in value.lower())
    normalized = "-".join(filter(None, normalized.split("-")))
    return normalized[:60] or None


def _create_org(session: Session, slug: str) -> uuid.UUID:
    org_id = uuid.uuid4()
    session.execute(
        text(
            """
            INSERT INTO orgs (id, name, slug, status, default_role, metadata)
            VALUES (:id, :name, :slug, 'active', 'viewer', CAST(:metadata AS JSONB))
            ON CONFLICT (slug) DO NOTHING
            """
        ),
        {
            "id": str(org_id),
            "name": slug,
            "slug": _slugify(slug),
            "metadata": json.dumps({"provisionedBy": "scim"}),
        },
    )
    return org_id


def _lookup_org_by_slug(session: Session, slug: str) -> Optional[uuid.UUID]:
    row = (
        session.execute(
            text("SELECT id FROM orgs WHERE LOWER(slug) = :slug"),
            {"slug": slug.lower()},
        )
        .mappings()
        .first()
    )
    return row["id"] if row else None


def _maybe_uuid(value: str) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None
