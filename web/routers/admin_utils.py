"""Shared helpers for constructing admin routers with consistent guards."""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

from fastapi import APIRouter, Depends

from web.deps_admin import require_admin_session


def create_admin_router(
    *,
    prefix: str,
    tags: Optional[Sequence[str]] = None,
) -> APIRouter:
    """Create an APIRouter with the admin session guard pre-configured."""

    tag_list: Iterable[str]
    if tags:
        tag_list = tags
    else:
        tag_list = ["Admin"]
    return APIRouter(prefix=prefix, tags=list(tag_list), dependencies=[Depends(require_admin_session)])


__all__ = ["create_admin_router"]
