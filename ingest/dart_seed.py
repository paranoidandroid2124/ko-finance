"""Seed recent filings from DART into the local database."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, cast

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from database import SessionLocal
from ingest.dart_client import DartClient
from ingest.file_downloader import attempt_viewer_fallback, parse_filing_bundle
from models.filing import Filing, STATUS_PENDING
from services import storage_service
from services.dart_sync import sync_additional_disclosures
from services.ingest_metrics import observe_latency, record_error, record_result

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

UPLOAD_DIR = "uploads"
PACKAGE_STAGE = "seed.package"
TASK_STAGE = "seed.task"


def _insert_filing_record(db: Session, values: Dict[str, object]) -> Optional[Filing]:
    """Insert a filing row if it does not already exist."""
    stmt = (
        insert(Filing)
        .values(**values)
        .on_conflict_do_nothing(index_elements=[Filing.receipt_no])
        .returning(Filing.id)
    )
    result = db.execute(stmt)
    inserted_id = result.scalar_one_or_none()
    db.commit()
    if inserted_id is None:
        return None
    return db.get(Filing, inserted_id)


def _ensure_storage_copy(receipt_no: str, pdf_path: Optional[str]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not pdf_path or not storage_service.is_enabled():
        return result
    object_name = f"{receipt_no}.pdf"
    uploaded = storage_service.upload_file(pdf_path, object_name=object_name)
    if not uploaded:
        return result
    result["storage_object"] = uploaded
    result["storage_provider"] = storage_service.provider_name()
    presigned = storage_service.get_presigned_url(uploaded)
    if presigned:
        result["storage_url"] = presigned
    # legacy keys for backwards compatibility with existing consumers
    result.setdefault("minio_object", uploaded)
    if presigned:
        result.setdefault("minio_url", presigned)
    return result


def _enqueue_filing_task(filing_id: uuid.UUID) -> None:
    try:
        from parse.tasks import process_filing  # Lazy import to avoid circular dependency
    except ImportError:
        logger.warning("process_filing task not available yet. Skipping enqueue.")
        return

    task = cast(Any, process_filing)
    if hasattr(task, "delay"):
        task.delay(str(filing_id))
    else:
        logger.warning("process_filing task does not expose delay().")


def seed_recent_filings(
    days_back: int = 1,
    db: Optional[Session] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    corp_code: Optional[str] = None,
) -> int:
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    created_count = 0
    task_stage_result = "success"
    task_started = time.perf_counter()

    try:
        client = DartClient()
        if start_date:
            since = datetime.combine(start_date, datetime.min.time())
        else:
            since = datetime.now() - timedelta(days=days_back)
        until = None
        if end_date:
            until = datetime.combine(end_date, datetime.min.time())
        filings_meta = client.list_recent_filings(
            since=since,
            until=until,
            corp_code=corp_code,
        )
        if not filings_meta:
            logger.info("No new filings detected in the last %d day(s).", days_back)
            return 0

        existing_receipts = {
            receipt for (receipt,) in db.query(Filing.receipt_no).all() if receipt
        }

        for meta in filings_meta:
            receipt_no = meta.get("rcept_no")
            if not receipt_no or receipt_no in existing_receipts:
                continue
            viewer_url = client.make_viewer_url(receipt_no)
            fetch_started = time.perf_counter()
            package_data = None
            package_result: Optional[str] = None

            try:
                zip_bytes = client.download_document_zip(receipt_no)
            except Exception as exc:  # pragma: no cover - defensive network guard
                logger.warning("Direct ZIP download failed for %s: %s", receipt_no, exc)
                record_error(PACKAGE_STAGE, "zip_download", exc)
                zip_bytes = None

            if zip_bytes:
                package_data = parse_filing_bundle(
                    receipt_no=receipt_no,
                    data=zip_bytes,
                    save_dir=UPLOAD_DIR,
                    download_url=client.make_document_url(receipt_no),
                )
                if package_data:
                    package_result = "success"
                else:
                    record_error(PACKAGE_STAGE, "zip_payload", "EmptyPackage")

            if not package_data:
                corp_code = meta.get("corp_code")
                fallback_outcome = attempt_viewer_fallback(
                    receipt_no=receipt_no,
                    viewer_url=viewer_url,
                    save_dir=UPLOAD_DIR,
                    corp_code=corp_code,
                    corp_name=meta.get("corp_name"),
                    db=db,
                )
                package_data = fallback_outcome.package
                package_result = fallback_outcome.status

                if fallback_outcome.status == "fallback_blocked":
                    logger.warning(
                        "Viewer fallback blocked for receipt %s (corp_code=%s).",
                        receipt_no,
                        corp_code,
                    )
                elif fallback_outcome.status == "fallback_disabled":
                    logger.warning("Viewer fallback globally disabled for %s.", receipt_no)
                elif fallback_outcome.status == "fallback_failure":
                    logger.error("Failed to obtain filing package for %s via viewer.", receipt_no)
                elif fallback_outcome.status == "fallback_success":
                    logger.info("Recovered filing package for %s via viewer fallback.", receipt_no)

                if not package_data:
                    if fallback_outcome.status == "fallback_failure":
                        record_error(PACKAGE_STAGE, "viewer_fallback", "NoPackage")
                    fetch_duration = time.perf_counter() - fetch_started
                    observe_latency(PACKAGE_STAGE, fetch_duration)
                    record_result(PACKAGE_STAGE, package_result)
                    continue

            fetch_duration = time.perf_counter() - fetch_started
            observe_latency(PACKAGE_STAGE, fetch_duration)
            record_result(PACKAGE_STAGE, package_result or "success")

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

            try:
                receipt_raw = meta.get("rcept_dt")
                filed_at = datetime.strptime(receipt_raw, "%Y%m%d") if isinstance(receipt_raw, str) else None
            except ValueError:
                filed_at = None

            filing_values: Dict[str, object] = {
                "id": uuid.uuid4(),
                "corp_code": meta.get("corp_code"),
                "corp_name": meta.get("corp_name"),
                "ticker": meta.get("stock_code"),
                "report_name": meta.get("report_nm"),
                "title": meta.get("report_nm"),
                "receipt_no": receipt_no,
                "filed_at": filed_at,
                "file_name": Path(pdf_path).name if pdf_path else None,
                "file_path": pdf_path,
                "status": STATUS_PENDING,
                "analysis_status": STATUS_PENDING,
                "urls": {
                    "viewer": viewer_url,
                    "download": package_data.get("download_url"),
                },
                "source_files": source_files,
            }

            new_filing = _insert_filing_record(db, filing_values)
            if not new_filing:
                logger.info("Filing %s already exists. Skipping duplicate insert.", receipt_no)
                existing_receipts.add(receipt_no)
                continue
            existing_receipts.add(receipt_no)

            storage_meta = _ensure_storage_copy(receipt_no, pdf_path)
            if storage_meta:
                existing_urls = cast(Optional[Mapping[str, Any]], new_filing.urls)
                urls = dict(existing_urls) if isinstance(existing_urls, Mapping) else {}
                urls.update(storage_meta)
                cast(Any, new_filing).urls = urls
                db.commit()

            try:
                sync_additional_disclosures(db=db, client=client, filing=new_filing)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning(
                    "Failed to sync extended DART disclosures for %s: %s",
                    receipt_no,
                    exc,
                    exc_info=True,
                )

            filing_id = cast(Optional[uuid.UUID], new_filing.id)
            if filing_id:
                _enqueue_filing_task(filing_id)
            created_count += 1

        logger.info("Seeded %d new filings.", created_count)
        return created_count

    except Exception as exc:
        logger.error("Error during DART seed: %s", exc, exc_info=True)
        task_stage_result = "failure"
        record_result(TASK_STAGE, "failure")
        raise

    finally:
        observe_latency(TASK_STAGE, time.perf_counter() - task_started)
        if task_stage_result == "success":
            record_result(TASK_STAGE, "success")
        if own_session:
            db.close()


__all__ = ["seed_recent_filings"]

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed recent filings from DART.")
    parser.add_argument("--days-back", type=int, default=1, help="How many days back to fetch filings for.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    seed_recent_filings(days_back=max(1, args.days_back))
