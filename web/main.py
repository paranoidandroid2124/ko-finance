from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web.routers import dashboard, filing, news, rag

app = FastAPI(
    title="K-Finance AI Research Copilot",
    description="SSoT 사양에 맞춘 공시·뉴스·RAG 백엔드 API",
    version="0.1.0",
)

# 프런트엔드 개발 환경 접근을 허용하는 CORS 설정
origins = [
    "http://localhost:3000",  # React 개발 서버
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
    """API 동작 여부를 확인하기 위한 헬스 체크 엔드포인트."""
    return {"status": "ok", "message": "K-Finance AI Research Copilot API is running."}


# API v1 라우터 등록
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(filing.router, prefix="/api/v1")
app.include_router(news.router, prefix="/api/v1")
app.include_router(rag.router, prefix="/api/v1")

