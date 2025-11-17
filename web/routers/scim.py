"""SCIM v2 router for enterprise SSO provisioning."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from services import sso_provider_service
from services.sso_metrics import record_scim_request
from services.scim_service import (
    SCIM_ERROR_SCHEMA,
    SCIM_LIST_RESPONSE,
    ScimError,
    list_scim_groups,
    list_scim_users,
    get_scim_group,
    get_scim_user,
    create_scim_group,
    create_scim_user,
    patch_scim_group,
    patch_scim_user,
    delete_scim_user,
)

router = APIRouter(prefix="/scim/v2", tags=["SCIM"])
_SCIM_DEFAULT_PROVIDER = "default"


def _extract_bearer_token(request: Request) -> str:
    header = request.headers.get("authorization")
    if not header or not header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Bearer token required."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    candidate = header.split(" ", 1)[1].strip()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Bearer token required."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return candidate


def _resolve_scim_provider(request: Request, db: Session) -> str:
    token = _extract_bearer_token(request)
    try:
        provider, _ = sso_provider_service.resolve_scim_token(db, token)
    except ValueError as exc:
        error_code = str(exc)
        if error_code == "token_revoked":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"detail": "SCIM token has been revoked."},
            ) from exc
        if error_code == "token_expired":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"detail": "SCIM token has expired."},
            ) from exc
        if error_code == "provider_unavailable":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"detail": "SCIM provider is unavailable."},
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Invalid SCIM token."},
        ) from exc
    slug = provider.slug or _SCIM_DEFAULT_PROVIDER
    request.state.scim_provider_slug = slug
    return slug


def _record_scim(provider_slug: str, resource: str, method: str, success: bool) -> None:
    try:
        record_scim_request(provider_slug, resource, method, success)
    except Exception:  # pragma: no cover - best effort
        pass


def _scim_error_response(exc: ScimError) -> None:
    payload: Dict[str, Any] = {
        "schemas": [SCIM_ERROR_SCHEMA],
        "detail": exc.detail,
        "status": exc.status_code,
    }
    if exc.scim_type:
        payload["scimType"] = exc.scim_type
    raise HTTPException(status_code=exc.status_code, detail=payload)


@router.get("/Users")
def list_users(
    request: Request,
    startIndex: int = 1,
    count: int = 50,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    provider_slug = _resolve_scim_provider(request, db)
    try:
        result = list_scim_users(db, start_index=startIndex, count=count)
    except ScimError as exc:
        _record_scim(provider_slug, "Users", "GET", False)
        _scim_error_response(exc)
    _record_scim(provider_slug, "Users", "GET", True)
    return {
        "schemas": [SCIM_LIST_RESPONSE],
        "totalResults": result.total,
        "startIndex": result.start_index,
        "itemsPerPage": len(result.resources),
        "Resources": result.resources,
    }


@router.post("/Users", status_code=status.HTTP_201_CREATED)
def create_user(
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    provider_slug = _resolve_scim_provider(request, db)
    try:
        result = create_scim_user(db, payload)
        _record_scim(provider_slug, "Users", "POST", True)
        return result
    except ScimError as exc:
        _record_scim(provider_slug, "Users", "POST", False)
        _scim_error_response(exc)


@router.get("/Users/{user_id}")
def get_user(
    user_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    provider_slug = _resolve_scim_provider(request, db)
    try:
        result = get_scim_user(db, user_id)
        _record_scim(provider_slug, "Users", "GET", True)
        return result
    except ScimError as exc:
        _record_scim(provider_slug, "Users", "GET", False)
        _scim_error_response(exc)


@router.patch("/Users/{user_id}")
def patch_user(
    user_id: uuid.UUID,
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    provider_slug = _resolve_scim_provider(request, db)
    try:
        result = patch_scim_user(db, user_id, payload)
        _record_scim(provider_slug, "Users", "PATCH", True)
        return result
    except ScimError as exc:
        _record_scim(provider_slug, "Users", "PATCH", False)
        _scim_error_response(exc)


@router.delete("/Users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    provider_slug = _resolve_scim_provider(request, db)
    try:
        delete_scim_user(db, user_id)
        _record_scim(provider_slug, "Users", "DELETE", True)
    except ScimError as exc:
        _record_scim(provider_slug, "Users", "DELETE", False)
        _scim_error_response(exc)


@router.get("/Groups")
def list_groups(
    request: Request,
    startIndex: int = 1,
    count: int = 50,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    provider_slug = _resolve_scim_provider(request, db)
    try:
        result = list_scim_groups(db, start_index=startIndex, count=count)
    except ScimError as exc:
        _record_scim(provider_slug, "Groups", "GET", False)
        _scim_error_response(exc)
    _record_scim(provider_slug, "Groups", "GET", True)
    return {
        "schemas": [SCIM_LIST_RESPONSE],
        "totalResults": result.total,
        "startIndex": result.start_index,
        "itemsPerPage": len(result.resources),
        "Resources": result.resources,
    }


@router.post("/Groups", status_code=status.HTTP_201_CREATED)
def create_group(
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    provider_slug = _resolve_scim_provider(request, db)
    try:
        result = create_scim_group(db, payload)
        _record_scim(provider_slug, "Groups", "POST", True)
        return result
    except ScimError as exc:
        _record_scim(provider_slug, "Groups", "POST", False)
        _scim_error_response(exc)


@router.get("/Groups/{group_id}")
def get_group(
    group_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    provider_slug = _resolve_scim_provider(request, db)
    try:
        result = get_scim_group(db, group_id)
        _record_scim(provider_slug, "Groups", "GET", True)
        return result
    except ScimError as exc:
        _record_scim(provider_slug, "Groups", "GET", False)
        _scim_error_response(exc)


@router.patch("/Groups/{group_id}")
def patch_group(
    group_id: uuid.UUID,
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    provider_slug = _resolve_scim_provider(request, db)
    try:
        result = patch_scim_group(db, group_id, payload)
        _record_scim(provider_slug, "Groups", "PATCH", True)
        return result
    except ScimError as exc:
        _record_scim(provider_slug, "Groups", "PATCH", False)
        _scim_error_response(exc)


__all__ = ["router"]
