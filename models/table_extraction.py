import uuid

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy.sql import func

from database import Base


class TableMeta(Base):
    __tablename__ = "table_meta"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filing_id = Column(UUID(as_uuid=True), ForeignKey("filings.id", ondelete="CASCADE"), nullable=False, index=True)
    receipt_no = Column(String, nullable=True, index=True)
    corp_code = Column(String, nullable=True, index=True)
    corp_name = Column(String, nullable=True)
    ticker = Column(String, nullable=True, index=True)
    table_type = Column(String, nullable=False, index=True)
    table_title = Column(String, nullable=True)
    page_number = Column(Integer, nullable=True)
    table_index = Column(Integer, nullable=True)
    header_rows = Column(Integer, nullable=False, default=1)
    row_count = Column(Integer, nullable=False, default=0)
    column_count = Column(Integer, nullable=False, default=0)
    non_empty_cells = Column(Integer, nullable=False, default=0)
    confidence = Column(Float, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    checksum = Column(String, nullable=True)
    column_headers = Column(JSON, nullable=True)
    quality = Column(JSON, nullable=True)
    table_json = Column(JSON, nullable=True)
    html = Column(Text, nullable=True)
    csv = Column(Text, nullable=True)
    extra = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    cells: Mapped[list["TableCell"]] = relationship(
        "TableCell",
        back_populates="table",
        cascade="all, delete-orphan",
    )


class TableCell(Base):
    __tablename__ = "table_cells"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_id = Column(
        UUID(as_uuid=True),
        ForeignKey("table_meta.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_index = Column(Integer, nullable=False)
    column_index = Column(Integer, nullable=False)
    header_path = Column(JSON, nullable=True)
    raw_value = Column(Text, nullable=True)
    normalized_value = Column(Text, nullable=True)
    numeric_value = Column(Numeric, nullable=True)
    value_type = Column(String, nullable=True, index=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    table: Mapped[TableMeta] = relationship("TableMeta", back_populates="cells")


__all__ = ["TableMeta", "TableCell"]
