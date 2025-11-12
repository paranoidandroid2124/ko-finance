from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from services.plan_service import resolve_plan_context
from web import routers
from web.background.rag_auto_retry import start_retry_scheduler

app = FastAPI(
    title="K-Finance Admin API",
    description="Operations-only FastAPI surface for the admin console.",
    version="0.1.0",
)

origins = [
    "http://localhost:3000",
    "http://localhost:3100",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def inject_plan_context(request: Request, call_next):
    """Ensure plan context is available on each request via request.state."""
    context = resolve_plan_context(request)
    request.state.plan_context = context
    response = await call_next(request)
    response.headers.setdefault("X-Plan-Tier", context.tier)
    return response


@app.get("/", summary="Health Check", tags=["Default"])
def health_check():
    """운영 세션 기본 상태를 확인하는 헬스 체크."""
    return {"status": "ok", "message": "K-Finance Admin API is running."}


app.include_router(routers.admin.router, prefix="/api/v1")
app.include_router(routers.admin_llm.router, prefix="/api/v1")
app.include_router(routers.admin_rag.router, prefix="/api/v1")
app.include_router(routers.admin_ops.router, prefix="/api/v1")
app.include_router(routers.admin_ui.router, prefix="/api/v1")


@app.on_event("startup")
async def launch_admin_background_jobs() -> None:
    """Kick off background schedulers used by the admin console."""
    start_retry_scheduler()
