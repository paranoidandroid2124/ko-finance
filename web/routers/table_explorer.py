from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models.table_extraction import TableCell, TableMeta
from schemas.api.table_explorer import (
    TableCellResponse,
    TableDetailResponse,
    TableListResponse,
    TableQuality,
    TableSummary,
)
from services.plan_service import PlanContext
from web.deps import require_plan_feature

router = APIRouter(prefix="/table-explorer", tags=["Table Explorer"])


def _quality(payload: Optional[dict]) -> Optional[TableQuality]:
    if not payload:
        return None
    return TableQuality(
        headerCoverage=payload.get("headerCoverage"),
        nonEmptyRatio=payload.get("nonEmptyRatio"),
        numericRatio=payload.get("numericRatio"),
        accuracyScore=payload.get("accuracyScore"),
    )


def _to_summary(row: TableMeta) -> TableSummary:
    return TableSummary(
        id=row.id,
        filingId=row.filing_id,
        receiptNo=row.receipt_no,
        corpCode=row.corp_code,
        corpName=row.corp_name,
        ticker=row.ticker,
        tableType=row.table_type,
        tableTitle=row.table_title,
        pageNumber=row.page_number,
        tableIndex=row.table_index,
        rowCount=row.row_count,
        columnCount=row.column_count,
        headerRows=row.header_rows,
        confidence=row.confidence,
        createdAt=row.created_at,
        updatedAt=row.updated_at,
        quality=_quality(row.quality),
    )


def _load_cells(db: Session, table_id: UUID) -> List[TableCellResponse]:
    rows = (
        db.query(TableCell)
        .filter(TableCell.table_id == table_id)
        .order_by(TableCell.row_index.asc(), TableCell.column_index.asc())
        .all()
    )
    return [
        TableCellResponse(
            rowIndex=cell.row_index,
            columnIndex=cell.column_index,
            headerPath=cell.header_path or [],
            value=cell.raw_value,
            normalizedValue=cell.normalized_value,
            numericValue=float(cell.numeric_value) if cell.numeric_value is not None else None,
            valueType=cell.value_type,
            confidence=cell.confidence,
        )
        for cell in rows
    ]


@router.get("/tables", response_model=TableListResponse)
def list_tables(
    table_type: Optional[str] = Query(default=None, description="Filter by table type."),
    receipt_no: Optional[str] = Query(default=None, description="Filter by DART receipt number."),
    ticker: Optional[str] = Query(default=None, description="Filter by ticker."),
    corp_code: Optional[str] = Query(default=None, description="Filter by corp code."),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: PlanContext = Depends(require_plan_feature("table.explorer")),
) -> TableListResponse:
    query = db.query(TableMeta)
    if table_type:
        query = query.filter(TableMeta.table_type == table_type)
    if receipt_no:
        query = query.filter(TableMeta.receipt_no == receipt_no)
    if ticker:
        query = query.filter(TableMeta.ticker == ticker)
    if corp_code:
        query = query.filter(TableMeta.corp_code == corp_code)

    total = query.count()
    rows = (
        query.order_by(TableMeta.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [_to_summary(row) for row in rows]
    return TableListResponse(items=items, total=total)


@router.get("/tables/{table_id}", response_model=TableDetailResponse)
def get_table_detail(
    table_id: UUID,
    db: Session = Depends(get_db),
    _: PlanContext = Depends(require_plan_feature("table.explorer")),
) -> TableDetailResponse:
    table = db.get(TableMeta, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table metadata not found.")

    cells = _load_cells(db, table_id)
    return TableDetailResponse(
        **_to_summary(table).dict(),
        columnHeaders=table.column_headers or [],
        tableJson=table.table_json,
        cells=cells,
    )
