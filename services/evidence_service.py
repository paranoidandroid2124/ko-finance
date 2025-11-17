"""Helpers for evidence diff enrichment."""

from __future__ import annotations

import json
import uuid
import hashlib
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from pydantic import ValidationError
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from core.logging import get_logger
from models.evidence import EvidenceSnapshot
from models.filing import Filing
from models.table_extraction import TableCell, TableMeta
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


logger = get_logger(__name__)


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


def compute_snapshot_hash(payload: Mapping[str, Any]) -> str:
    """Generate a stable hash for the given evidence payload."""

    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def save_evidence_snapshot(
    db: Session,
    *,
    urn_id: str,
    payload: Mapping[str, Any],
    author: Optional[str] = None,
    process: Optional[str] = None,
    org_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
) -> Optional[EvidenceSnapshot]:
    """
    Persist an evidence snapshot if it represents a new version.

    Returns the newly-created snapshot when stored, otherwise ``None`` when a duplicate is detected.
    """

    if not urn_id:
        return None

    stored_payload = dict(payload)
    snapshot_hash = compute_snapshot_hash(stored_payload)
    existing = (
        db.query(EvidenceSnapshot)
        .filter(EvidenceSnapshot.urn_id == urn_id, EvidenceSnapshot.snapshot_hash == snapshot_hash)
        .first()
    )
    if existing:
        return None

    latest = (
        db.query(EvidenceSnapshot)
        .filter(EvidenceSnapshot.urn_id == urn_id)
        .order_by(EvidenceSnapshot.updated_at.desc())
        .first()
    )

    snapshot = EvidenceSnapshot(
        urn_id=urn_id,
        snapshot_hash=snapshot_hash,
        previous_snapshot_hash=latest.snapshot_hash if latest else None,
        diff_type="created" if latest is None else "updated",
        payload=stored_payload,
        author=author,
        process=process,
        org_id=org_id,
        user_id=user_id,
    )
    db.add(snapshot)
    return snapshot


def _safe_uuid(value: Any) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _document_payload(row: Filing) -> Dict[str, Any]:
    urls = row.urls if isinstance(row.urls, dict) else {}
    viewer_url = urls.get("viewer") if isinstance(urls, dict) else None
    download_url = None
    if isinstance(urls, dict):
        download_url = urls.get("download") or urls.get("pdf")
    filed_at_iso = None
    if row.filed_at:
        filed_at_iso = row.filed_at.isoformat()
    return {
        "documentId": str(row.id),
        "title": row.report_name or row.title,
        "corpName": row.corp_name,
        "ticker": row.ticker,
        "receiptNo": row.receipt_no,
        "viewerUrl": viewer_url,
        "downloadUrl": download_url,
        "publishedAt": filed_at_iso,
    }


def _attach_document_metadata(db: Session, evidence_items: List[Dict[str, Any]]) -> None:
    filing_ids: Dict[str, uuid.UUID] = {}
    for item in evidence_items:
        filing_id = item.get("filing_id") or item.get("document_id")
        candidate = _safe_uuid(filing_id)
        if candidate:
            filing_ids[str(candidate)] = candidate
    if not filing_ids:
        return
    rows = (
        db.query(Filing)
        .filter(Filing.id.in_(list(filing_ids.values())))
        .all()
    )
    doc_map: Dict[str, Dict[str, Any]] = {str(row.id): _document_payload(row) for row in rows}
    for item in evidence_items:
        filing_id = item.get("filing_id")
        doc = doc_map.get(str(filing_id)) if filing_id else None
        if not doc:
            continue
        item["document"] = doc
        document_url = doc.get("viewerUrl") or doc.get("downloadUrl")
        item.setdefault("document_title", doc.get("title"))
        if document_url:
            item.setdefault("document_url", document_url)
        if doc.get("viewerUrl"):
            item.setdefault("viewer_url", doc.get("viewerUrl"))
        if doc.get("downloadUrl"):
            item.setdefault("download_url", doc.get("downloadUrl"))


def _collect_table_keys(
    evidence_items: List[Dict[str, Any]]
) -> Tuple[List[Tuple[uuid.UUID, int, int]], Dict[str, Dict[str, Any]]]:
    keys: List[Tuple[uuid.UUID, int, int]] = []
    hints: Dict[str, Dict[str, Any]] = {}
    for item in evidence_items:
        hint = item.get("table_hint")
        filing_id = _safe_uuid(item.get("filing_id"))
        if not hint or not filing_id:
            continue
        page_number = hint.get("page_number")
        table_index = hint.get("table_index")
        if page_number is None or table_index is None:
            continue
        try:
            page_int = int(page_number)
            table_int = int(table_index)
        except (TypeError, ValueError):
            continue
        keys.append((filing_id, page_int, table_int))
        hints[item.get("urn_id") or item.get("urnId") or str(id(item))] = {
            "row_index": hint.get("focus_row_index"),
            "page_number": page_int,
            "table_index": table_int,
            "filing_id": filing_id,
        }
    return keys, hints


def _attach_table_metadata(db: Session, evidence_items: List[Dict[str, Any]]) -> None:
    table_keys, hints = _collect_table_keys(evidence_items)
    if not table_keys:
        for item in evidence_items:
            item.pop("table_hint", None)
        return
    unique_keys = list(dict.fromkeys(table_keys))
    rows = (
        db.query(TableMeta)
        .filter(
            tuple_(TableMeta.filing_id, TableMeta.page_number, TableMeta.table_index).in_(unique_keys)
        )
        .all()
    )
    table_map: Dict[Tuple[str, int, int], TableMeta] = {
        (str(row.filing_id), row.page_number or 0, row.table_index or 0): row for row in rows
    }
    row_filters: List[Tuple[uuid.UUID, int]] = []
    for hint in hints.values():
        table_meta = table_map.get(
            (str(hint["filing_id"]), hint.get("page_number") or 0, hint.get("table_index") or 0)
        )
        if not table_meta:
            continue
        row_index = hint.get("row_index")
        if row_index is None:
            continue
        row_filters.append((table_meta.id, row_index))
    unique_row_filters = list(dict.fromkeys(row_filters))
    cell_map: Dict[Tuple[uuid.UUID, int], List[TableCell]] = {}
    if unique_row_filters:
        cell_rows = (
            db.query(TableCell)
            .filter(tuple_(TableCell.table_id, TableCell.row_index).in_(unique_row_filters))
            .order_by(TableCell.table_id.asc(), TableCell.column_index.asc())
            .all()
        )
        for cell in cell_rows:
            cell_map.setdefault((cell.table_id, cell.row_index), []).append(cell)
    for item in evidence_items:
        hint_key = item.get("urn_id") or item.get("urnId") or str(id(item))
        hint = hints.get(hint_key)
        if not hint:
            item.pop("table_hint", None)
            continue
        table_meta = table_map.get(
            (str(hint["filing_id"]), hint.get("page_number") or 0, hint.get("table_index") or 0)
        )
        if not table_meta:
            item.pop("table_hint", None)
            continue
        row_index = hint.get("row_index")
        cells = cell_map.get((table_meta.id, row_index)) if row_index is not None else None
        focus_cells: List[Dict[str, Any]] = []
        if cells:
            for cell in cells:
                numeric_value = float(cell.numeric_value) if cell.numeric_value is not None else None
                focus_cells.append(
                    {
                        "column_index": cell.column_index,
                        "header_path": cell.header_path or [],
                        "value": cell.raw_value,
                        "normalized_value": cell.normalized_value,
                        "numeric_value": numeric_value,
                        "value_type": cell.value_type,
                        "confidence": cell.confidence,
                    }
                )
        item["table_reference"] = {
            "table_id": str(table_meta.id),
            "page_number": table_meta.page_number,
            "table_index": table_meta.table_index,
            "title": table_meta.table_title,
            "row_count": table_meta.row_count,
            "column_count": table_meta.column_count,
            "header_rows": table_meta.header_rows,
            "confidence": table_meta.confidence,
            "column_headers": table_meta.column_headers or [],
            "focus_row_index": row_index,
            "focus_row_cells": focus_cells,
            "explorer_url": f"/table-explorer/tables/{table_meta.id}",
        }
        item.pop("table_hint", None)


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


def _load_trace_removed_snapshots(
    db: Session,
    trace_id: Optional[str],
    current_urns: Set[str],
) -> List[EvidenceSnapshot]:
    if not trace_id:
        return []
    stmt = (
        select(EvidenceSnapshot)
        .where(EvidenceSnapshot.payload["trace_id"].astext == trace_id)
        .order_by(EvidenceSnapshot.urn_id.asc(), EvidenceSnapshot.updated_at.desc())
    )
    rows = db.scalars(stmt).all()
    latest: Dict[str, EvidenceSnapshot] = {}
    for snapshot in rows:
        urn_key = snapshot.urn_id
        if not urn_key or urn_key in latest:
            continue
        latest[urn_key] = snapshot
    removed: List[EvidenceSnapshot] = []
    for urn_key, snapshot in latest.items():
        if urn_key in current_urns:
            continue
        removed.append(snapshot)
    return removed


def attach_diff_metadata(
    db: Session,
    evidence_items: List[Dict[str, Any]],
    trace_id: Optional[str] = None,
) -> DiffMeta:
    """Mutate evidence items with diff metadata derived from previous snapshots."""

    if not evidence_items:
        if trace_id:
            removed_snapshots = _load_trace_removed_snapshots(db, trace_id, set())
            removed_payloads = []
            for snapshot in removed_snapshots:
                data = dict(snapshot.payload or {})
                data.setdefault("urn_id", snapshot.urn_id)
                data["diff_type"] = "removed"
                if snapshot.updated_at:
                    data.setdefault("removed_at", snapshot.updated_at.isoformat())
                removed_payloads.append(data)
            return {"enabled": bool(removed_payloads), "removed": removed_payloads}
        return {"enabled": False, "removed": []}

    current_urns: Set[str] = set()
    latest_snapshots = _load_latest_snapshots(db, (item.get("urn_id") for item in evidence_items))
    if not latest_snapshots:
        for item in evidence_items:
            item.setdefault("diff_type", "created")
            urn_id = item.get("urn_id")
            if urn_id:
                current_urns.add(str(urn_id))
        removed_payloads: List[Dict[str, Any]] = []
        if trace_id:
            removed_snapshots = _load_trace_removed_snapshots(db, trace_id, current_urns)
            for snapshot in removed_snapshots:
                payload = dict(snapshot.payload or {})
                payload.setdefault("urn_id", snapshot.urn_id)
                payload["diff_type"] = "removed"
                if snapshot.updated_at:
                    payload.setdefault("removed_at", snapshot.updated_at.isoformat())
                removed_payloads.append(payload)
            if removed_payloads:
                try:
                    _attach_document_metadata(db, removed_payloads)
                    _attach_table_metadata(db, removed_payloads)
                except Exception as exc:  # pragma: no cover
                    logger.debug("Evidence enrichment failed for removed items: %s", exc, exc_info=True)
                return {"enabled": True, "removed": removed_payloads}
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
        if urn_id:
            current_urns.add(str(urn_id))

    removed_payloads: List[Dict[str, Any]] = []
    if trace_id:
        removed_snapshots = _load_trace_removed_snapshots(db, trace_id, current_urns)
        for snapshot in removed_snapshots:
            payload = dict(snapshot.payload or {})
            payload.setdefault("urn_id", snapshot.urn_id)
            payload["diff_type"] = "removed"
            if snapshot.updated_at:
                payload.setdefault("removed_at", snapshot.updated_at.isoformat())
            removed_payloads.append(payload)
        if removed_payloads:
            diff_enabled = True

    combined_items = list(evidence_items)
    if removed_payloads:
        combined_items.extend(removed_payloads)

    try:
        _attach_document_metadata(db, combined_items)
        _attach_table_metadata(db, combined_items)
    except Exception as exc:  # pragma: no cover - best effort enrichment
        logger.debug("Evidence enrichment failed: %s", exc, exc_info=True)

    return {"enabled": diff_enabled, "removed": removed_payloads}


__all__ = ["attach_diff_metadata"]
