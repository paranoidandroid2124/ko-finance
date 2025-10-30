import os
import sys
import types
from typing import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from database import Base

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
def engine() -> Generator[Engine, None, None]:
    database_url = _resolve_test_database_url()
    engine = create_engine(database_url)
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def db_session(engine: Engine) -> Generator[Session, None, None]:
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
