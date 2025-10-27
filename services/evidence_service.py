"""Helpers for evidence diff enrichment."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.evidence import EvidenceSnapshot
from schemas.api.rag import EvidenceAnchor, SelfCheckResult

DiffMeta = Dict[str, Any]

_DIFF_FIELDS = (
    "quote",
    "section",
    "page_number",
    "anchor",
    "source_reliability",
    "self_check",
)


def _normalize_anchor(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    try:
        anchor = EvidenceAnchor.model_validate(value)
    except ValidationError:
        return None
    return anchor.model_dump(mode="json", exclude_none=True)


def _normalize_self_check(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    try:
        result = SelfCheckResult.model_validate(value)
    except ValidationError:
        return None
    return result.model_dump(mode="json", exclude_none=True)


def _normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    quote = payload.get("quote")
    if quote is None:
        quote = payload.get("content")

    normalized = {
        "quote": str(quote) if quote is not None else None,
        "section": payload.get("section"),
        "page_number": payload.get("page_number"),
        "anchor": _normalize_anchor(payload.get("anchor")),
        "source_reliability": payload.get("source_reliability"),
        "self_check": _normalize_self_check(payload.get("self_check")),
    }
    return normalized


def _build_signature(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _load_latest_snapshots(
    db: Session, urn_ids: Iterable[str]
) -> Dict[str, EvidenceSnapshot]:
    urn_list = [urn for urn in urn_ids if urn]
    if not urn_list:
        return {}

    stmt = (
        select(EvidenceSnapshot)
        .where(EvidenceSnapshot.urn_id.in_(urn_list))
        .order_by(EvidenceSnapshot.urn_id, EvidenceSnapshot.updated_at.desc())
    )
    rows = db.scalars(stmt).all()

    latest: Dict[str, EvidenceSnapshot] = {}
    for snapshot in rows:
        if snapshot.urn_id in latest:
            continue
        latest[snapshot.urn_id] = snapshot
    return latest


def attach_diff_metadata(db: Session, evidence_items: List[Dict[str, Any]]) -> DiffMeta:
    """Mutate evidence items with diff metadata derived from previous snapshots."""

    if not evidence_items:
        return {"enabled": False, "removed": []}

    latest_snapshots = _load_latest_snapshots(db, (item.get("urn_id") for item in evidence_items))
    if not latest_snapshots:
        for item in evidence_items:
            item.setdefault("diff_type", "created")
        return {"enabled": True, "removed": []}

    diff_enabled = False

    for item in evidence_items:
        urn_id = item.get("urn_id")
        if not urn_id:
            continue

        previous_snapshot = latest_snapshots.get(urn_id)
        if previous_snapshot is None:
            item.setdefault("diff_type", "created")
            diff_enabled = True
            continue

        previous_payload = previous_snapshot.payload or {}
        previous_normalized = _normalize_payload(previous_payload)
        current_normalized = _normalize_payload(item)

        previous_anchor = previous_normalized.get("anchor")
        if previous_anchor:
            item["previous_anchor"] = previous_anchor

        previous_self_check = previous_normalized.get("self_check")
        if previous_self_check:
            item["previous_self_check"] = previous_self_check

        if previous_normalized.get("quote") is not None:
            item["previous_quote"] = previous_normalized["quote"]
        if previous_normalized.get("section"):
            item["previous_section"] = previous_normalized["section"]
        if previous_normalized.get("page_number") is not None:
            item["previous_page_number"] = previous_normalized["page_number"]
        if previous_normalized.get("source_reliability"):
            item["previous_source_reliability"] = previous_normalized["source_reliability"]

        previous_signature = _build_signature(previous_normalized)
        current_signature = _build_signature(current_normalized)

        if previous_signature == current_signature:
            item["diff_type"] = "unchanged"
        else:
            item["diff_type"] = "updated"
            changed_fields = [
                field
                for field in _DIFF_FIELDS
                if previous_normalized.get(field) != current_normalized.get(field)
            ]
            if changed_fields:
                item["diff_changed_fields"] = changed_fields
        diff_enabled = True

    return {"enabled": diff_enabled, "removed": []}


__all__ = ["attach_diff_metadata"]
