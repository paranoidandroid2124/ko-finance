import uuid

import pytest
from sqlalchemy import ARRAY as SA_ARRAY, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

from database import Base
from models.sso_provider import ScimToken, SsoProvider, SsoProviderCredential
from services import sso_provider_service


@compiles(SA_ARRAY, "sqlite")
def _compile_array_sqlite(_element, _compiler, **_kw):
    return "TEXT"


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        bind=engine,
        tables=[
            SsoProvider.__table__,
            SsoProviderCredential.__table__,
            ScimToken.__table__,
        ],
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(
            bind=engine,
            tables=[
                SsoProvider.__table__,
                SsoProviderCredential.__table__,
                ScimToken.__table__,
            ],
        )
        engine.dispose()


def test_create_provider_and_credentials(db_session: Session) -> None:
    provider = sso_provider_service.create_sso_provider(
        db_session,
        slug="ACME",
        provider_type="oidc",
        display_name="Acme OIDC",
        authorization_url="https://idp.acme.com/authorize",
        token_url="https://idp.acme.com/token",
        attribute_mapping={"email": "mail", "name": "displayName"},
        scopes=None,
        default_role="editor",
        default_plan_tier="enterprise",
        metadata={"support": {"email": "ops@acme.com"}},
    )
    sso_provider_service.store_provider_credential(
        db_session,
        provider.id,
        credential_type="oidc_client_secret",
        secret_value="very-secret-value",
        created_by="tester",
    )

    config = sso_provider_service.get_provider_config(db_session, slug="acme")
    assert config
    assert config.provider_type == "oidc"
    assert config.credentials["oidc_client_secret"] == "very-secret-value"
    assert config.attribute_mapping["email"] == "mail"
    assert config.default_role == "editor"


def test_generate_scim_token(db_session: Session) -> None:
    provider = sso_provider_service.create_sso_provider(
        db_session,
        slug="scim-co",
        provider_type="saml",
        display_name="SCIM Co",
        acs_url="https://app.kfinance.local/api/v1/auth/saml/acs/scim-co",
    )

    token = sso_provider_service.generate_scim_token(
        db_session,
        provider.id,
        created_by="ops-user",
        description="primary token",
    )
    assert token and len(token) > 16

    records = sso_provider_service.list_scim_tokens(db_session, provider.id)
    assert len(records) == 1
    stored = records[0]
    assert stored.provider_id == provider.id
    assert token.startswith(stored.token_prefix)
