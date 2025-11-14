"""Health-related API endpoints."""

from __future__ import annotations

from typing import Optional, Tuple

from fastapi import APIRouter
from sqlalchemy.exc import SQLAlchemyError

from database import SessionLocal
from services.memory.health import lightmem_health_summary

router = APIRouter(prefix="/health", tags=["Health"])


def ping_database() -> Tuple[bool, Optional[str]]:
    """Return database connectivity status and optional error message."""
    db = SessionLocal()
    try:
        db.execute("SELECT 1")
        return True, None
    except SQLAlchemyError as exc:
        return False, str(exc)
    finally:
        db.close()


@router.get(
    "/status",
    summary="Service runtime status",
    description="Aggregated service health information used by Cloud Run/Monitoring probes.",
)
def read_service_status():
    db_ok, db_error = ping_database()
    status = "ok" if db_ok else "degraded"
    payload = {"status": status, "database": {"ok": db_ok}}
    if db_error:
        payload["database"]["error"] = db_error
    return payload


@router.get(
    "/lightmem",
    summary="Check LightMem dependencies",
    description="Runs connectivity checks against the LightMem session (Redis) and long-term (Qdrant) stores.",
)
def read_lightmem_health():
    return lightmem_health_summary()


__all__ = ["router", "ping_database"]
