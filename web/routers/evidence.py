from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models.evidence import EvidenceSnapshot
from schemas.api.evidence import EvidenceWorkspaceDiffSchema, EvidenceWorkspaceResponse
from schemas.api.rag import RAGEvidence
from services.evidence_service import attach_diff_metadata
from services.plan_service import PlanContext
from web.deps import require_plan_feature

router = APIRouter(prefix="/evidence", tags=["Evidence"])


def _parse_uuid(value: Optional[str], *, field: str) -> Optional[uuid.UUID]:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": f"evidence.invalid_{field}", "message": f"Invalid {field} format."},
        ) from exc


def _load_trace_snapshots(
    db: Session,
    trace_id: str,
    *,
    org_id: Optional[uuid.UUID],
    user_id: Optional[uuid.UUID],
) -> List[EvidenceSnapshot]:
    stmt = select(EvidenceSnapshot).where(EvidenceSnapshot.payload["trace_id"].astext == trace_id)
    if org_id:
        stmt = stmt.where(EvidenceSnapshot.org_id == org_id)
    elif user_id:
        stmt = stmt.where(EvidenceSnapshot.user_id == user_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "evidence.owner_required", "message": "User or organization context is required."},
        )
    stmt = (
        stmt.order_by(EvidenceSnapshot.updated_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


@router.get(
    "/workspace",
    response_model=EvidenceWorkspaceResponse,
    summary="Evidence workspace payload for a specific trace identifier.",
)
def get_evidence_workspace(
    trace_id: str = Query(..., alias="traceId", min_length=3),
    urn_id: Optional[str] = Query(None, alias="urnId"),
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    plan: PlanContext = Depends(require_plan_feature("evidence.diff")),
    db: Session = Depends(get_db),
) -> EvidenceWorkspaceResponse:
    del plan  # PlanContext is only used for entitlement enforcement.
    user_id = _parse_uuid(x_user_id, field="userId") if x_user_id else None
    org_id = _parse_uuid(x_org_id, field="orgId") if x_org_id else None
    snapshots = _load_trace_snapshots(db, trace_id, org_id=org_id, user_id=user_id)
    if not snapshots:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidence_trace_not_found")
    payloads: List[Dict[str, Any]] = []
    for snapshot in snapshots:
        entry = dict(snapshot.payload or {})
        entry.setdefault("urn_id", snapshot.urn_id)
        payloads.append(entry)

    enriched_items, diff_meta = attach_diff_metadata(db, payloads, trace_id=trace_id)

    try:
        evidence_models = [
            RAGEvidence.model_validate(item) if isinstance(item, dict) else RAGEvidence(**item)
            for item in enriched_items
        ]
    except ValidationError as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="invalid_evidence_payload") from exc

    selected_urn = urn_id if urn_id and any(item.urn_id == urn_id for item in evidence_models) else None
    pdf_url = None
    pdf_download = None
    for item in evidence_models:
        if not pdf_url:
            pdf_url = item.viewer_url or item.document_url
        if not pdf_download:
            pdf_download = item.download_url
        if pdf_url and pdf_download:
            break

    diff_schema = EvidenceWorkspaceDiffSchema(
        enabled=bool(diff_meta.get("enabled")) if isinstance(diff_meta, dict) else False,
        removed=[
            RAGEvidence.model_validate(entry)
            for entry in diff_meta.get("removed", [])
            if isinstance(entry, dict)
        ]
        if isinstance(diff_meta, dict)
        else [],
    )

    return EvidenceWorkspaceResponse(
        traceId=trace_id,
        evidence=evidence_models,
        diff=diff_schema,
        pdfUrl=pdf_url,
        pdfDownloadUrl=pdf_download,
        selectedUrnId=selected_urn,
    )


__all__ = ["router"]
