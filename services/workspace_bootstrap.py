"""Helpers to seed default workspace assets for new organisations."""

from __future__ import annotations

import logging
import uuid
from typing import Mapping, Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database import SessionLocal
from services import notebook_service
from services.notebook_service import NotebookServiceError

logger = logging.getLogger(__name__)

_BOOTSTRAP_NOTEBOOK_TITLE = "리서치 스타터 노트"
_BOOTSTRAP_NOTEBOOK_SUMMARY = "온보딩 시 자동으로 생성된 샘플 노트입니다. 팀 메모나 이벤트 정리를 여기에 시작해 보세요."


def _has_notebook(session, *, org_id: uuid.UUID) -> bool:
    row = (
        session.execute(
            text("SELECT 1 FROM notebooks WHERE org_id = :org_id LIMIT 1"),
            {"org_id": str(org_id)},
        )
        .mappings()
        .first()
    )
    return bool(row)


def bootstrap_workspace_for_org(
    *,
    org_id: uuid.UUID,
    owner_id: uuid.UUID,
    source: str = "onboarding",
    metadata: Optional[Mapping[str, object]] = None,
) -> None:
    """Ensure each org has at least one starter notebook."""

    session = SessionLocal()
    try:
        if _has_notebook(session, org_id=org_id):
            return
        note_metadata: dict[str, object] = {"bootstrap": True, "source": source}
        if metadata:
            note_metadata.update(dict(metadata))
        try:
            notebook_service.create_notebook(
                session,
                org_id=org_id,
                owner_id=owner_id,
                title=_BOOTSTRAP_NOTEBOOK_TITLE,
                summary=_BOOTSTRAP_NOTEBOOK_SUMMARY,
                tags=["onboarding", "starter"],
                cover_color="#0ea5e9",
                metadata=note_metadata,
            )
        except NotebookServiceError as exc:
            session.rollback()
            logger.warning("Failed to bootstrap notebook for org=%s: %s", org_id, exc)
    except SQLAlchemyError:
        session.rollback()
        logger.warning("Failed to bootstrap workspace for org=%s", org_id, exc_info=True)
    finally:
        session.close()


__all__ = ["bootstrap_workspace_for_org"]

