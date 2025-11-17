from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from services import onboarding_service

pytestmark = pytest.mark.postgres


def _create_user(session: Session, email: str) -> str:
    now = datetime.now(timezone.utc)
    row = (
        session.execute(
            text(
                """
                INSERT INTO "users" (
                    email, name, password_hash, plan_tier, role, signup_channel, email_verified_at, failed_attempts, locked_until
                )
                VALUES (:email, :name, :password_hash, 'free', 'user', 'email', :now, 0, NULL)
                RETURNING id
                """
            ),
            {"email": email, "name": "Tester", "password_hash": "hash", "now": now},
        )
        .mappings()
        .first()
    )
    assert row is not None
    return str(row["id"])


def test_load_wizard_state_bootstraps_org(db_session: Session) -> None:
    user_id = _create_user(db_session, f"user_{uuid.uuid4().hex}@example.com")
    state = onboarding_service.load_onboarding_wizard_state(db_session, user_id=user_id)

    assert state.org.plan_tier == "free"
    assert state.org.member_count == 1
    assert state.org.membership_role == "admin"
    assert any(option.tier == "starter" for option in state.plan_options)


def test_upsert_org_profile_updates_slug_and_name(db_session: Session) -> None:
    user_id = _create_user(db_session, f"user_{uuid.uuid4().hex}@example.com")
    onboarding_service.load_onboarding_wizard_state(db_session, user_id=user_id)

    updated = onboarding_service.upsert_org_profile(
        db_session,
        user_id=user_id,
        name="핵심 전략팀",
        slug="core-team",
    )
    assert updated.name == "핵심 전략팀"
    assert updated.slug == "core-team"

    other_user = _create_user(db_session, f"other_{uuid.uuid4().hex}@example.com")
    onboarding_service.load_onboarding_wizard_state(db_session, user_id=other_user)

    with pytest.raises(ValueError):
        onboarding_service.upsert_org_profile(db_session, user_id=other_user, name="다른 팀", slug="core-team")


def test_invite_org_members_creates_pending_membership(db_session: Session) -> None:
    user_id = _create_user(db_session, f"user_{uuid.uuid4().hex}@example.com")
    state = onboarding_service.load_onboarding_wizard_state(db_session, user_id=user_id)
    members = onboarding_service.invite_org_members(
        db_session,
        actor_id=user_id,
        org_id=state.org.id,
        invites=[{"email": f"invitee_{uuid.uuid4().hex}@example.com"}],
    )
    assert any(member.email and member.status == "pending" for member in members)


def test_select_plan_for_org_updates_subscription(db_session: Session) -> None:
    user_id = _create_user(db_session, f"user_{uuid.uuid4().hex}@example.com")
    state = onboarding_service.load_onboarding_wizard_state(db_session, user_id=user_id)

    updated = onboarding_service.select_plan_for_org(
        db_session,
        user_id=user_id,
        org_id=state.org.id,
        plan_tier="starter",
    )
    assert updated.plan_tier == "starter"

    row = (
        db_session.execute(
            text("SELECT status FROM org_subscriptions WHERE org_id = :org_id"),
            {"org_id": str(state.org.id)},
        )
        .mappings()
        .first()
    )
    assert row and row["status"] == "active"
