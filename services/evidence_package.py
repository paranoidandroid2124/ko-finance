"""Assemble PDF, evidence, and trace data into a distributable bundle."""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from core.logging import get_logger
from services import storage_service

logger = get_logger(__name__)

_OUTPUT_ROOT = Path(os.getenv("EVENT_BRIEF_OUTPUT_DIR", "uploads/admin/event_briefs"))
_PREFIX = os.getenv("EVENT_BRIEF_OBJECT_PREFIX", "event-briefs")


@dataclass
class PackageResult:
    pdf_path: Path
    pdf_object: Optional[str]
    pdf_url: Optional[str]
    zip_path: Path
    zip_object: Optional[str]
    zip_url: Optional[str]
    manifest_path: Path


def _ensure_output_dir() -> Path:
    try:
        _OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover - filesystem guard
        logger.error("Failed to ensure event brief output directory: %s", exc, exc_info=True)
    return _OUTPUT_ROOT


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_object_name(base: str, suffix: str) -> str:
    slug = base.replace(" ", "-").lower()
    return f"{_PREFIX}/{slug}/{suffix}"


def make_evidence_bundle(
    *,
    task_id: str,
    pdf_path: Path,
    brief_payload: Mapping[str, Any],
    diff_payload: Optional[Mapping[str, Any]] = None,
    trace_payload: Optional[Mapping[str, Any]] = None,
    audit_payload: Optional[Mapping[str, Any]] = None,
) -> PackageResult:
    """
    Persist the rendered PDF alongside JSON artefacts and package them into a ZIP archive.

    Returns
    -------
    PackageResult
        Paths and optional MinIO object metadata for downstream consumption.
    """

    base_name = f"{task_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    output_dir = _ensure_output_dir() / base_name
    output_dir.mkdir(parents=True, exist_ok=True)

    target_pdf = output_dir / "event_brief.pdf"
    shutil.copy2(pdf_path, target_pdf)

    brief_path = output_dir / "event_brief.json"
    _write_json(brief_path, brief_payload)

    if diff_payload:
        diff_path = output_dir / "evidence_diff.json"
        _write_json(diff_path, diff_payload)
    else:
        diff_path = None

    if trace_payload:
        trace_path = output_dir / "trace_meta.json"
        _write_json(trace_path, trace_payload)
    else:
        trace_path = None

    if audit_payload:
        audit_path = output_dir / "audit_meta.json"
        _write_json(audit_path, audit_payload)
    else:
        audit_path = None

    manifest = {
        "taskId": task_id,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "files": {
            "pdf": target_pdf.name,
            "brief": brief_path.name,
            "diff": diff_path.name if diff_path else None,
            "trace": trace_path.name if trace_path else None,
            "audit": audit_path.name if audit_path else None,
        },
    }
    manifest_path = output_dir / "manifest.json"
    _write_json(manifest_path, manifest)

    package_path = output_dir / "evidence_package.zip"
    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(target_pdf, arcname=target_pdf.name)
        archive.write(brief_path, arcname=brief_path.name)
        archive.write(manifest_path, arcname=manifest_path.name)
        if diff_path:
            archive.write(diff_path, arcname=diff_path.name)
        if trace_path:
            archive.write(trace_path, arcname=trace_path.name)
        if audit_path:
            archive.write(audit_path, arcname=audit_path.name)

    pdf_object = None
    pdf_url = None
    zip_object = None
    zip_url = None

    if storage_service.is_enabled():
        pdf_object = storage_service.upload_file(
            str(target_pdf),
            object_name=_build_object_name(base_name, target_pdf.name),
            content_type="application/pdf",
        )
        if pdf_object:
            pdf_url = storage_service.get_presigned_url(pdf_object)

        zip_object = storage_service.upload_file(
            str(package_path),
            object_name=_build_object_name(base_name, package_path.name),
            content_type="application/zip",
        )
        if zip_object:
            zip_url = storage_service.get_presigned_url(zip_object)

    return PackageResult(
        pdf_path=target_pdf,
        pdf_object=pdf_object,
        pdf_url=pdf_url,
        zip_path=package_path,
        zip_object=zip_object,
        zip_url=zip_url,
        manifest_path=manifest_path,
    )


__all__ = ["PackageResult", "make_evidence_bundle"]


