from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from services.plan_service import resolve_plan_context
from web import routers
from web.middleware.rbac import rbac_context_middleware

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


@app.middleware("http")
async def apply_rbac_context(request: Request, call_next):
    """Hydrate RBAC context + enforce global guardrails."""
    return await rbac_context_middleware(request, call_next)


@app.get("/", summary="Health Check", tags=["Default"])
def health_check():
    """API 상태를 확인하는 헬스 체크 엔드포인트입니다."""
    return {"status": "ok", "message": "K-Finance AI Research Copilot API is running."}


app.include_router(routers.dashboard.router, prefix="/api/v1")
app.include_router(routers.public.router, prefix="/api/v1")
app.include_router(routers.alerts.router, prefix="/api/v1")
app.include_router(routers.news.router, prefix="/api/v1")
app.include_router(routers.chat.router, prefix="/api/v1")
app.include_router(routers.rag.router, prefix="/api/v1")
app.include_router(routers.search.router, prefix="/api/v1")
app.include_router(routers.sectors.router, prefix="/api/v1")
app.include_router(routers.company.router, prefix="/api/v1")
app.include_router(routers.event_study.router, prefix="/api/v1")
app.include_router(routers.payments.router, prefix="/api/v1")
app.include_router(routers.plan.router, prefix="/api/v1")
app.include_router(routers.orgs.router, prefix="/api/v1")
app.include_router(routers.table_explorer.router, prefix="/api/v1")
app.include_router(routers.auth.router, prefix="/api/v1")
app.include_router(routers.user_settings.router, prefix="/api/v1")
app.include_router(routers.campaign.router, prefix="/api/v1")
app.include_router(routers.analytics.router, prefix="/api/v1")
app.include_router(routers.reports.router, prefix="/api/v1")
app.include_router(routers.health.router, prefix="/api/v1")
app.include_router(routers.ops.router, prefix="/ops/api")
app.include_router(routers.scim.router)
app.include_router(routers.notebooks.router, prefix="/api/v1")

if getattr(routers, "filing", None):
    app.include_router(routers.filing.router, prefix="/api/v1")
