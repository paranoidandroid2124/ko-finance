"""Persistence helpers for guardrail evaluation history."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from core.logging import get_logger
from services.admin_shared import ADMIN_BASE_DIR, ensure_admin_dir, now_iso

logger = get_logger(__name__)

_SAMPLES_PATH = ADMIN_BASE_DIR / "guardrail_samples.jsonl"
_SAMPLE_LIMIT_DEFAULT = 200


def list_guardrail_samples(
    *,
    limit: int = _SAMPLE_LIMIT_DEFAULT,
    search: Optional[str] = None,
    bookmarked: Optional[bool] = None,
) -> List[Dict[str, object]]:
    if not _SAMPLES_PATH.exists():
        return []

    try:
        lines = _SAMPLES_PATH.read_text(encoding="utf-8").splitlines()
    except OSError as exc:  # pragma: no cover
        logger.error("Failed to read guardrail samples: %s", exc)
        return []

    search_lower = search.lower() if search else None
    results: List[Dict[str, object]] = []
    for line in reversed(lines):
        if len(results) >= limit:
            break
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if bookmarked is not None and bool(record.get("bookmarked")) is not bookmarked:
            continue
        if search_lower:
            haystacks = [
                record.get("sample"),
                record.get("sanitizedSample"),
                record.get("actor"),
                record.get("result"),
                record.get("judgeDecision"),
            ]
            if not any(isinstance(value, str) and search_lower in value.lower() for value in haystacks):
                continue
        results.append(record)
    return results


def record_guardrail_sample(
    *,
    actor: str,
    sample: str,
    sanitized_sample: str,
    result: str,
    channels: Iterable[str],
    matched_rules: Iterable[str],
    judge_decision: Optional[str],
    audit_file: Optional[str],
    line_diff: List[Dict[str, object]],
) -> Dict[str, object]:
    ensure_admin_dir(logger)
    sample_id = f"guardrail-{uuid.uuid4().hex[:12]}"
    record = {
        "sampleId": sample_id,
        "actor": actor,
        "sample": sample,
        "sanitizedSample": sanitized_sample,
        "result": result,
        "channels": [str(item) for item in channels],
        "matchedRules": [str(item) for item in matched_rules],
        "judgeDecision": judge_decision,
        "auditFile": audit_file,
        "lineDiff": line_diff,
        "bookmarked": False,
        "note": None,
        "evaluatedAt": now_iso(),
    }
    try:
        with _SAMPLES_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")
    except OSError as exc:  # pragma: no cover
        logger.error("Failed to append guardrail sample: %s", exc)
    return record


def update_guardrail_bookmark(sample_id: str, *, bookmarked: bool) -> Optional[Dict[str, object]]:
    if not _SAMPLES_PATH.exists():
        return None
    try:
        lines = _SAMPLES_PATH.read_text(encoding="utf-8").splitlines()
    except OSError as exc:  # pragma: no cover
        logger.error("Failed to read guardrail samples: %s", exc)
        return None

    updated: Optional[Dict[str, object]] = None
    entries: List[str] = []
    for raw in lines:
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            entries.append(raw)
            continue
        if str(record.get("sampleId")) == sample_id:
            record["bookmarked"] = bool(bookmarked)
            record["updatedAt"] = now_iso()
            updated = record
            entries.append(json.dumps(record, ensure_ascii=False))
        else:
            entries.append(raw)

    if updated is None:
        return None

    try:
        ensure_admin_dir(logger)
        _SAMPLES_PATH.write_text("\n".join(entries) + "\n", encoding="utf-8")
    except OSError as exc:  # pragma: no cover
        logger.error("Failed to persist guardrail bookmark update: %s", exc)
    return updated


__all__ = [
    "list_guardrail_samples",
    "record_guardrail_sample",
    "update_guardrail_bookmark",
]
