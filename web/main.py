from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web import routers

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


@app.get("/", summary="Health Check", tags=["Default"])
def health_check():
    """API 상태를 확인하는 헬스 체크 엔드포인트입니다."""
    return {"status": "ok", "message": "K-Finance AI Research Copilot API is running."}


app.include_router(routers.dashboard.router, prefix="/api/v1")
app.include_router(routers.news.router, prefix="/api/v1")
app.include_router(routers.chat.router, prefix="/api/v1")
app.include_router(routers.rag.router, prefix="/api/v1")

if getattr(routers, "filing", None):
    app.include_router(routers.filing.router, prefix="/api/v1")

