"""FastAPI router for Research Notebook CRUD, entries, and share links."""

from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.api.notebooks import (
    NotebookCreateRequest,
    NotebookDetailResponse,
    NotebookEntryCreateRequest,
    NotebookEntryResponse,
    NotebookEntryUpdateRequest,
    NotebookListFilters,
    NotebookListResponse,
    NotebookShareAccessRequest,
    NotebookShareAccessResponse,
    NotebookShareCreateRequest,
    NotebookShareListResponse,
    NotebookShareResponse,
    NotebookSummary,
    NotebookUpdateRequest,
)
from services import notebook_service
from services.audit_log import audit_collab_event
from services.notebook_service import (
    NotebookEntryRecord,
    NotebookNotFoundError,
    NotebookRecord,
    NotebookServiceError,
    NotebookShareAccessError,
    NotebookShareRecord,
    NotebookShareView,
)
from services.plan_service import PlanContext
from web.deps import require_plan_feature
from web.deps_rbac import RbacState, get_rbac_state, require_org_role

router = APIRouter(prefix="/notebooks", tags=["Research Notebook"])
DEFAULT_LIMIT = 25
NOTEBOOK_ENTITLEMENT = "collab.notebook"


def _clean_query_list(values: Optional[List[str]]) -> List[str]:
    normalized: List[str] = []
    if not values:
        return normalized
    for raw in values:
        if not raw:
            continue
        for part in str(raw).split(","):
            trimmed = part.strip()
            if trimmed and trimmed not in normalized:
                normalized.append(trimmed)
    return normalized


def _require_org(state: RbacState) -> uuid.UUID:
    if state.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "notebook.org_required", "message": "X-Org-Id header is required for notebook access."},
        )
    return state.org_id


def _require_user(state: RbacState) -> uuid.UUID:
    if state.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "notebook.user_required", "message": "X-User-Id header is required for notebook actions."},
        )
    return state.user_id


def _serialize_notebook(record: NotebookRecord) -> NotebookSummary:
    return NotebookSummary(
        id=str(record.id),
        orgId=str(record.org_id),
        ownerId=str(record.owner_id),
        title=record.title,
        summary=record.summary,
        tags=list(record.tags or []),
        coverColor=record.cover_color,
        metadata=dict(record.metadata or {}),
        entryCount=record.entry_count,
        lastActivityAt=record.last_activity_at.isoformat() if record.last_activity_at else None,
        createdAt=record.created_at.isoformat(),
        updatedAt=record.updated_at.isoformat(),
    )


def _serialize_entry(record: NotebookEntryRecord) -> NotebookEntryResponse:
    return NotebookEntryResponse(
        id=str(record.id),
        notebookId=str(record.notebook_id),
        authorId=str(record.author_id),
        highlight=record.highlight,
        annotation=record.annotation,
        annotationFormat=record.annotation_format,
        tags=list(record.tags or []),
        source=record.source,
        isPinned=record.is_pinned,
        position=record.position,
        createdAt=record.created_at.isoformat(),
        updatedAt=record.updated_at.isoformat(),
    )


def _serialize_share(record: NotebookShareRecord) -> NotebookShareResponse:
    return NotebookShareResponse(
        id=str(record.id),
        notebookId=str(record.notebook_id),
        token=record.token,
        createdBy=str(record.created_by),
        accessScope=record.access_scope,
        expiresAt=record.expires_at.isoformat() if record.expires_at else None,
        passwordProtected=record.password_protected,
        passwordHint=record.password_hint,
        revokedAt=record.revoked_at.isoformat() if record.revoked_at else None,
        lastAccessedAt=record.last_accessed_at.isoformat() if record.last_accessed_at else None,
        createdAt=record.created_at.isoformat(),
    )


def _service_error(exc: NotebookServiceError) -> HTTPException:
    if isinstance(exc, NotebookNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "notebook.not_found", "message": str(exc)})
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "notebook.error", "message": str(exc)})


@router.get("", response_model=NotebookListResponse)
def list_notebooks(
    query: Optional[str] = Query(default=None, description="Full-text search across title/summary."),
    tags: Optional[List[str]] = Query(default=None, description="Filter by tags."),
    limit: Optional[int] = Query(default=DEFAULT_LIMIT, ge=1, le=100),
    state: RbacState = Depends(require_org_role("viewer")),
    session: Session = Depends(get_db),
    _: PlanContext = Depends(require_plan_feature(NOTEBOOK_ENTITLEMENT)),
) -> NotebookListResponse:
    org_id = _require_org(state)
    tag_filter = _clean_query_list(tags)
    records = notebook_service.list_notebooks(
        session,
        org_id=org_id,
        query=query,
        tags=tag_filter,
        limit=limit,
    )
    filters = NotebookListFilters(tags=tag_filter, query=query, limit=limit or DEFAULT_LIMIT)
    return NotebookListResponse(items=[_serialize_notebook(record) for record in records], filters=filters)


@router.get("/{notebook_id}", response_model=NotebookDetailResponse)
def get_notebook_detail(
    notebook_id: uuid.UUID,
    entry_tags: Optional[List[str]] = Query(default=None, alias="entryTags"),
    state: RbacState = Depends(require_org_role("viewer")),
    session: Session = Depends(get_db),
    _: PlanContext = Depends(require_plan_feature(NOTEBOOK_ENTITLEMENT)),
) -> NotebookDetailResponse:
    org_id = _require_org(state)
    try:
        notebook = notebook_service.get_notebook(session, notebook_id=notebook_id, org_id=org_id)
        entries = notebook_service.list_entries(
            session,
            notebook_id=notebook_id,
            org_id=org_id,
            tag_filter=_clean_query_list(entry_tags),
        )
    except NotebookServiceError as exc:
        raise _service_error(exc) from exc
    return NotebookDetailResponse(
        notebook=_serialize_notebook(notebook),
        entries=[_serialize_entry(entry) for entry in entries],
    )


@router.post("", response_model=NotebookDetailResponse, status_code=status.HTTP_201_CREATED)
def create_notebook(
    payload: NotebookCreateRequest,
    state: RbacState = Depends(require_org_role("editor")),
    session: Session = Depends(get_db),
    _: PlanContext = Depends(require_plan_feature(NOTEBOOK_ENTITLEMENT)),
) -> NotebookDetailResponse:
    org_id = _require_org(state)
    user_id = _require_user(state)
    try:
        notebook = notebook_service.create_notebook(
            session,
            org_id=org_id,
            owner_id=user_id,
            title=payload.title,
            summary=payload.summary,
            tags=payload.tags,
            cover_color=payload.coverColor,
            metadata=payload.metadata,
        )
    except NotebookServiceError as exc:
        raise _service_error(exc) from exc
    audit_collab_event(
        action="collab.notebook.create",
        user_id=user_id,
        org_id=org_id,
        target_id=str(notebook.id),
        extra={"title": notebook.title, "tags": notebook.tags},
    )
    return NotebookDetailResponse(notebook=_serialize_notebook(notebook), entries=[])


@router.put("/{notebook_id}", response_model=NotebookDetailResponse)
def update_notebook(
    notebook_id: uuid.UUID,
    payload: NotebookUpdateRequest,
    state: RbacState = Depends(require_org_role("editor")),
    session: Session = Depends(get_db),
    _: PlanContext = Depends(require_plan_feature(NOTEBOOK_ENTITLEMENT)),
) -> NotebookDetailResponse:
    org_id = _require_org(state)
    user_id = _require_user(state)
    try:
        notebook = notebook_service.update_notebook(
            session,
            notebook_id=notebook_id,
            org_id=org_id,
            title=payload.title,
            summary=payload.summary,
            tags=payload.tags,
            cover_color=payload.coverColor,
            metadata=payload.metadata,
        )
        entries = notebook_service.list_entries(session, notebook_id=notebook_id, org_id=org_id)
    except NotebookServiceError as exc:
        raise _service_error(exc) from exc
    audit_collab_event(
        action="collab.notebook.update",
        user_id=user_id,
        org_id=org_id,
        target_id=str(notebook_id),
        extra={"title": notebook.title},
    )
    return NotebookDetailResponse(
        notebook=_serialize_notebook(notebook),
        entries=[_serialize_entry(entry) for entry in entries],
    )


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notebook(
    notebook_id: uuid.UUID,
    state: RbacState = Depends(require_org_role("editor")),
    session: Session = Depends(get_db),
    _: PlanContext = Depends(require_plan_feature(NOTEBOOK_ENTITLEMENT)),
) -> Response:
    org_id = _require_org(state)
    user_id = _require_user(state)
    try:
        notebook_service.delete_notebook(session, notebook_id=notebook_id, org_id=org_id)
    except NotebookServiceError as exc:
        raise _service_error(exc) from exc
    audit_collab_event(
        action="collab.notebook.delete",
        user_id=user_id,
        org_id=org_id,
        target_id=str(notebook_id),
        extra=None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{notebook_id}/entries", response_model=NotebookEntryResponse, status_code=status.HTTP_201_CREATED)
def create_entry(
    notebook_id: uuid.UUID,
    payload: NotebookEntryCreateRequest,
    state: RbacState = Depends(require_org_role("editor")),
    session: Session = Depends(get_db),
    _: PlanContext = Depends(require_plan_feature(NOTEBOOK_ENTITLEMENT)),
) -> NotebookEntryResponse:
    org_id = _require_org(state)
    user_id = _require_user(state)
    try:
        entry = notebook_service.create_entry(
            session,
            notebook_id=notebook_id,
            org_id=org_id,
            author_id=user_id,
            highlight=payload.highlight,
            annotation=payload.annotation,
            tags=payload.tags,
            source=payload.source.model_dump(),
            is_pinned=payload.isPinned,
            position=payload.position,
            annotation_format=payload.annotationFormat or "markdown",
        )
    except NotebookServiceError as exc:
        raise _service_error(exc) from exc
    audit_collab_event(
        action="collab.notebook.entry.create",
        user_id=user_id,
        org_id=org_id,
        target_id=str(entry.id),
        extra={"notebookId": str(notebook_id)},
    )
    return _serialize_entry(entry)


@router.put("/{notebook_id}/entries/{entry_id}", response_model=NotebookEntryResponse)
def update_entry(
    notebook_id: uuid.UUID,
    entry_id: uuid.UUID,
    payload: NotebookEntryUpdateRequest,
    state: RbacState = Depends(require_org_role("editor")),
    session: Session = Depends(get_db),
    _: PlanContext = Depends(require_plan_feature(NOTEBOOK_ENTITLEMENT)),
) -> NotebookEntryResponse:
    org_id = _require_org(state)
    user_id = _require_user(state)
    try:
        entry = notebook_service.update_entry(
            session,
            notebook_id=notebook_id,
            org_id=org_id,
            entry_id=entry_id,
            highlight=payload.highlight,
            annotation=payload.annotation,
            tags=payload.tags,
            source=payload.source.model_dump() if payload.source else None,
            is_pinned=payload.isPinned,
            position=payload.position,
            annotation_format=payload.annotationFormat,
        )
    except NotebookServiceError as exc:
        raise _service_error(exc) from exc
    audit_collab_event(
        action="collab.notebook.entry.update",
        user_id=user_id,
        org_id=org_id,
        target_id=str(entry_id),
        extra={"notebookId": str(notebook_id)},
    )
    return _serialize_entry(entry)


@router.delete("/{notebook_id}/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    notebook_id: uuid.UUID,
    entry_id: uuid.UUID,
    state: RbacState = Depends(require_org_role("editor")),
    session: Session = Depends(get_db),
    _: PlanContext = Depends(require_plan_feature(NOTEBOOK_ENTITLEMENT)),
) -> Response:
    org_id = _require_org(state)
    user_id = _require_user(state)
    try:
        notebook_service.delete_entry(session, notebook_id=notebook_id, org_id=org_id, entry_id=entry_id)
    except NotebookServiceError as exc:
        raise _service_error(exc) from exc
    audit_collab_event(
        action="collab.notebook.entry.delete",
        user_id=user_id,
        org_id=org_id,
        target_id=str(entry_id),
        extra={"notebookId": str(notebook_id)},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{notebook_id}/shares", response_model=NotebookShareListResponse)
def list_shares(
    notebook_id: uuid.UUID,
    state: RbacState = Depends(require_org_role("editor")),
    session: Session = Depends(get_db),
    _: PlanContext = Depends(require_plan_feature(NOTEBOOK_ENTITLEMENT)),
) -> NotebookShareListResponse:
    org_id = _require_org(state)
    try:
        shares = notebook_service.list_shares(session, notebook_id=notebook_id, org_id=org_id)
    except NotebookServiceError as exc:
        raise _service_error(exc) from exc
    return NotebookShareListResponse(shares=[_serialize_share(share) for share in shares])


@router.post("/{notebook_id}/shares", response_model=NotebookShareResponse, status_code=status.HTTP_201_CREATED)
def create_share(
    notebook_id: uuid.UUID,
    payload: NotebookShareCreateRequest,
    state: RbacState = Depends(require_org_role("editor")),
    session: Session = Depends(get_db),
    _: PlanContext = Depends(require_plan_feature(NOTEBOOK_ENTITLEMENT)),
) -> NotebookShareResponse:
    org_id = _require_org(state)
    user_id = _require_user(state)
    try:
        share = notebook_service.create_share_link(
            session,
            notebook_id=notebook_id,
            org_id=org_id,
            created_by=user_id,
            expires_in_minutes=payload.expiresInMinutes,
            password=payload.password,
            password_hint=payload.passwordHint,
            access_scope=payload.accessScope or "view",
        )
    except NotebookServiceError as exc:
        raise _service_error(exc) from exc
    audit_collab_event(
        action="collab.notebook.share.create",
        user_id=user_id,
        org_id=org_id,
        target_id=str(share.id),
        extra={"notebookId": str(notebook_id)},
    )
    return _serialize_share(share)


@router.delete("/{notebook_id}/shares/{share_id}", response_model=NotebookShareResponse)
def revoke_share(
    notebook_id: uuid.UUID,
    share_id: uuid.UUID,
    state: RbacState = Depends(require_org_role("editor")),
    session: Session = Depends(get_db),
    _: PlanContext = Depends(require_plan_feature(NOTEBOOK_ENTITLEMENT)),
) -> NotebookShareResponse:
    org_id = _require_org(state)
    user_id = _require_user(state)
    try:
        share = notebook_service.revoke_share_link(session, notebook_id=notebook_id, org_id=org_id, share_id=share_id)
    except NotebookServiceError as exc:
        raise _service_error(exc) from exc
    audit_collab_event(
        action="collab.notebook.share.revoke",
        user_id=user_id,
        org_id=org_id,
        target_id=str(share_id),
        extra={"notebookId": str(notebook_id)},
    )
    return _serialize_share(share)


@router.post("/shares/access", response_model=NotebookShareAccessResponse, include_in_schema=False)
def resolve_share(
    payload: NotebookShareAccessRequest,
    session: Session = Depends(get_db),
) -> NotebookShareAccessResponse:
    try:
        view: NotebookShareView = notebook_service.resolve_share_token(
            session,
            token=payload.token,
            password=payload.password,
        )
    except NotebookShareAccessError as exc:
        code = str(exc)
        status_code = status.HTTP_400_BAD_REQUEST
        if code == "not_found":
            status_code = status.HTTP_404_NOT_FOUND
        elif code in {"revoked", "expired"}:
            status_code = status.HTTP_410_GONE
        raise HTTPException(status_code=status_code, detail={"code": f"notebook.share.{code}", "message": "Unable to open share link."}) from exc
    except NotebookServiceError as exc:
        raise _service_error(exc) from exc

    audit_collab_event(
        action="collab.notebook.share.access",
        user_id=None,
        org_id=view.notebook.org_id,
        target_id=str(view.share.id),
        extra={"status": "ok"},
    )
    return NotebookShareAccessResponse(
        notebook=_serialize_notebook(view.notebook),
        entries=[_serialize_entry(entry) for entry in view.entries],
        share=_serialize_share(view.share),
    )
