"""SCIM v2 router for enterprise SSO provisioning."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from core.env import env_str
from database import get_db
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
_SCIM_BEARER_TOKEN = env_str("SCIM_BEARER_TOKEN")


def _require_scim_token(request: Request) -> None:
    if not _SCIM_BEARER_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"detail": "SCIM provisioning is disabled."},
        )
    header = request.headers.get("authorization")
    if not header or not header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Bearer token required."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = header.split(" ", 1)[1].strip()
    if token != _SCIM_BEARER_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Invalid SCIM token."},
        )


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
    _require_scim_token(request)
    try:
        result = list_scim_users(db, start_index=startIndex, count=count)
    except ScimError as exc:
        _scim_error_response(exc)
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
    _require_scim_token(request)
    try:
        return create_scim_user(db, payload)
    except ScimError as exc:
        _scim_error_response(exc)


@router.get("/Users/{user_id}")
def get_user(
    user_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _require_scim_token(request)
    try:
        return get_scim_user(db, user_id)
    except ScimError as exc:
        _scim_error_response(exc)


@router.patch("/Users/{user_id}")
def patch_user(
    user_id: uuid.UUID,
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _require_scim_token(request)
    try:
        return patch_scim_user(db, user_id, payload)
    except ScimError as exc:
        _scim_error_response(exc)


@router.delete("/Users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    _require_scim_token(request)
    try:
        delete_scim_user(db, user_id)
    except ScimError as exc:
        _scim_error_response(exc)


@router.get("/Groups")
def list_groups(
    request: Request,
    startIndex: int = 1,
    count: int = 50,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _require_scim_token(request)
    try:
        result = list_scim_groups(db, start_index=startIndex, count=count)
    except ScimError as exc:
        _scim_error_response(exc)
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
    _require_scim_token(request)
    try:
        return create_scim_group(db, payload)
    except ScimError as exc:
        _scim_error_response(exc)


@router.get("/Groups/{group_id}")
def get_group(
    group_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _require_scim_token(request)
    try:
        return get_scim_group(db, group_id)
    except ScimError as exc:
        _scim_error_response(exc)


@router.patch("/Groups/{group_id}")
def patch_group(
    group_id: uuid.UUID,
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _require_scim_token(request)
    try:
        return patch_scim_group(db, group_id, payload)
    except ScimError as exc:
        _scim_error_response(exc)


__all__ = ["router"]
