import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL 환경 변수가 설정되어 있어야 합니다.")
if not DATABASE_URL.lower().startswith("postgresql"):
    raise RuntimeError(f"DATABASE_URL은 PostgreSQL DSN이어야 합니다. 현재 값: {DATABASE_URL}")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


def get_db():
    """FastAPI 의존성 주입용 세션 생성기."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
