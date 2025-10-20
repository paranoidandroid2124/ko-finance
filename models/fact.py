from sqlalchemy import Column, String, Text, JSON, ForeignKey, Float, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from database import Base

DEFAULT_METHOD = "llm_extraction"


class ExtractedFact(Base):
    __tablename__ = "extracted_facts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filing_id = Column(UUID(as_uuid=True), ForeignKey("filings.id"), nullable=False, index=True)

    fact_type = Column(String, nullable=False, index=True)
    value = Column(String, nullable=False)
    unit = Column(String, nullable=True)
    currency = Column(String, nullable=True)

    anchor_page = Column(Integer, nullable=True)
    anchor_quote = Column(Text, nullable=True)
    anchor = Column(JSON, nullable=True)

    method = Column(String, default=DEFAULT_METHOD, nullable=False)
    confidence_score = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
