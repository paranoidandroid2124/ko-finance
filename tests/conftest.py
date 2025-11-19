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
    from sqlalchemy.orm import Session, scoped_session, sessionmaker
    from sqlalchemy.ext.compiler import compiles
    from sqlalchemy.pool import StaticPool
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


@pytest.fixture(scope="session")
def engine(request: pytest.FixtureRequest) -> Generator["Engine", None, None]:
    if _SQLALCHEMY_IMPORT_ERROR or create_engine is None:
        pytest.skip(f"SQLAlchemy is unavailable: {_SQLALCHEMY_IMPORT_ERROR}")
    if Base is None or database_module is None:
        pytest.skip(f"Database metadata unavailable: {_DATABASE_IMPORT_ERROR}")

    # Ensure all model metadata is registered before creating tables.
    try:  # pragma: no cover - import side effect only
        import models  # noqa: F401
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Failed to import models: {exc}")

    database_url, is_postgres = _resolve_test_database_url()
    if request.node.get_closest_marker("postgres") and not is_postgres:
        pytest.skip("PostgreSQL is required for this test")

    engine_kwargs = {}
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if ":memory:" in database_url:
            engine_kwargs["poolclass"] = StaticPool
    test_engine = create_engine(database_url, connect_args=connect_args, **engine_kwargs)

    required_tables = {
        "chat_sessions",
        "chat_messages",
        "chat_messages_archive",
        "chat_audit",
        "evidence_snapshots",
    }

    tables = [
        table
        for name, table in Base.metadata.tables.items()
        if name in required_tables
    ]
    if not tables:
        tables = list(Base.metadata.tables.values())

    try:
        Base.metadata.create_all(bind=test_engine, tables=tables)
    except CompileError as exc:
        pytest.skip(f"Active test database cannot render schema: {exc}")

    SessionFactory = scoped_session(sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False))
    original_session_local = database_module.SessionLocal
    original_engine = database_module.engine
    database_module.SessionLocal = SessionFactory
    database_module.engine = test_engine
    try:  # pragma: no cover - optional dependency
        import services.entitlement_service as entitlement_service

        entitlement_original_session = getattr(entitlement_service, "_SessionLocal", None)
        entitlement_service._SessionLocal = SessionFactory  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - fallback if module unavailable
        entitlement_original_session = None

    try:
        yield test_engine
    finally:
        database_module.SessionLocal = original_session_local
        database_module.engine = original_engine
        if "entitlement_service" in locals() and entitlement_original_session is not None:
            entitlement_service._SessionLocal = entitlement_original_session  # type: ignore[attr-defined]
        Base.metadata.drop_all(bind=test_engine, tables=tables)
        SessionFactory.remove()
        test_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_schema(engine: "Engine") -> Generator[None, None, None]:
    """Autouse wrapper to make sure the engine fixture runs for API tests."""

    try:
        yield
    finally:
        pass


@pytest.fixture()
def db_session(engine: "Engine") -> Generator["Session", None, None]:
    if _SQLALCHEMY_IMPORT_ERROR or sessionmaker is None:
        pytest.skip(f"SQLAlchemy is unavailable: {_SQLALCHEMY_IMPORT_ERROR}")

    session_factory = database_module.SessionLocal
    connection = engine.connect()
    transaction = connection.begin()
    session_factory.configure(bind=connection)
    session = session_factory()
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans) -> None:  # pragma: no cover - SQLAlchemy callback
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        session_factory.remove()
        session_factory.configure(bind=engine)
        transaction.rollback()
        connection.close()
