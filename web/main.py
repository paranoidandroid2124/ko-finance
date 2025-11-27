    return await auth_context_middleware(request, call_next)


@app.middleware("http")
async def inject_plan_context(request: Request, call_next):
    """Ensure plan context is available on each request via request.state."""
    context = resolve_plan_context(request.headers)
    request.state.plan_context = context
    response = await call_next(request)
    response.headers.setdefault("X-Plan-Tier", context.tier)
    return response


@app.middleware("http")
async def apply_rbac_context(request: Request, call_next):
    """Hydrate RBAC context + enforce global guardrails."""
    return await rbac_context_middleware(request, call_next)


@app.middleware("http")
async def track_sensitive_requests(request: Request, call_next):
    """Record audit trails for privileged or export endpoints."""
    return await audit_trail_middleware(request, call_next)


@app.get("/", summary="Health Check", tags=["Default"])
def health_check():
    """API 상태를 확인하는 헬스 체크 엔드포인트입니다."""
    return {"status": "ok", "message": "Nuvien AI Research Copilot API is running."}


@app.get("/healthz", include_in_schema=False)
def cloud_run_health_check():
    """Lightweight Cloud Run friendly health probe."""
    db_ok, db_error = routers.health.ping_database()
    payload = {"status": "ok" if db_ok else "unhealthy", "database": {"ok": db_ok}}
    if db_error:
        payload["database"]["error"] = db_error
    status_code = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=payload)


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics():
    """Expose Prometheus metrics for Cloud Monitoring."""
    if generate_latest is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "metrics.unavailable", "message": "prometheus_client is not installed"},
        )
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(routers.chat.router, prefix="/api/v1")
app.include_router(routers.rag.router, prefix="/api/v1")
app.include_router(routers.search.router, prefix="/api/v1")
app.include_router(routers.company.router, prefix="/api/v1")
app.include_router(routers.evidence.router, prefix="/api/v1")
app.include_router(routers.payments.router, prefix="/api/v1")
app.include_router(routers.plan.router, prefix="/api/v1")
app.include_router(routers.report.router, prefix="/api/v1")
app.include_router(routers.auth.router, prefix="/api/v1")
app.include_router(routers.user_settings.router, prefix="/api/v1")
app.include_router(routers.health.router, prefix="/api/v1")
app.include_router(routers.account.router, prefix="/api/v1")
app.include_router(routers.tools.router, prefix="/api/v1")
app.include_router(routers.tools_text.router, prefix="/api/v1")
app.include_router(routers.recommendations.router, prefix="/api/v1")
app.include_router(routers.profile.router, prefix="/api/v1")
