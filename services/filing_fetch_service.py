"""Service for on-demand fetching of filing content."""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, cast

from sqlalchemy.orm import Session

from ingest.dart_client import DartClient
from ingest.file_downloader import attempt_viewer_fallback, parse_filing_bundle
from models.filing import Filing
from services import storage_service, filing_jobs
from services.dart_sync import sync_additional_disclosures

logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploads"


def fetch_filing_content(db: Session, filing_id: uuid.UUID) -> Filing:
    """
    Fetch content (PDF/XML) for a filing that was created with metadata only.
    
    1. Checks if filing exists and is in PENDING state (or missing content).
    2. Downloads ZIP from DART.
    3. Updates Filing record with file paths and source_files.
    4. Triggers parsing task.
    """
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise ValueError(f"Filing {filing_id} not found.")

    if filing.file_path and Path(filing.file_path).exists():
        # Already has content, just ensure task is queued if needed
        if filing.analysis_status == "PENDING":
             filing_jobs.enqueue_process_filing(str(filing.id))
        return filing

    receipt_no = filing.receipt_no
    if not receipt_no:
        raise ValueError(f"Filing {filing_id} has no receipt_no.")

    client = DartClient()
    
    # 1. Try ZIP download
    try:
        zip_bytes = client.download_document_zip(receipt_no)
    except Exception as exc:
        logger.warning("Direct ZIP download failed for %s: %s", receipt_no, exc)
        zip_bytes = None

    package_data = None
    if zip_bytes:
        package_data = parse_filing_bundle(
            receipt_no=receipt_no,
            data=zip_bytes,
            save_dir=UPLOAD_DIR,
            download_url=client.make_document_url(receipt_no),
        )

    # 2. Fallback to viewer
    if not package_data:
        viewer_url = client.make_viewer_url(receipt_no)
        fallback_outcome = attempt_viewer_fallback(
            receipt_no=receipt_no,
            viewer_url=viewer_url,
            save_dir=UPLOAD_DIR,
            corp_code=filing.corp_code,
            corp_name=filing.corp_name,
            db=db,
        )
        package_data = fallback_outcome.package
    
    if not package_data:
        raise RuntimeError(f"Failed to fetch content for filing {receipt_no}")

    # 3. Update Filing record
    pdf_path = package_data.get("pdf")
    xml_entries = []
    for xml_path in package_data.get("xml") or []:
        entry = {"path": xml_path}
        if storage_service.is_enabled():
            object_name = f"{receipt_no}/xml/{Path(xml_path).name}"
            uploaded_xml = storage_service.upload_file(
                xml_path,
                object_name=object_name,
                content_type="application/xml",
            )
            if uploaded_xml:
                entry["storage"] = storage_service.provider_name()
                entry["object"] = uploaded_xml
                entry["object_name"] = uploaded_xml
        xml_entries.append(entry)

    source_files = {
        "package": package_data.get("download_url"),
        "pdf": pdf_path,
        "xml": xml_entries,
        "attachments": package_data.get("attachments"),
    }

    filing.file_name = Path(pdf_path).name if pdf_path else None
    filing.file_path = pdf_path
    filing.source_files = source_files
    
    # Update URLs
    existing_urls = cast(Optional[Mapping[str, Any]], filing.urls)
    urls = dict(existing_urls) if isinstance(existing_urls, Mapping) else {}
    urls["download"] = package_data.get("download_url")
    
    if pdf_path and storage_service.is_enabled():
        object_name = f"{receipt_no}.pdf"
        uploaded = storage_service.upload_file(pdf_path, object_name=object_name)
        if uploaded:
            urls["storage_object"] = uploaded
            urls["storage_provider"] = storage_service.provider_name()
            presigned = storage_service.get_presigned_url(uploaded)
            if presigned:
                urls["storage_url"] = presigned
    
    filing.urls = urls
    db.commit()

    # 4. Sync additional info (optional but good for completeness)
    try:
        sync_additional_disclosures(db=db, client=client, filing=filing)
    except Exception as exc:
        logger.warning("Failed to sync extended disclosures for %s: %s", receipt_no, exc)

    # 5. Trigger processing
    filing_jobs.enqueue_process_filing(str(filing.id))
    
    return filing
