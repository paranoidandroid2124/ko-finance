import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv

load_dotenv()

TEST_DATABASE_URL: Optional[str] = os.getenv("TEST_DATABASE_URL")
DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL") or TEST_DATABASE_URL
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL 또는 TEST_DATABASE_URL 환경 변수가 설정되어 있어야 합니다.")

ALLOW_NON_POSTGRES = os.getenv("DATABASE_ALLOW_NON_POSTGRES", "0") == "1"
IS_POSTGRES = DATABASE_URL.lower().startswith("postgresql")
if not IS_POSTGRES and not ALLOW_NON_POSTGRES:
    raise RuntimeError(f"DATABASE_URL은 PostgreSQL DSN이어야 합니다. 현재 값: {DATABASE_URL}")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args)
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
