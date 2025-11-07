from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from services.plan_service import resolve_plan_context
from web import routers
from web.background.rag_auto_retry import start_retry_scheduler

app = FastAPI(
    title="K-Finance AI Research Copilot",
    description="SSoT-aligned filings, news, and RAG backend API",
    version="0.1.0",
)

origins = [
    "http://localhost:3000",
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
    """API 상태를 확인하는 헬스 체크 엔드포인트입니다."""
    return {"status": "ok", "message": "K-Finance AI Research Copilot API is running."}


app.include_router(routers.dashboard.router, prefix="/api/v1")
app.include_router(routers.alerts.router, prefix="/api/v1")
app.include_router(routers.news.router, prefix="/api/v1")
app.include_router(routers.chat.router, prefix="/api/v1")
app.include_router(routers.rag.router, prefix="/api/v1")
app.include_router(routers.search.router, prefix="/api/v1")
app.include_router(routers.sectors.router, prefix="/api/v1")
app.include_router(routers.company.router, prefix="/api/v1")
app.include_router(routers.payments.router, prefix="/api/v1")
app.include_router(routers.plan.router, prefix="/api/v1")
app.include_router(routers.reports.router, prefix="/api/v1")
app.include_router(routers.admin.router, prefix="/api/v1")
app.include_router(routers.admin_llm.router, prefix="/api/v1")
app.include_router(routers.admin_rag.router, prefix="/api/v1")
app.include_router(routers.admin_ops.router, prefix="/api/v1")
app.include_router(routers.admin_ui.router, prefix="/api/v1")

if getattr(routers, "filing", None):
    app.include_router(routers.filing.router, prefix="/api/v1")


@app.on_event("startup")
async def launch_background_jobs() -> None:
    """Kick off background schedulers used by the admin console."""
    start_retry_scheduler()
