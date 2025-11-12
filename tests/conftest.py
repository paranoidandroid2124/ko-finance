import os
import sys
import types
from typing import Generator, Optional

import pytest

try:
    from sqlalchemy import create_engine, event
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session, sessionmaker
except Exception as exc:  # pragma: no cover - SQLAlchemy optional during CI
    Engine = Session = sessionmaker = None  # type: ignore
    create_engine = None  # type: ignore
    _SQLALCHEMY_IMPORT_ERROR: Optional[Exception] = exc
else:
    _SQLALCHEMY_IMPORT_ERROR = None


# Stub PyMuPDF so tests importing parse modules don't require native dependency.
sys.modules.setdefault("fitz", types.SimpleNamespace())  # type: ignore


def _resolve_test_database_url() -> str:
    candidates = (
        os.getenv("TEST_DATABASE_URL"),
        os.getenv("DATABASE_URL"),
    )
    for candidate in candidates:
        if candidate:
            if not candidate.lower().startswith("postgresql"):
                raise RuntimeError(
                    f"테스트용 데이터베이스는 PostgreSQL 이어야 합니다. 현재 값: {candidate}"
                )
            return candidate
    raise RuntimeError(
        "TEST_DATABASE_URL 또는 DATABASE_URL 환경 변수를 PostgreSQL DSN으로 설정해 주세요."
    )


@pytest.fixture(scope="session")
def engine() -> Generator["Engine", None, None]:
    if _SQLALCHEMY_IMPORT_ERROR or create_engine is None:
        pytest.skip(f"SQLAlchemy is unavailable: {_SQLALCHEMY_IMPORT_ERROR}")
    try:
        from database import Base  # type: ignore
    except Exception as exc:
        pytest.skip(f"Database metadata unavailable: {exc}")
    database_url = _resolve_test_database_url()
    engine = create_engine(database_url)
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def db_session(engine: "Engine") -> Generator["Session", None, None]:
    if _SQLALCHEMY_IMPORT_ERROR:
        pytest.skip(f"SQLAlchemy is unavailable: {_SQLALCHEMY_IMPORT_ERROR}")
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, autoflush=False, expire_on_commit=False)
    session = SessionLocal()
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans) -> None:  # pragma: no cover - SQLAlchemy callback
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
