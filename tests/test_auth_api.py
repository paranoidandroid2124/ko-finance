import base64
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from lxml import etree
from signxml import XMLSigner, methods
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from core.auth.constants import DEFAULT_SIGNUP_CHANNEL
from database import get_db
from services import auth_service, auth_tokens
from services.auth import common as auth_common
from services.auth_service import RateLimitResult
from web.routers import auth

pytestmark = pytest.mark.postgres


@pytest.fixture(autouse=True)
def _stub_auth_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        auth_common,
        "_check_limit",
        lambda *_, **__: RateLimitResult(allowed=True, remaining=None, reset_at=None),
    )


@pytest.fixture()
def token_store(monkeypatch: pytest.MonkeyPatch) -> Dict[str, List[str]]:
    captured: Dict[str, List[str]] = defaultdict(list)
    original_issue = auth_tokens.issue_magic_token

    def capture(session: Session, **kwargs):
        token = original_issue(session, **kwargs)
        captured[kwargs["token_type"]].append(token.token)
        return token

    monkeypatch.setattr(auth_tokens, "issue_magic_token", capture)
    return captured


@pytest.fixture()
def auth_api_client(db_session: Session) -> Tuple[TestClient, Session]:
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1")
    bind = db_session.connection()
    SessionOverride = sessionmaker(bind=bind, autoflush=False, expire_on_commit=False)

    def override_get_db():
        session = SessionOverride()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        yield client, db_session
    finally:
        client.close()


@pytest.fixture(scope="module")
def saml_signing_material() -> Tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test IdP")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(private_key=key, algorithm=hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    return cert_pem, key_pem


def _build_signed_saml_response(
    *,
    cert_pem: str,
    key_pem: str,
    audience: str,
    destination: str,
    issuer: str,
    email: str = "user@example.com",
) -> str:
    now = datetime.now(timezone.utc)
    issue_instant = now.isoformat().replace("+00:00", "Z")
    not_before = (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    not_on_or_after = (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    response_id = f"_{uuid.uuid4().hex}"
    assertion_id = f"_{uuid.uuid4().hex}"
    xml = f"""
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                ID="{response_id}"
                Version="2.0"
                IssueInstant="{issue_instant}"
                Destination="{destination}">
  <saml:Issuer>{issuer}</saml:Issuer>
  <saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                  ID="{assertion_id}"
                  Version="2.0"
                  IssueInstant="{issue_instant}">
    <saml:Issuer>{issuer}</saml:Issuer>
    <saml:Subject>
      <saml:NameID>{email}</saml:NameID>
    </saml:Subject>
    <saml:Conditions NotBefore="{not_before}" NotOnOrAfter="{not_on_or_after}">
      <saml:AudienceRestriction>
        <saml:Audience>{audience}</saml:Audience>
      </saml:AudienceRestriction>
    </saml:Conditions>
    <saml:AttributeStatement>
      <saml:Attribute Name="email">
        <saml:AttributeValue>{email}</saml:AttributeValue>
      </saml:Attribute>
      <saml:Attribute Name="role">
        <saml:AttributeValue>viewer</saml:AttributeValue>
      </saml:Attribute>
      <saml:Attribute Name="orgSlug">
        <saml:AttributeValue>default-org</saml:AttributeValue>
      </saml:Attribute>
    </saml:AttributeStatement>
  </saml:Assertion>
</samlp:Response>
""".strip()
    root = etree.fromstring(xml.encode("utf-8"))
    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm="rsa-sha256",
        digest_algorithm="sha256",
    )
    signed_root = signer.sign(root, key=key_pem, cert=cert_pem)
    return base64.b64encode(etree.tostring(signed_root)).decode("ascii")


def _saml_config_with_cert(cert_pem: str) -> auth_common.SamlProviderConfig:
    return auth_common.SamlProviderConfig(
        enabled=True,
        sp_entity_id="sp:test",
        acs_url="https://app.local/api/v1/auth/saml/acs",
        metadata_url=None,
        sp_certificate=None,
        idp_entity_id="https://idp.local/metadata",
        idp_sso_url="https://idp.local/sso",
        idp_certificate=cert_pem,
        email_attribute="email",
        name_attribute="displayName",
        org_attribute="orgSlug",
        role_attribute="role",
        default_org_slug="default-org",
        default_role="viewer",
        role_mapping={},
        auto_provision_orgs=False,
        default_plan_tier="enterprise",
    )


def _register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecureP@ssw0rd!",
            "name": "테스트",
            "acceptTerms": True,
            "signupChannel": DEFAULT_SIGNUP_CHANNEL,
        },
    )
    assert response.status_code == 201, response.text


def _verify_latest_token(client: TestClient, token_store: Dict[str, List[str]], token_type: str = "email_verify") -> None:
    token = token_store[token_type][-1]
    response = client.post("/api/v1/auth/email/verify", json={"token": token})
    assert response.status_code == 200, response.text


def test_register_and_verify_flow(auth_api_client: Tuple[TestClient, Session], token_store: Dict[str, List[str]]) -> None:
    client, db = auth_api_client
    email = f"user_{uuid.uuid4().hex}@example.com"

    _register(client, email)
    assert token_store["email_verify"], "verification token was not issued"

    _verify_latest_token(client, token_store)
    row = db.execute(text('SELECT email_verified_at FROM "users" WHERE email = :email'), {"email": email}).mappings().first()
    assert row and row["email_verified_at"] is not None


def test_login_requires_verification(auth_api_client: Tuple[TestClient, Session]) -> None:
    client, _ = auth_api_client
    email = f"user_{uuid.uuid4().hex}@example.com"
    _register(client, email)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecureP@ssw0rd!", "rememberMe": False},
    )
    assert response.status_code == 403
    payload = response.json()
    assert payload["detail"]["code"] == "auth.needs_verification"


def test_login_refresh_and_logout(auth_api_client: Tuple[TestClient, Session], token_store: Dict[str, List[str]]) -> None:
    client, db = auth_api_client
    email = f"user_{uuid.uuid4().hex}@example.com"
    _register(client, email)
    _verify_latest_token(client, token_store)

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecureP@ssw0rd!", "rememberMe": True},
    )
    assert login_response.status_code == 200
    login_data = login_response.json()
    assert login_data["sessionId"]
    assert login_data["sessionToken"]
    assert login_data["accessToken"]
    assert login_data["user"]["orgId"]

    refresh_response = client.post(
        "/api/v1/auth/session/refresh",
        json={
            "refreshToken": login_data["refreshToken"],
            "sessionId": login_data["sessionId"],
            "sessionToken": login_data["sessionToken"],
        },
    )
    assert refresh_response.status_code == 200
    refresh_data = refresh_response.json()
    assert refresh_data["refreshToken"] != login_data["refreshToken"]

    logout_response = client.post(
        "/api/v1/auth/logout",
        json={"sessionId": login_data["sessionId"], "refreshToken": login_data["refreshToken"], "allDevices": False},
    )
    assert logout_response.status_code == 204
    row = db.execute(
        text("SELECT revoked_at FROM session_tokens WHERE id = :id"),
        {"id": login_data["sessionId"]},
    ).mappings().first()
    assert row and row["revoked_at"] is not None


def test_password_reset_flow(auth_api_client: Tuple[TestClient, Session], token_store: Dict[str, List[str]]) -> None:
    client, _ = auth_api_client
    email = f"user_{uuid.uuid4().hex}@example.com"
    _register(client, email)
    _verify_latest_token(client, token_store)

    reset_request = client.post("/api/v1/auth/password-reset/request", json={"email": email})
    assert reset_request.status_code == 200
    assert token_store["password_reset"], "password reset token missing"

    new_password = "NewP@ssword42!"
    reset_confirm = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token_store["password_reset"][-1], "newPassword": new_password},
    )
    assert reset_confirm.status_code == 200

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": new_password, "rememberMe": False},
    )
    assert login_response.status_code == 200


def test_rate_limit_yields_retry_after(auth_api_client: Tuple[TestClient, Session], monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ = auth_api_client

    def always_block(*_, **__):
        return RateLimitResult(allowed=False, remaining=0, reset_at=None)

    monkeypatch.setattr(auth_service, "_check_limit", always_block)
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"user_{uuid.uuid4().hex}@example.com",
            "password": "SecureP@ssw0rd!",
            "name": "테스트",
            "acceptTerms": True,
            "signupChannel": DEFAULT_SIGNUP_CHANNEL,
        },
    )
    assert response.status_code == 429
    payload = response.json()
    assert payload["detail"]["code"] == "auth.rate_limited"
    assert "retryAfter" in payload["detail"]
    assert response.headers.get("Retry-After") is not None


def test_resend_verification(auth_api_client: Tuple[TestClient, Session], token_store: Dict[str, List[str]]) -> None:
    client, _ = auth_api_client
    email = f"user_{uuid.uuid4().hex}@example.com"
    _register(client, email)

    response = client.post("/api/v1/auth/email/verify/resend", json={"email": email})
    assert response.status_code == 200
    assert token_store["email_verify"], "resend should create verification token"


def test_account_unlock_request_and_confirm(auth_api_client: Tuple[TestClient, Session], token_store: Dict[str, List[str]]) -> None:
    client, db_session = auth_api_client
    email = f"user_{uuid.uuid4().hex}@example.com"
    _register(client, email)
    _verify_latest_token(client, token_store)

    locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
    db_session.execute(
        text('UPDATE "users" SET failed_attempts = :attempts, locked_until = :locked WHERE email = :email'),
        {"attempts": 5, "locked": locked_until, "email": email},
    )
    db_session.commit()

    request_response = client.post("/api/v1/auth/account/unlock/request", json={"email": email})
    assert request_response.status_code == 200
    assert token_store["account_unlock"], "unlock token missing"

    confirm_response = client.post(
        "/api/v1/auth/account/unlock/confirm", json={"token": token_store["account_unlock"][-1]}
    )
    assert confirm_response.status_code == 200
    payload = confirm_response.json()
    assert payload["unlocked"] is True

    row = db_session.execute(
        text('SELECT failed_attempts, locked_until FROM "users" WHERE email = :email'),
        {"email": email},
    ).mappings().first()
    assert row and (row["locked_until"] is None or row["locked_until"] <= datetime.now(timezone.utc))
    assert row["failed_attempts"] == 0


@pytest.mark.parametrize(
    ("scenario", "expected_code"),
    [
        ("saml_invalid_payload", "auth.saml_invalid_payload"),
        ("oidc_state_expired", "auth.oidc_state_expired"),
    ],
)
def test_sso_failure_scenarios(
    auth_api_client: Tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    expected_code: str,
) -> None:
    client, _ = auth_api_client
    if scenario == "saml_invalid_payload":
        saml_config = auth_common.SamlProviderConfig(
            enabled=True,
            sp_entity_id="sp:test",
            acs_url="https://app.local/api/v1/auth/saml/acs",
            metadata_url=None,
            sp_certificate=None,
            idp_entity_id="idp-test",
            idp_sso_url="https://idp.local/sso",
            idp_certificate=None,
            email_attribute="email",
            name_attribute="displayName",
            org_attribute="org",
            role_attribute="role",
            default_org_slug="default-org",
            default_role="viewer",
            role_mapping={},
            auto_provision_orgs=False,
            default_plan_tier="enterprise",
        )
        monkeypatch.setattr(auth_common, "_SAML_CONFIG", saml_config)
        response = client.post(
            "/api/v1/auth/saml/acs",
            data={
                "SAMLResponse": "!!!",  # invalid base64 payload
                "RelayState": "state",
            },
        )
    else:
        oidc_config = auth_common.OidcProviderConfig(
            enabled=True,
            client_id="client-id",
            client_secret="client-secret",
            authorization_url="https://idp.local/authorize",
            token_url="https://idp.local/token",
            userinfo_url="https://idp.local/userinfo",
            redirect_uri="https://app.local/api/v1/auth/oidc/callback",
            scopes=("openid", "email"),
            default_org_slug=None,
            org_claim="org",
            role_claim="role",
            plan_claim="plan",
            email_claim="email",
            name_claim="name",
            default_role="viewer",
            role_mapping={},
            auto_provision_orgs=False,
            default_plan_tier="enterprise",
        )
        monkeypatch.setattr(auth_common, "_OIDC_CONFIG", oidc_config)
        expired_state = auth_common._encode_state(  # type: ignore[attr-defined]
            {
                "provider": "oidc",
                "nonce": "expired",
                "exp": int((datetime.now(timezone.utc) - timedelta(seconds=5)).timestamp()),
            }
        )
        response = client.get(
            "/api/v1/auth/oidc/callback",
            params={"code": "dummy-code", "state": expired_state},
        )

    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["code"] == expected_code


def test_validate_saml_signature_accepts_valid_payload(saml_signing_material: Tuple[str, str]) -> None:
    cert_pem, key_pem = saml_signing_material
    config = _saml_config_with_cert(cert_pem)
    payload = base64.b64decode(
        _build_signed_saml_response(
            cert_pem=cert_pem,
            key_pem=key_pem,
            audience=config.sp_entity_id or "",
            destination=config.acs_url or "",
            issuer=config.idp_entity_id or "https://idp.local/metadata",
        ).encode("utf-8")
    )
    auth_common._validate_saml_signature(payload, config)


def test_validate_saml_signature_rejects_tampered_payload(saml_signing_material: Tuple[str, str]) -> None:
    cert_pem, key_pem = saml_signing_material
    config = _saml_config_with_cert(cert_pem)
    payload = base64.b64decode(
        _build_signed_saml_response(
            cert_pem=cert_pem,
            key_pem=key_pem,
            audience=config.sp_entity_id or "",
            destination=config.acs_url or "",
            issuer=config.idp_entity_id or "https://idp.local/metadata",
        ).encode("utf-8")
    )
    tampered = payload.replace(b"user@example.com", b"attacker@example.com")
    with pytest.raises(auth_common.AuthServiceError) as excinfo:
        auth_common._validate_saml_signature(tampered, config)
    assert excinfo.value.code == "auth.saml_invalid_signature"


def test_enforce_saml_temporal_conditions_blocks_invalid_windows() -> None:
    future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    past = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    with pytest.raises(auth_common.AuthServiceError) as excinfo:
        auth_common._enforce_saml_temporal_conditions({"@NotBefore": future})
    assert excinfo.value.code == "auth.saml_not_yet_valid"
    with pytest.raises(auth_common.AuthServiceError) as excinfo:
        auth_common._enforce_saml_temporal_conditions({"@NotOnOrAfter": past})
    assert excinfo.value.code == "auth.saml_expired"
