import uuid

from sqlalchemy import Column, DateTime, Float, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from database import Base

STATUS_PENDING = "PENDING"
STATUS_COMPLETED = "COMPLETED"
STATUS_PARTIAL = "PARTIAL"
STATUS_FAILED = "FAILED"

ANALYSIS_PENDING = "PENDING"
ANALYSIS_ANALYZED = "ANALYZED"
ANALYSIS_PARTIAL = "PARTIAL"
ANALYSIS_FAILED = "FAILED"


class Filing(Base):
    __tablename__ = "filings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    corp_code = Column(String, index=True, nullable=True)
    corp_name = Column(String, nullable=True)
    ticker = Column(String, index=True, nullable=True)
    market = Column(String, nullable=True, index=True)

    title = Column(String, nullable=True)
    report_name = Column(String, nullable=True)
    report_code = Column(String, unique=True, nullable=True)
    receipt_no = Column(String, unique=True, index=True, nullable=True)
    filed_at = Column(DateTime, nullable=True, index=True)

    file_name = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    urls = Column(JSON, nullable=True)
    source_files = Column(JSON, nullable=True)

    raw_md = Column(Text, nullable=True)
    chunks = Column(JSON, nullable=True)

    status = Column(String, nullable=False, default=STATUS_PENDING, index=True)
    analysis_status = Column(String, nullable=False, default=ANALYSIS_PENDING, index=True)
    category = Column(String, nullable=True, index=True)
    category_confidence = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
