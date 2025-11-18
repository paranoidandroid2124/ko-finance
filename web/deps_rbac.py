"""FastAPI dependencies for Light RBAC enforcement."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request, status

from services.audit_log import audit_rbac_event
from services.rbac_service import (
    MembershipRecord,
    RBAC_ENFORCE_DEFAULT,
    ROLE_ORDER,
    rbac_service,
)
from services.web_utils import parse_uuid

USER_HEADER = "x-user-id"
ORG_HEADER = "x-org-id"


@dataclass(frozen=True)
class RbacState:
    user_id: Optional[uuid.UUID]
    org_id: Optional[uuid.UUID]
    membership: Optional[MembershipRecord]
    issue: Optional[str]
    enforce_default: bool

    @property
    def role(self) -> Optional[str]:
        return self.membership.role if self.membership else None

    @property
    def status(self) -> Optional[str]:
        return self.membership.status if self.membership else None


def _parse_uuid_header(value: Optional[str]) -> Optional[uuid.UUID]:
    if not value:
        return None
    try:
        return parse_uuid(value)
    except HTTPException:
        return None


def _http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def resolve_rbac_state(request: Request) -> RbacState:
    cached = getattr(request.state, "rbac_state", None)
    if isinstance(cached, RbacState):
        return cached

    user_id = _parse_uuid_header(request.headers.get(USER_HEADER))
    org_id = _parse_uuid_header(request.headers.get(ORG_HEADER))
    membership: Optional[MembershipRecord] = None
    issue: Optional[str] = None

    if org_id and user_id:
        membership = rbac_service.get_membership(org_id=org_id, user_id=user_id)
        if not membership:
            issue = "membership_not_found"
        elif membership.status != "active":
            issue = "membership_inactive"
    elif org_id and not user_id:
        issue = "user_missing"

    state = RbacState(
        user_id=user_id,
        org_id=org_id,
        membership=membership,
        issue=issue,
        enforce_default=RBAC_ENFORCE_DEFAULT,
    )
    if issue and not getattr(request.state, "_rbac_issue_logged", False):
        audit_rbac_event(
            action="rbac.shadow.issue",
            actor=str(user_id) if user_id else None,
            org_id=org_id,
            target_id=str(user_id) if user_id else None,
            extra={
                "reason": issue,
                "path": request.url.path,
                "method": request.method,
            },
        )
        request.state._rbac_issue_logged = True

    request.state.rbac_state = state
    return state


def get_rbac_state(request: Request) -> RbacState:
    """Dependency wrapper that returns the request RBAC context."""

    return resolve_rbac_state(request)


def require_org_role(min_role: str, *, enforce: Optional[bool] = None):
    """Ensure the current membership meets the ``min_role`` threshold."""

    normalized = (min_role or "").strip().lower()
    if normalized not in ROLE_ORDER:
        raise ValueError(f"Unknown role '{min_role}'. Expected one of {', '.join(sorted(ROLE_ORDER))}.")
    required_rank = ROLE_ORDER[normalized]

    def _dependency(request: Request, state: RbacState = Depends(get_rbac_state)) -> RbacState:
        effective_enforce = RBAC_ENFORCE_DEFAULT if enforce is None else enforce

        if state.org_id is None:
            if effective_enforce:
                raise _http_error(
                    status.HTTP_400_BAD_REQUEST,
                    "rbac.org_required",
                    f"X-Org-Id header is required for endpoints protected by {normalized} role.",
                )
            return state

        if state.user_id is None:
            if effective_enforce:
                raise _http_error(
                    status.HTTP_401_UNAUTHORIZED,
                    "rbac.user_required",
                    f"{USER_HEADER} header is missing or invalid.",
                )
            return state

        membership = state.membership
        if membership is None:
            if effective_enforce:
                raise _http_error(
                    status.HTTP_403_FORBIDDEN,
                    "rbac.membership_required",
                    "User is not a member of the requested organisation.",
                )
            audit_rbac_event(
                action="rbac.shadow.membership_missing",
                actor=str(state.user_id),
                org_id=state.org_id,
                target_id=str(state.user_id),
                extra={"path": request.url.path if request else None},
            )
            return state

        if membership.status != "active":
            if effective_enforce:
                raise _http_error(
                    status.HTTP_403_FORBIDDEN,
                    "rbac.membership_inactive",
                    "Membership is not active for this operation.",
                )
            audit_rbac_event(
                action="rbac.shadow.membership_inactive",
                actor=str(state.user_id),
                org_id=state.org_id,
                target_id=str(state.user_id),
                extra={"status": membership.status},
            )
            return state

        current_rank = ROLE_ORDER.get(membership.role, -1)
        if current_rank < required_rank:
            if effective_enforce:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "rbac.role_insufficient",
                        "message": f"{normalized} role required.",
                        "requiredRole": normalized,
                        "currentRole": membership.role,
                    },
                )
            audit_rbac_event(
                action="rbac.shadow.role_insufficient",
                actor=str(state.user_id),
                org_id=state.org_id,
                target_id=str(state.user_id),
                extra={"required": normalized, "current": membership.role},
            )
        return state

    return _dependency


__all__ = [
    "RbacState",
    "get_rbac_state",
    "require_org_role",
    "resolve_rbac_state",
    "USER_HEADER",
    "ORG_HEADER",
]
