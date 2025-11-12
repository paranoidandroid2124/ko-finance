"""Health-related API endpoints."""

from fastapi import APIRouter

from services.memory.health import lightmem_health_summary

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "/lightmem",
    summary="Check LightMem dependencies",
    description="Runs connectivity checks against the LightMem session (Redis) and long-term (Qdrant) stores.",
)
def read_lightmem_health():
    return lightmem_health_summary()


__all__ = ["router"]
