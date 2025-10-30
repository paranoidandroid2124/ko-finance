"""Seed recent filings from DART into the local database."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import SessionLocal
from ingest.dart_client import DartClient
from ingest.file_downloader import fetch_viewer_bundle, parse_filing_bundle
from models.filing import Filing, STATUS_PENDING
from services import minio_service
from services.dart_sync import sync_additional_disclosures

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

UPLOAD_DIR = "uploads"


def _ensure_minio_copy(receipt_no: str, pdf_path: Optional[str]) -> Optional[str]:
    if not pdf_path or not minio_service.is_enabled():
        return None
    object_name = f"{receipt_no}.pdf"
    uploaded = minio_service.upload_file(pdf_path, object_name=object_name)
    if not uploaded:
        return None
    presigned = minio_service.get_presigned_url(uploaded)
    return presigned


def _enqueue_filing_task(filing_id: uuid.UUID) -> None:
    try:
        from parse.tasks import process_filing  # Lazy import to avoid circular dependency
    except ImportError:
        logger.warning("process_filing task not available yet. Skipping enqueue.")
        return

    if hasattr(process_filing, "delay"):
        process_filing.delay(str(filing_id))
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

            package_data = None
            zip_bytes = client.download_document_zip(receipt_no)
            if zip_bytes:
                package_data = parse_filing_bundle(
                    receipt_no=receipt_no,
                    data=zip_bytes,
                    save_dir=UPLOAD_DIR,
                    download_url=client.make_document_url(receipt_no),
                )

            if not package_data:
                logger.info("Falling back to viewer download for %s.", receipt_no)
                package_data = fetch_viewer_bundle(client.make_viewer_url(receipt_no), UPLOAD_DIR)

            if not package_data:
                logger.error("Failed to obtain filing package for %s. Skipping.", receipt_no)
                continue

            pdf_path = package_data.get("pdf")
            xml_entries = []
            for xml_path in package_data.get("xml") or []:
                entry = {"path": xml_path}
                if minio_service.is_enabled():
                    object_name = f"{receipt_no}/xml/{Path(xml_path).name}"
                    uploaded_xml = minio_service.upload_file(
                        xml_path,
                        object_name=object_name,
                        content_type="application/xml",
                    )
                    if uploaded_xml:
                        entry["storage"] = "minio"
                        entry["object"] = uploaded_xml
                xml_entries.append(entry)

            source_files = {
                "package": package_data.get("download_url"),
                "pdf": pdf_path,
                "xml": xml_entries,
                "attachments": package_data.get("attachments"),
            }

            try:
                filed_at = datetime.strptime(meta.get("rcept_dt"), "%Y%m%d") if meta.get("rcept_dt") else None
            except ValueError:
                filed_at = None

            new_filing = Filing(
                id=uuid.uuid4(),
                corp_code=meta.get("corp_code"),
                corp_name=meta.get("corp_name"),
                ticker=meta.get("stock_code"),
                report_name=meta.get("report_nm"),
                title=meta.get("report_nm"),
                receipt_no=receipt_no,
                filed_at=filed_at,
                file_name=Path(pdf_path).name if pdf_path else None,
                file_path=pdf_path,
                status=STATUS_PENDING,
                analysis_status=STATUS_PENDING,
                urls={
                    "viewer": client.make_viewer_url(receipt_no),
                    "download": package_data.get("download_url"),
                },
                source_files=source_files,
            )

            try:
                db.add(new_filing)
                db.commit()
                db.refresh(new_filing)
                existing_receipts.add(receipt_no)
            except IntegrityError:
                db.rollback()
                logger.info("Filing %s already exists. Skipping duplicate insert.", receipt_no)
                continue

            presigned_url = _ensure_minio_copy(receipt_no, pdf_path)
            if presigned_url:
                urls = new_filing.urls or {}
                urls["minio_url"] = presigned_url
                new_filing.urls = urls
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

            _enqueue_filing_task(new_filing.id)
            created_count += 1

        logger.info("Seeded %d new filings.", created_count)
        return created_count

    except Exception as exc:
        logger.error("Error during DART seed: %s", exc, exc_info=True)
        raise

    finally:
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
