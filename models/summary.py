from sqlalchemy import Column, Text, ForeignKey, Float, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from database import Base


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filing_id = Column(UUID(as_uuid=True), ForeignKey("filings.id"), nullable=False, index=True)

    who = Column(Text, nullable=True)
    what = Column(Text, nullable=True)
    when = Column(Text, nullable=True)
    where = Column(Text, nullable=True)
    how = Column(Text, nullable=True)
    why = Column(Text, nullable=True)
    insight = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
