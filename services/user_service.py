"""User data access helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text

from database import SessionLocal


@dataclass(frozen=True)
class UserRecord:
    id: str
    email: str
    plan_tier: Optional[str]
    role: Optional[str]
    email_verified: bool


def fetch_user_by_id(user_id: str) -> Optional[UserRecord]:
    """Load a user row by identifier."""

    db = SessionLocal()
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT id, email, plan_tier, role, email_verified_at
                    FROM "users"
                    WHERE id = :id
                    """
                ),
                {"id": user_id},
            )
            .mappings()
            .first()
        )
    finally:
        db.close()

    if not row:
        return None

    return UserRecord(
        id=str(row["id"]),
        email=row["email"],
        plan_tier=row.get("plan_tier"),
        role=row.get("role"),
        email_verified=bool(row.get("email_verified_at")),
    )


__all__ = ["UserRecord", "fetch_user_by_id"]
