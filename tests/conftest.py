import os
import sys
import types
from typing import Generator, Optional, Tuple

import pytest
from sqlalchemy.exc import CompileError

os.environ.setdefault("DATABASE_ALLOW_NON_POSTGRES", "1")
os.environ.setdefault("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("DATABASE_URL", os.getenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"]))

try:
    from sqlalchemy import create_engine, event
    from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.ext.compiler import compiles
except Exception as exc:  # pragma: no cover
    Engine = Session = sessionmaker = None  # type: ignore
    create_engine = None  # type: ignore
    _SQLALCHEMY_IMPORT_ERROR: Optional[Exception] = exc
else:
    _SQLALCHEMY_IMPORT_ERROR = None

try:
    import database as database_module
    from database import Base, IS_POSTGRES
except Exception as exc:  # pragma: no cover
    database_module = None  # type: ignore
    Base = None  # type: ignore
    IS_POSTGRES = False
    _DATABASE_IMPORT_ERROR: Optional[Exception] = exc
else:
    _DATABASE_IMPORT_ERROR = None

# Provide lightweight fallbacks for PostgreSQL-only column types when using SQLite.
if not IS_POSTGRES and _SQLALCHEMY_IMPORT_ERROR is None and Base is not None:
    @compiles(JSONB, "sqlite")  # type: ignore[misc]
    def _compile_jsonb_sqlite(_element, _compiler, **_kw):  # pragma: no cover - sqlite compat
        return "TEXT"

    @compiles(UUID, "sqlite")  # type: ignore[misc]
    def _compile_uuid_sqlite(_element, _compiler, **_kw):  # pragma: no cover - sqlite compat
        return "TEXT"

    @compiles(ARRAY, "sqlite")  # type: ignore[misc]
    def _compile_array_sqlite(_element, _compiler, **_kw):  # pragma: no cover - sqlite compat
        return "TEXT"


# Stub PyMuPDF so tests importing parse modules don't require native dependency.
sys.modules.setdefault("fitz", types.SimpleNamespace())  # type: ignore


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "postgres: requires a PostgreSQL database")


def _resolve_test_database_url() -> Tuple[str, bool]:
    candidate = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    url = candidate or "sqlite+pysqlite:///:memory:"
    return url, url.lower().startswith("postgresql")


@pytest.fixture()
def engine(request: pytest.FixtureRequest) -> Generator["Engine", None, None]:
    if _SQLALCHEMY_IMPORT_ERROR or create_engine is None:
        pytest.skip(f"SQLAlchemy is unavailable: {_SQLALCHEMY_IMPORT_ERROR}")
    if Base is None or database_module is None:
        pytest.skip(f"Database metadata unavailable: {_DATABASE_IMPORT_ERROR}")

    database_url, is_postgres = _resolve_test_database_url()
    if request.node.get_closest_marker("postgres") and not is_postgres:
        pytest.skip("PostgreSQL is required for this test")

    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    test_engine = create_engine(database_url, connect_args=connect_args)
    try:
        Base.metadata.create_all(bind=test_engine)
    except CompileError as exc:
        pytest.skip(f"Active test database cannot render schema: {exc}")

    TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    original_session_local = database_module.SessionLocal
    original_engine = database_module.engine
    database_module.SessionLocal = TestingSessionLocal
    database_module.engine = test_engine
    try:
        yield test_engine
    finally:
        database_module.SessionLocal = original_session_local
        database_module.engine = original_engine
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


@pytest.fixture()
def db_session(engine: "Engine") -> Generator["Session", None, None]:
    if _SQLALCHEMY_IMPORT_ERROR or sessionmaker is None:
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
