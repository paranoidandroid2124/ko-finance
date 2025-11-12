"""Light RBAC helpers for organisation membership and enforcement."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Mapping, Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from core.env import env_bool
from services.audit_log import audit_rbac_event

try:  # pragma: no cover - optional during import-time
    from database import SessionLocal as _SessionLocal
except Exception:  # pragma: no cover
    _SessionLocal = None

logger = logging.getLogger(__name__)

ROLE_ORDER = {
    "viewer": 10,
    "editor": 20,
    "admin": 30,
}
VALID_STATUSES = {"active", "pending", "revoked"}
DEFAULT_ROLE = "viewer"
DEFAULT_STATUS = "active"
RBAC_ENFORCE_DEFAULT = env_bool("RBAC_ENFORCE", False)


class RbacServiceError(RuntimeError):
    """Raised when membership/role operations fail."""


@dataclass(frozen=True)
class OrgRecord:
    id: uuid.UUID
    name: str
    slug: Optional[str]
    status: str
    default_role: str
    metadata: Mapping[str, object]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class MembershipRecord:
    org_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    status: str
    invited_by: Optional[uuid.UUID]
    invited_at: Optional[datetime]
    accepted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class MembershipDecision:
    allowed: bool
    role: Optional[str]
    status: Optional[str]
    membership: Optional[MembershipRecord]
    reason: Optional[str] = None


def _session_factory() -> Session:
    if _SessionLocal is None:  # pragma: no cover - runtime guard
        raise RbacServiceError("SessionLocal is unavailable. DATABASE_URL must be configured.")
    return _SessionLocal()


def _role_rank(role: Optional[str]) -> int:
    if not role:
        return -1
    return ROLE_ORDER.get(role, -1)


def _normalize_role(role: Optional[str]) -> str:
    candidate = (role or DEFAULT_ROLE).strip().lower()
    if candidate not in ROLE_ORDER:
        raise RbacServiceError(f"Unknown role '{role}'. Must be one of: {', '.join(sorted(ROLE_ORDER))}")
    return candidate


def _normalize_status(status: Optional[str]) -> str:
    candidate = (status or DEFAULT_STATUS).strip().lower()
    if candidate not in VALID_STATUSES:
        raise RbacServiceError(f"Unknown membership status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}")
    return candidate


class RbacService:
    """Persistence + helper layer for Light RBAC."""

    def __init__(self, *, session_factory=_session_factory) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def get_org(self, org_id: uuid.UUID) -> Optional[OrgRecord]:
        session = self._session_factory()
        try:
            row = (
                session.execute(
                    text(
                        """
                        SELECT id, name, slug, status, default_role, metadata, created_at, updated_at
                        FROM orgs
                        WHERE id = :org_id
                        """
                    ),
                    {"org_id": str(org_id)},
                )
                .mappings()
                .first()
            )
            if not row:
                return None
            return OrgRecord(
                id=row["id"],
                name=row["name"],
                slug=row.get("slug"),
                status=row["status"],
                default_role=row["default_role"],
                metadata=row.get("metadata") or {},
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        finally:
            session.close()

    def list_memberships(self, *, user_id: uuid.UUID) -> List[MembershipRecord]:
        session = self._session_factory()
        try:
            rows = session.execute(
                text(
                    """
                    SELECT org_id, user_id, role_key, status, invited_by, invited_at, accepted_at, created_at, updated_at
                    FROM user_orgs
                    WHERE user_id = :user_id
                    ORDER BY created_at ASC
                    """
                ),
                {"user_id": str(user_id)},
            ).mappings()
            memberships: List[MembershipRecord] = []
            for row in rows:
                memberships.append(
                    MembershipRecord(
                        org_id=row["org_id"],
                        user_id=row["user_id"],
                        role=row["role_key"],
                        status=row["status"],
                        invited_by=row.get("invited_by"),
                        invited_at=row.get("invited_at"),
                        accepted_at=row.get("accepted_at"),
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    )
                )
            return memberships
        finally:
            session.close()

    def get_membership(self, *, org_id: uuid.UUID, user_id: uuid.UUID) -> Optional[MembershipRecord]:
        session = self._session_factory()
        try:
            row = (
                session.execute(
                    text(
                        """
                        SELECT org_id, user_id, role_key, status, invited_by, invited_at, accepted_at, created_at, updated_at
                        FROM user_orgs
                        WHERE org_id = :org_id AND user_id = :user_id
                        """
                    ),
                    {"org_id": str(org_id), "user_id": str(user_id)},
                )
                .mappings()
                .first()
            )
            if not row:
                return None
            return MembershipRecord(
                org_id=row["org_id"],
                user_id=row["user_id"],
                role=row["role_key"],
                status=row["status"],
                invited_by=row.get("invited_by"),
                invited_at=row.get("invited_at"),
                accepted_at=row.get("accepted_at"),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def ensure_personal_org(self, *, user_id: uuid.UUID) -> OrgRecord:
        """
        Ensure the user has at least one org membership by bootstrapping
        a private org with admin rights when missing.
        """

        session = self._session_factory()
        try:
            existing = session.execute(
                text(
                    """
                    SELECT o.id, o.name, o.slug, o.status, o.default_role, o.metadata, o.created_at, o.updated_at
                    FROM user_orgs u
                    JOIN orgs o ON o.id = u.org_id
                    WHERE u.user_id = :user_id
                    ORDER BY u.created_at ASC
                    LIMIT 1
                    """
                ),
                {"user_id": str(user_id)},
            ).mappings().first()
            if existing:
                return OrgRecord(
                    id=existing["id"],
                    name=existing["name"],
                    slug=existing.get("slug"),
                    status=existing["status"],
                    default_role=existing["default_role"],
                    metadata=existing.get("metadata") or {},
                    created_at=existing["created_at"],
                    updated_at=existing["updated_at"],
                )

            org_id = uuid.uuid4()
            name = f"Workspace {str(user_id)[:8]}"
            slug = None  # keep optional to avoid conflicts
            now = datetime.now(timezone.utc)
            session.execute(
                text(
                    """
                    INSERT INTO orgs (id, name, slug, status, default_role)
                    VALUES (:id, :name, :slug, 'active', 'viewer')
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {"id": str(org_id), "name": name, "slug": slug},
            )
            session.execute(
                text(
                    """
                    INSERT INTO user_orgs (org_id, user_id, role_key, status, invited_by, invited_at, accepted_at)
                    VALUES (:org_id, :user_id, 'admin', 'active', :user_id, :now, :now)
                    ON CONFLICT (org_id, user_id) DO NOTHING
                    """
                ),
                {"org_id": str(org_id), "user_id": str(user_id), "now": now},
            )
            session.commit()
            audit_rbac_event(
                action="rbac.org.bootstrap",
                actor=str(user_id),
                org_id=org_id,
                target_id=str(user_id),
                extra={"name": name},
            )
            return OrgRecord(
                id=org_id,
                name=name,
                slug=slug,
                status="active",
                default_role="viewer",
                metadata={},
                created_at=now,
                updated_at=now,
            )
        except SQLAlchemyError as exc:
            session.rollback()
            logger.exception("Failed to bootstrap personal org for user=%s", user_id)
            raise RbacServiceError("Failed to bootstrap personal org.") from exc
        finally:
            session.close()

    def upsert_membership(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
        status: str = DEFAULT_STATUS,
        invited_by: Optional[uuid.UUID] = None,
        metadata: Optional[Mapping[str, object]] = None,
    ) -> MembershipRecord:
        normalized_role = _normalize_role(role)
        normalized_status = _normalize_status(status)
        payload = {
            "org_id": str(org_id),
            "user_id": str(user_id),
            "role_key": normalized_role,
            "status": normalized_status,
            "invited_by": str(invited_by) if invited_by else None,
            "metadata": json.dumps(metadata or {}),
            "now": datetime.now(timezone.utc),
            "accepted_at": datetime.now(timezone.utc) if normalized_status == "active" else None,
        }
        session = self._session_factory()
        try:
            row = (
                session.execute(
                    text(
                        """
                        INSERT INTO user_orgs (org_id, user_id, role_key, status, invited_by, invited_at, accepted_at, metadata)
                        VALUES (:org_id, :user_id, :role_key, :status, :invited_by, :now, :accepted_at, CAST(:metadata AS JSONB))
                        ON CONFLICT (org_id, user_id) DO UPDATE SET
                            role_key = EXCLUDED.role_key,
                            status = EXCLUDED.status,
                            invited_by = COALESCE(EXCLUDED.invited_by, user_orgs.invited_by),
                            invited_at = COALESCE(user_orgs.invited_at, EXCLUDED.invited_at),
                            accepted_at = CASE
                                WHEN EXCLUDED.status = 'active' THEN COALESCE(user_orgs.accepted_at, EXCLUDED.accepted_at)
                                ELSE user_orgs.accepted_at
                            END,
                            metadata = COALESCE(EXCLUDED.metadata, user_orgs.metadata),
                            updated_at = NOW()
                        RETURNING org_id, user_id, role_key, status, invited_by, invited_at, accepted_at, created_at, updated_at
                        """
                    ),
                    payload,
                )
                .mappings()
                .first()
            )
            session.commit()
            if not row:
                raise RbacServiceError("Membership upsert returned no row.")
            membership = MembershipRecord(
                org_id=row["org_id"],
                user_id=row["user_id"],
                role=row["role_key"],
                status=row["status"],
                invited_by=row.get("invited_by"),
                invited_at=row.get("invited_at"),
                accepted_at=row.get("accepted_at"),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            audit_rbac_event(
                action="rbac.membership.upsert",
                actor=str(invited_by) if invited_by else None,
                org_id=org_id,
                target_id=str(user_id),
                extra={"role": normalized_role, "status": normalized_status},
            )
            return membership
        except IntegrityError as exc:
            session.rollback()
            raise RbacServiceError("Invalid organisation or user reference.") from exc
        except SQLAlchemyError as exc:
            session.rollback()
            logger.exception("Failed to upsert membership org=%s user=%s", org_id, user_id)
            raise RbacServiceError("Failed to upsert membership.") from exc
        finally:
            session.close()

    def update_membership_fields(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        role: Optional[str] = None,
        status: Optional[str] = None,
        actor: Optional[uuid.UUID] = None,
    ) -> MembershipRecord:
        updates = []
        params = {"org_id": str(org_id), "user_id": str(user_id)}
        if role:
            normalized_role = _normalize_role(role)
            updates.append("role_key = :role_key")
            params["role_key"] = normalized_role
        if status:
            normalized_status = _normalize_status(status)
            updates.append("status = :status")
            params["status"] = normalized_status
            if normalized_status == "active":
                updates.append("accepted_at = COALESCE(accepted_at, NOW())")
        if not updates:
            membership = self.get_membership(org_id=org_id, user_id=user_id)
            if not membership:
                raise RbacServiceError("Membership not found.")
            return membership

        set_clause = ", ".join(updates + ["updated_at = NOW()"])
        session = self._session_factory()
        try:
            row = (
                session.execute(
                    text(
                        f"""
                        UPDATE user_orgs
                        SET {set_clause}
                        WHERE org_id = :org_id AND user_id = :user_id
                        RETURNING org_id, user_id, role_key, status, invited_by, invited_at, accepted_at, created_at, updated_at
                        """
                    ),
                    params,
                )
                .mappings()
                .first()
            )
            session.commit()
            if not row:
                raise RbacServiceError("Membership not found.")
            membership = MembershipRecord(
                org_id=row["org_id"],
                user_id=row["user_id"],
                role=row["role_key"],
                status=row["status"],
                invited_by=row.get("invited_by"),
                invited_at=row.get("invited_at"),
                accepted_at=row.get("accepted_at"),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            audit_rbac_event(
                action="rbac.membership.update",
                actor=str(actor) if actor else None,
                org_id=org_id,
                target_id=str(user_id),
                extra={
                    "role": membership.role,
                    "status": membership.status,
                },
            )
            return membership
        except SQLAlchemyError as exc:
            session.rollback()
            logger.exception("Failed to update membership org=%s user=%s", org_id, user_id)
            raise RbacServiceError("Failed to update membership.") from exc
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Evaluation helpers
    # ------------------------------------------------------------------

    def evaluate(
        self,
        *,
        org_id: Optional[uuid.UUID],
        user_id: Optional[uuid.UUID],
        required_role: Optional[str] = None,
    ) -> MembershipDecision:
        if not org_id or not user_id:
            return MembershipDecision(
                allowed=False,
                role=None,
                status=None,
                membership=None,
                reason="missing_org_or_user",
            )
        membership = self.get_membership(org_id=org_id, user_id=user_id)
        if not membership:
            return MembershipDecision(
                allowed=False,
                role=None,
                status=None,
                membership=None,
                reason="membership_not_found",
            )
        effective_role = membership.role
        role_sufficient = True
        if required_role:
            required = _role_rank(_normalize_role(required_role))
            role_sufficient = _role_rank(effective_role) >= required
        status_ok = membership.status == "active"
        allowed = role_sufficient and status_ok
        reason = None
        if not status_ok:
            reason = "membership_inactive"
        elif not role_sufficient:
            reason = "role_insufficient"
        return MembershipDecision(
            allowed=allowed,
            role=effective_role,
            status=membership.status,
            membership=membership,
            reason=reason,
        )


rbac_service = RbacService()

__all__ = [
    "DEFAULT_ROLE",
    "DEFAULT_STATUS",
    "MembershipDecision",
    "MembershipRecord",
    "OrgRecord",
    "RbacService",
    "RbacServiceError",
    "RBAC_ENFORCE_DEFAULT",
    "ROLE_ORDER",
    "VALID_STATUSES",
    "rbac_service",
]
