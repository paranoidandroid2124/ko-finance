from __future__ import annotations

import uuid
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from web.middleware.auth_context import AuthenticatedUser
from web.routers import onboarding as onboarding_router

pytestmark = pytest.mark.postgres


def _create_user(session: Session, email: str) -> str:
    row = (
        session.execute(
            text(
                """
                INSERT INTO "users" (email, name, password_hash, plan_tier, role, signup_channel, email_verified_at, failed_attempts, locked_until)
                VALUES (:email, 'Tester', 'hash', 'free', 'user', 'email', NOW(), 0, NULL)
                RETURNING id
                """
            ),
            {"email": email},
        )
        .mappings()
        .first()
    )
    assert row is not None
    return str(row["id"])


def _build_auth_user(user_id: str, email: str) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user_id,
        email=email,
        plan="free",
        role="user",
        email_verified=True,
    )


def _setup_app(db_session: Session, user_id: str) -> FastAPI:
    app = FastAPI()
    app.include_router(onboarding_router.router, prefix="/api/v1")

    def override_db():
        yield db_session

    def override_user(request):
        return _build_auth_user(user_id, "user@example.com")

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[onboarding_router._require_user] = override_user  # type: ignore[attr-defined]
    return app


def _state(client: TestClient) -> dict:
    response = client.get("/api/v1/onboarding/state")
    assert response.status_code == 200
    return response.json()


def _org_id_from_state(state: dict) -> str:
    return str(state["org"]["id"])


def _count_subscriptions(session: Session, org_id: str) -> int:
    row = session.execute(
        text("SELECT COUNT(*) AS total FROM org_subscriptions WHERE org_id = :org_id"),
        {"org_id": org_id},
    ).mappings().first()
    return int(row["total"])


def test_onboarding_state_and_slug_check(db_session: Session) -> None:
    user_id = _create_user(db_session, f"user_{uuid.uuid4().hex}@example.com")
    app = _setup_app(db_session, user_id)
    client = TestClient(app)
    try:
        state = _state(client)
        org_id = _org_id_from_state(state)
        assert org_id

        available = client.get("/api/v1/onboarding/org/slug/demo-workspace")
        assert available.status_code == 200
        assert available.json()["available"] is True

        update = client.post("/api/v1/onboarding/org", json={"name": "Demo Org", "slug": "demo-workspace"})
        assert update.status_code == 200

        unavailable = client.get("/api/v1/onboarding/org/slug/demo-workspace")
        assert unavailable.status_code == 200
        assert unavailable.json()["available"] is False
    finally:
        client.close()


def test_invite_and_plan_endpoints(db_session: Session) -> None:
    user_id = _create_user(db_session, f"user_{uuid.uuid4().hex}@example.com")
    app = _setup_app(db_session, user_id)
    client = TestClient(app)
    try:
        state = _state(client)
        org_id = _org_id_from_state(state)
        invite_payload = {
            "orgId": org_id,
            "invites": [
                {"email": f"a_{uuid.uuid4().hex}@example.com", "role": "viewer"},
                {"email": f"b_{uuid.uuid4().hex}@example.com", "role": "editor"},
            ],
        }
        invite_response = client.post("/api/v1/onboarding/invite", json=invite_payload)
        assert invite_response.status_code == 200
        payload = invite_response.json()
        assert len(payload["members"]) >= 3  # owner + two invites

        select_response = client.post("/api/v1/onboarding/plan", json={"orgId": org_id, "planTier": "starter"})
        assert select_response.status_code == 200
        assert select_response.json()["org"]["planTier"] == "starter"

        assert _count_subscriptions(db_session, org_id) == 1
    finally:
        client.close()
