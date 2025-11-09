"""Dependencies shared by /ops (internal) routers."""

from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException, status

from core.env import env_str

OPS_ACCESS_TOKEN = env_str("OPS_ACCESS_TOKEN")


def require_ops_access(x_ops_token: Optional[str] = Header(default=None)) -> None:
    """Ensure the caller provided the configured ops access token."""

    if not OPS_ACCESS_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "ops.disabled", "message": "Ops access token is not configured."},
        )
    if x_ops_token != OPS_ACCESS_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ops.unauthorized", "message": "Ops access denied."},
        )
