"""Pydantic schemas for the Table Explorer API."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TableQuality(BaseModel):
    headerCoverage: Optional[float] = Field(default=None, description="Ratio of columns with non-empty headers.")
    nonEmptyRatio: Optional[float] = Field(default=None, description="Share of body cells that are non-empty.")
    numericRatio: Optional[float] = Field(default=None, description="Share of body cells parsed as numeric.")
    accuracyScore: Optional[float] = Field(default=None, description="Composite accuracy score used during QA.")


class TableCellResponse(BaseModel):
    rowIndex: int
    columnIndex: int
    headerPath: List[str] = Field(default_factory=list)
    value: Optional[str] = None
    normalizedValue: Optional[str] = None
    numericValue: Optional[float] = None
    valueType: Optional[str] = None
    confidence: Optional[float] = None


class TableSummary(BaseModel):
    id: UUID
    filingId: UUID
    receiptNo: Optional[str] = None
    corpCode: Optional[str] = None
    corpName: Optional[str] = None
    ticker: Optional[str] = None
    tableType: str
    tableTitle: Optional[str] = None
    pageNumber: Optional[int] = None
    tableIndex: Optional[int] = None
    rowCount: int
    columnCount: int
    headerRows: int
    confidence: Optional[float] = None
    createdAt: datetime
    updatedAt: datetime
    quality: Optional[TableQuality] = None


class TableListResponse(BaseModel):
    items: List[TableSummary]
    total: int


class TableDetailResponse(TableSummary):
    columnHeaders: List[List[str]] = Field(default_factory=list, description="Header hierarchy per column.")
    tableJson: Optional[dict] = Field(default=None, description="Full JSON representation of the table.")
    cells: List[TableCellResponse] = Field(default_factory=list)


__all__ = [
    "TableQuality",
    "TableCellResponse",
    "TableSummary",
    "TableListResponse",
    "TableDetailResponse",
]
