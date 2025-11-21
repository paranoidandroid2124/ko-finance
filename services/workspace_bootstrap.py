"""Utilities to bootstrap a sample workspace for new orgs/users."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from database import SessionLocal
from models.chat import ChatMessage, ChatSession


def bootstrap_workspace_for_org(
    *,
    org_id: Optional[uuid.UUID],
    owner_id: Optional[uuid.UUID],
    source: str = "onboarding",
) -> None:
    """Create a minimal sample chat session/messages for a new org."""
    db = SessionLocal()
    try:
        session = ChatSession(
            user_id=owner_id,
            org_id=org_id,
            title="[샘플] 하이브 주가 분석 가이드",
            message_count=2,
            last_message_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.flush()

        turn_id = uuid.uuid4()
        user_msg = ChatMessage(
            session_id=session.id,
            seq=1,
            turn_id=turn_id,
            role="user",
            state="ready",
            content="하이브 주가 분석 (주요 리스크와 CAR 영향까지 정리해줘)",
            meta={"source": source},
        )
        ai_msg = ChatMessage(
            session_id=session.id,
            seq=2,
            turn_id=turn_id,
            role="assistant",
            state="ready",
            content="하이브 최근 실적은 역기저와 비용 확대로 조정 구간입니다. 사건 발생 후 5일 CAR은 -12% 수준으로 엔터 피어 대비 -8%p 언더퍼폼했습니다. 재무·사건 영향과 동종업계 비교를 함께 확인해 보세요.",
            meta={"source": source},
        )
        db.add_all([user_msg, ai_msg])
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


__all__ = ["bootstrap_workspace_for_org"]
