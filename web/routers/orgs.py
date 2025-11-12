"""Organisation + membership management endpoints (Light RBAC)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from schemas.api.orgs import (
    OrgMemberResponse,
    OrgMemberUpdateRequest,
    OrgMemberUpsertRequest,
    OrgMembershipListResponse,
)
from services.rbac_service import MembershipRecord, RbacServiceError, rbac_service
from web.deps_rbac import RbacState, get_rbac_state, require_org_role

router = APIRouter(prefix="/orgs", tags=["Organisations"])


def _serialize_membership(record: MembershipRecord) -> OrgMemberResponse:
    return OrgMemberResponse(
        orgId=record.org_id,
        userId=record.user_id,
        role=record.role,
        status=record.status,
        invitedBy=record.invited_by,
        invitedAt=record.invited_at,
        acceptedAt=record.accepted_at,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
    )


@router.get(
    "/me/memberships",
    response_model=OrgMembershipListResponse,
    summary="List memberships for the current user.",
)
def list_memberships(state: RbacState = Depends(get_rbac_state)) -> OrgMembershipListResponse:
    if not state.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "rbac.user_required", "message": "X-User-Id header is required."},
        )
    records = rbac_service.list_memberships(user_id=state.user_id)
    return OrgMembershipListResponse(memberships=[_serialize_membership(record) for record in records])


def _ensure_same_org(requested_org: uuid.UUID, state: RbacState) -> None:
    if state.org_id and state.org_id != requested_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "rbac.org_mismatch",
                "message": "X-Org-Id header must match the org_id in the path.",
            },
        )


@router.post(
    "/{org_id}/members",
    response_model=OrgMemberResponse,
    summary="Invite or upsert a membership (admin only).",
)
def upsert_member(
    org_id: uuid.UUID,
    payload: OrgMemberUpsertRequest,
    state: RbacState = Depends(require_org_role("admin", enforce=True)),
) -> OrgMemberResponse:
    _ensure_same_org(org_id, state)
    try:
        record = rbac_service.upsert_membership(
            org_id=org_id,
            user_id=payload.userId,
            role=payload.role,
            status=payload.status,
            invited_by=state.user_id,
        )
    except RbacServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "rbac.membership_upsert_failed", "message": str(exc)},
        ) from exc
    return _serialize_membership(record)


@router.patch(
    "/{org_id}/members/{user_id}",
    response_model=OrgMemberResponse,
    summary="Update membership role/status (admin only).",
)
def patch_member(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: OrgMemberUpdateRequest,
    state: RbacState = Depends(require_org_role("admin", enforce=True)),
) -> OrgMemberResponse:
    _ensure_same_org(org_id, state)
    update_kwargs = {}
    if payload.role is not None:
        update_kwargs["role"] = payload.role
    if payload.status is not None:
        update_kwargs["status"] = payload.status
    if not update_kwargs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "rbac.no_changes", "message": "At least one field (role/status) must be provided."},
        )
    try:
        record = rbac_service.update_membership_fields(
            org_id=org_id,
            user_id=user_id,
            actor=state.user_id,
            **update_kwargs,
        )
    except RbacServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "rbac.membership_update_failed", "message": str(exc)},
        ) from exc
    return _serialize_membership(record)


__all__ = ["router"]
